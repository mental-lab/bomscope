"""Background scan runner for the web service.

Runs the same analyzer the CLI uses, in a daemon thread, and persists results
to the shared database. Platform config comes from the dashboard Settings
(stored in the DB); PLATFORM/SOURCE/TOKEN/ORG env vars override them for
automation. Scan logs are captured into a ring buffer so the UI can show a
live read-only console.

Usage:
    from .scan_runner import start_scan, scan_status
    started = start_scan(db_url, trusted_registries=["cgr.dev"])  # False if running
    status = scan_status()
"""

import logging
import os
import threading
import time
from collections import deque
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

_MAX_LOG_LINES = 500

_lock = threading.Lock()
_log_lines: deque = deque(maxlen=_MAX_LOG_LINES)
_state: Dict[str, Any] = {
    "status": "idle",        # idle | running | completed | failed
    "started_at": None,
    "finished_at": None,
    "error": None,
    "scan_id": None,
}


class _LogCapture(logging.Handler):
    """Collects log records into the shared ring buffer."""

    def __init__(self):
        super().__init__(level=logging.INFO)
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))

    def emit(self, record):
        try:
            _log_lines.append(self.format(record))
        except Exception:
            pass


def scan_status() -> Dict[str, Any]:
    with _lock:
        st = dict(_state)
    st["log"] = list(_log_lines)[-200:]
    return st


def start_scan(
    database_url: str,
    trusted_registries: Optional[List[str]] = None,
    reason: str = "manual",
) -> bool:
    """Kick off a background scan. Returns False if one is already running."""
    with _lock:
        if _state["status"] == "running":
            return False
        _log_lines.clear()
        _state.update({
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "error": None,
            "scan_id": None,
            "reason": reason,
        })
        _log("Scan started (%s)", reason)

    thread = threading.Thread(
        target=_run,
        args=(database_url, trusted_registries),
        daemon=True,
    )
    thread.start()
    return True


def _log(msg: str, *args) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    _log_lines.append(f"{ts} INFO    {msg % args if args else msg}")


_scheduler_started = False


def start_scheduler(database_url: str, get_patterns) -> None:
    """In-process daily-ish scan scheduler. Interval from SCAN_INTERVAL_HOURS
    (default 24, 0 disables)."""
    global _scheduler_started
    hours = float(os.getenv("SCAN_INTERVAL_HOURS", "24"))
    if hours <= 0 or _scheduler_started:
        return
    _scheduler_started = True

    def loop():
        logging.getLogger("bomscope").info(
            "Scheduler active: scanning every %.0f hours", hours)
        while True:
            time.sleep(60)
            try:
                from .database import connect
                from sqlalchemy import select
                from sqlalchemy.orm import sessionmaker
                from .database import BomscopeScan
                engine = connect(database_url)
                session = sessionmaker(bind=engine, future=True)()
                latest = session.execute(
                    select(BomscopeScan).order_by(BomscopeScan.scan_timestamp.desc())
                ).scalars().first()
                session.close()
                if latest and latest.scan_timestamp:
                    ts = latest.scan_timestamp
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) - ts < timedelta(hours=hours):
                        continue
                start_scan(database_url, trusted_registries=get_patterns(), reason="scheduled")
            except Exception as e:
                logging.getLogger("bomscope").warning("Scheduler tick failed: %s", e)

    threading.Thread(target=loop, daemon=True).start()


def _resolve_config(engine) -> Dict[str, str]:
    """Env vars win; otherwise read platform config from dashboard Settings."""
    from .database import load_setting
    from .secrets import decrypt

    env_token = os.getenv("TOKEN")
    stored_token = decrypt(load_setting(engine, "token", "")) if not env_token else ""
    return {
        "platform": os.getenv("PLATFORM") or load_setting(engine, "platform", "github"),
        "source": os.getenv("SOURCE") or load_setting(engine, "source", "https://github.com"),
        "token": env_token or stored_token,
        "org": os.getenv("ORG") or load_setting(engine, "organization", ""),
        "repo_scope": os.getenv("REPO_SCOPE") or load_setting(engine, "repo_scope", ""),
    }


def _run(database_url: str, trusted_registries: Optional[List[str]]) -> None:
    # Capture analyzer+cli logs into the ring buffer for the live console.
    pkg_logger = logging.getLogger("bomscope")
    pkg_logger.setLevel(logging.INFO)
    handler = _LogCapture()
    pkg_logger.addHandler(handler)
    try:
        from .repository_analyzer import RepositoryAnalyzer
        from .database import connect, persist_analysis

        engine = connect(database_url)
        cfg = _resolve_config(engine)
        if not cfg["token"]:
            raise RuntimeError("No access token configured — set one in Settings")
        if not cfg["org"]:
            raise RuntimeError("No organization configured — set one in Settings")

        max_workers = int(os.getenv("SCAN_WORKERS", "4"))
        cache_dir = os.getenv("REPO_CACHE_DIR") or (
            "/data/repo-cache" if os.path.isdir("/data") else None
        )
        _log("Scan config: %d workers, cache=%s", max_workers, cache_dir or "disabled")

        # Full rescan (no incremental reuse) so repos are re-classified
        # against the current trusted-registry patterns.
        analyzer = RepositoryAnalyzer(
            platform=cfg["platform"],
            url=cfg["source"],
            token=cfg["token"],
            max_workers=max_workers,
            trusted_registries=trusted_registries,
            cache_dir=cache_dir,
        )

        scope = [r.strip() for r in cfg["repo_scope"].split(",") if r.strip()]
        if scope:
            _log("Scanning %d scoped repositories", len(scope))
            analysis = analyzer.analyze_scope(cfg["org"], scope)
        else:
            analysis = analyzer.analyze_organization(cfg["org"])
        output_data = asdict(analysis)
        output_data["trusted_registries"] = trusted_registries or []
        scan_id = persist_analysis(engine, output_data)

        with _lock:
            _state.update({
                "status": "completed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "scan_id": scan_id,
            })
    except Exception as e:
        logging.getLogger("bomscope").error("Scan failed: %s", e)
        with _lock:
            _state.update({
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            })
    finally:
        pkg_logger.removeHandler(handler)
