"""Bearer-token authentication for bomscope.

Model: two optional shared credentials, env-driven or bootstrapped.

- BOMSCOPE_ADMIN_TOKEN: required for all writes (settings, scan triggers).
  If unset, one is generated on first boot, written to
  ``/data/initial_admin_token`` (mode 600) and logged once, so fresh installs
  are not trivially open on a network.
- BOMSCOPE_VIEWER_TOKEN: optional read-only seat. When set, GET endpoints
  also require a token (admin counts as a viewer). When unset, reads stay
  open once writes are locked.

Tokens live in env/that file, never the DB: auth survives DB resets and
can't be exfiltrated via query bugs. Auth state is per-process; set env
vars to make it deterministic across restarts.
"""

from __future__ import annotations

import hmac
import logging
import os
import secrets
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

_DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))

_admin_token: Optional[str] = None
_viewer_token: Optional[str] = None
_bootstrapped = False


def _boot_token(env_name: str, filename: str) -> Optional[str]:
    """Resolve a token from env, a persisted bootstrap file, or generate one."""
    global _bootstrapped
    token = os.environ.get(env_name)
    if token:
        return token
    path = _DATA_DIR / filename
    try:
        if path.exists():
            return path.read_text().strip()
        token = secrets.token_urlsafe(32)
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(token + "\n")
        os.chmod(path, 0o600)
        _bootstrapped = True
        logger.warning(
            "No %s set — generated initial admin token (written to %s): %s",
            env_name, path, token,
        )
        return token
    except OSError:
        # Read-only filesystem etc.: fall back to a process-local token that
        # still gates writes for this container's lifetime.
        return secrets.token_urlsafe(32)


def _matches(token: Optional[str], presented: Optional[str]) -> bool:
    if not token:
        return False
    if presented is None:
        return False
    return hmac.compare_digest(token, presented)


def admin_token() -> str:
    global _admin_token
    if _admin_token is None:
        _admin_token = _boot_token("BOMSCOPE_ADMIN_TOKEN", "initial_admin_token")
    return _admin_token


def viewer_token() -> Optional[str]:
    global _viewer_token
    if _viewer_token is None:
        env = os.environ.get("BOMSCOPE_VIEWER_TOKEN")
        _viewer_token = env if env else ""  # "" = unset, reads open
    return _viewer_token or None


def bootstrapped() -> bool:
    return _bootstrapped


def _bearer(request: Request) -> Optional[str]:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


def _db_token_scope(presented: Optional[str], session_factory) -> Optional[str]:
    """Look up a user-created token (bsc_...) in the DB. Returns its scope
    ('admin'/'viewer') if valid, unexpired, and unrevoked; None otherwise."""
    if not presented or not presented.startswith("bsc_") or session_factory is None:
        return None
    import hashlib
    from datetime import datetime, timezone
    from sqlalchemy import select
    from .database import BomscopeAuthToken

    session = session_factory()
    try:
        row = session.execute(
            select(BomscopeAuthToken).where(
                BomscopeAuthToken.token_hash == hashlib.sha256(presented.encode()).hexdigest()
            )
        ).scalars().first()
        if row is None or row.revoked_at is not None:
            return None
        if row.expires_at is not None and row.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
            return None
        row.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.commit()
        return row.scope
    finally:
        session.close()


def require_admin(request: Request, session_factory=None) -> None:
    """Gate for writes: env/bootstrap admin token or an admin-scope DB token."""
    presented = _bearer(request)
    if _matches(admin_token(), presented):
        return
    if _db_token_scope(presented, session_factory) == "admin":
        return
    raise HTTPException(status_code=401, detail="admin token required")


def require_viewer(request: Request, session_factory=None) -> Optional[str]:
    """Gate for reads. Returns the resolved scope, or None for open mode."""
    presented = _bearer(request)
    if _matches(admin_token(), presented):
        return "admin"
    scope = _db_token_scope(presented, session_factory)
    if scope:
        return scope
    vt = viewer_token()
    if vt is None and not _db_token_mode(session_factory):
        return None  # reads open (no viewer token, no DB-user tokens active)
    if _matches(vt, presented):
        return "viewer"
    raise HTTPException(status_code=401, detail="authentication required")


def _db_token_mode(session_factory) -> bool:
    """True if any active user token exists (DB tokens switch reads to
    closed-by-default like a multi-user instance)."""
    if session_factory is None:
        return False
    from sqlalchemy import select, func
    from datetime import datetime, timezone
    from .database import BomscopeAuthToken
    session = session_factory()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        n = session.execute(
            select(func.count(BomscopeAuthToken.id)).where(
                BomscopeAuthToken.revoked_at.is_(None),
                (BomscopeAuthToken.expires_at.is_(None)) | (BomscopeAuthToken.expires_at > now),
            )
        ).scalar()
        return bool(n)
    finally:
        session.close()
