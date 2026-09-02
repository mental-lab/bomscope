"""FastAPI web service for bomscope.

Serves scan results from PostgreSQL and hosts the built Vue dashboard.
The CLI writes to the same database, so the UI always shows the latest scan.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from .database import (
    BomscopeDependency,
    BomscopeRepository,
    BomscopeScan,
    BomscopeSettings,
    connect,
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    # Zero-dependency default: embedded SQLite. Set DATABASE_URL to Postgres
    # for production/scale installs (compose does this for you).
    "sqlite:////data/bomscope.db",
)

app = FastAPI(title="bomscope API", version="1.0.0")

# The dashboard is served by this same app (same-origin), so CORS is only
# needed for the Vite dev server or if you expose the API cross-origin.
# BOMSCOPE_ALLOWED_ORIGINS: comma-separated allow-list; leave unset for a
# strict same-origin posture.
_allowed_origins = [o.strip() for o in os.getenv(
    "BOMSCOPE_ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "PUT", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.middleware("http")
async def _security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.middleware("http")
async def _auth_gate(request, call_next):
    """Auth gate: everything under /api requires credentials except
    /api/health and /api/auth/check. Writes require the admin token; reads
    may be open unless a viewer token is configured."""
    from .auth import require_admin, require_viewer
    if request.url.path.startswith("/api/") and request.url.path not in (
        "/api/health", "/api/auth/check",
    ):
        try:
            if request.method in ("POST", "PUT", "DELETE", "PATCH"):
                require_admin(request, session_factory=lambda: _Session() if _Session else None)
            else:
                require_viewer(request, session_factory=lambda: _Session() if _Session else None)
        except HTTPException:
            return JSONResponse(status_code=401, content={"detail": "authentication required"})
    return await call_next(request)


_engine = None
_Session = None


def get_session():
    global _engine, _Session
    if _engine is None:
        _engine = connect(DATABASE_URL)
        _Session = sessionmaker(bind=_engine, future=True)
    return _Session()


def db_session():
    """FastAPI dependency: yields a session and always closes it.

    Prevents 'idle in transaction' connection leaks that hold locks and
    can block DDL migrations in other processes.
    """
    session = get_session()
    try:
        yield session
    finally:
        session.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/auth/check")
def auth_check(request: Request):
    """Report the caller's role for UI unlock decisions.

    Roles: admin (env admin token or admin-scope user token), viewer
    (viewer env token or viewer-scope user token), open (no auth needed —
    no viewer token configured and no user tokens created yet)."""
    from .auth import (
        _bearer,
        _db_token_mode,
        _db_token_scope,
        _matches,
        admin_token,
        bootstrapped,
        viewer_token,
    )
    presented = _bearer(request)
    if _matches(admin_token(), presented):
        return {"role": "admin", "bootstrapped": bootstrapped()}
    if _Session is not None:
        scope = _db_token_scope(presented, _Session)
        if scope:
            return {"role": scope, "bootstrapped": bootstrapped()}
    vt = viewer_token()
    if vt is None and not (_Session is not None and _db_token_mode(_Session)):
        return {"role": "open", "bootstrapped": bootstrapped()}
    if _matches(vt, presented):
        return {"role": "viewer", "bootstrapped": bootstrapped()}
    raise HTTPException(status_code=401, detail="authentication required")


class AuthTokenCreate(BaseModel):
    name: str
    scope: str = "viewer"            # 'admin' | 'viewer'
    expires_in_days: Optional[int] = 30  # None / 0 = never


@app.get("/api/auth/tokens")
def list_auth_tokens(session = Depends(db_session)):
    """Admin-only (middleware). Never returns token material."""
    from .database import BomscopeAuthToken
    rows = session.execute(select(BomscopeAuthToken)).scalars().all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "scope": t.scope,
            "token_prefix": t.token_prefix,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "expires_at": t.expires_at.isoformat() if t.expires_at else None,
            "revoked": t.revoked_at is not None,
            "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
        }
        for t in rows
    ]


@app.post("/api/auth/tokens", status_code=201)
def create_auth_token(cfg: AuthTokenCreate, session = Depends(db_session)):
    """Admin-only (middleware). Returns the raw token ONCE — it is hashed
    in the DB and cannot be recovered."""
    import hashlib
    import secrets
    from datetime import datetime, timedelta, timezone
    from .database import BomscopeAuthToken

    if cfg.scope not in ("admin", "viewer"):
        raise HTTPException(status_code=400, detail="scope must be admin or viewer")
    if not cfg.name.strip():
        raise HTTPException(status_code=400, detail="name is required")

    raw = "bsc_" + secrets.token_urlsafe(30)
    expires_at = None
    if cfg.expires_in_days and cfg.expires_in_days > 0:
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=cfg.expires_in_days)
    row = BomscopeAuthToken(
        name=cfg.name.strip()[:128],
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        token_prefix=raw[:8],
        scope=cfg.scope,
        expires_at=expires_at,
    )
    session.add(row)
    session.commit()
    return {
        "id": row.id,
        "name": row.name,
        "scope": row.scope,
        "token": raw,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }


@app.delete("/api/auth/tokens/{token_id}")
def revoke_auth_token(token_id: int, session = Depends(db_session)):
    """Admin-only (middleware). Revoke rather than delete keeps audit trail."""
    from datetime import datetime, timezone
    from .database import BomscopeAuthToken
    row = session.get(BomscopeAuthToken, token_id)
    if row is None:
        raise HTTPException(status_code=404, detail="token not found")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.commit()
    return {"revoked": True}


def _adoption_patterns(session) -> list[str]:
    return [p.strip() for p in _get_setting(session, "adoption_patterns", "").split(",") if p.strip()]


def _get_setting(session, key: str, default: str = "") -> str:
    row = session.get(BomscopeSettings, key)
    return row.value if row else default


def _latest_scan_id(session):
    """ID of the most recent scan, or None. List endpoints filter on this so
    they never mix rows from multiple scans (duplicates) or scan history."""
    row = session.execute(
        select(BomscopeScan.id).order_by(BomscopeScan.scan_timestamp.desc()).limit(1)
    ).scalars().first()
    return row


def _set_setting(session, key: str, value: str) -> None:
    row = session.get(BomscopeSettings, key)
    if row:
        row.value = value
    else:
        session.add(BomscopeSettings(key=key, value=value))


class AdoptionConfig(BaseModel):
    label: str = "Trusted"
    patterns: str = ""


class PlatformConfig(BaseModel):
    platform: str
    source: str
    organization: str
    repo_scope: str = ""         # comma-separated owner/repo list; empty = whole org
    token: Optional[str] = None  # optional on update; never returned


@app.on_event("startup")
def _startup():
    from .scan_runner import start_scheduler

    def fresh_patterns():
        engine = connect(DATABASE_URL)
        session = sessionmaker(bind=engine, future=True)()
        try:
            return _adoption_patterns(session)
        finally:
            session.close()

    start_scheduler(DATABASE_URL, fresh_patterns)


@app.get("/api/config")
def config(session = Depends(db_session)):
    """Dashboard configuration: user-defined settings, falling back to the
    most recent scan's trusted registries. Token is never returned."""
    stmt = select(BomscopeScan).order_by(BomscopeScan.scan_timestamp.desc())
    scan = session.execute(stmt).scalars().first()
    scan_patterns = ", ".join((scan.trusted_registries if scan else None) or [])
    return {
        "organization": _get_setting(session, "organization", scan.organization_name if scan else None),
        "adoption": {
            "label": _get_setting(session, "adoption_label", "Trusted"),
            "patterns": _get_setting(session, "adoption_patterns", scan_patterns),
        },
        "platform": {
            "platform": _get_setting(session, "platform", "github"),
            "source": _get_setting(session, "source", "https://github.com"),
            "organization": _get_setting(session, "organization", ""),
            "repo_scope": _get_setting(session, "repo_scope", ""),
            "token_set": bool(_get_setting(session, "token", "")) or bool(os.getenv("TOKEN")),
        },
    }


@app.put("/api/config/platform")
def update_platform(cfg: PlatformConfig, session = Depends(db_session)):
    """Save platform connection settings (the zero-.env path)."""
    if cfg.platform not in ("github", "gitlab", "ado"):
        raise HTTPException(status_code=400, detail="platform must be github, gitlab, or ado")
    _set_setting(session, "platform", cfg.platform)
    _set_setting(session, "source", cfg.source.strip())
    _set_setting(session, "organization", cfg.organization.strip())
    _set_setting(session, "repo_scope", cfg.repo_scope.strip())
    if cfg.token:
        from .secrets import encrypt
        _set_setting(session, "token", encrypt(cfg.token.strip()))
    session.commit()
    return {"saved": True}


@app.put("/api/config/adoption")
def update_adoption(cfg: AdoptionConfig, session = Depends(db_session)):
    """Save adoption config and kick off a background rescan so repos are
    re-classified against the new patterns."""
    _set_setting(session, "adoption_label", cfg.label.strip() or "Trusted")
    _set_setting(session, "adoption_patterns", cfg.patterns.strip())
    session.commit()

    from .scan_runner import start_scan
    scan_started = start_scan(
        DATABASE_URL,
        trusted_registries=[p.strip() for p in cfg.patterns.split(",") if p.strip()],
        reason="settings-change",
    )
    return {
        "label": cfg.label.strip() or "Trusted",
        "patterns": cfg.patterns.strip(),
        "scan_started": scan_started,
    }


@app.post("/api/scans/run")
def run_scan(session = Depends(db_session)):
    """Manually trigger a background scan using the saved adoption patterns."""
    from .scan_runner import start_scan
    started = start_scan(DATABASE_URL, trusted_registries=_adoption_patterns(session), reason="manual")
    if not started:
        raise HTTPException(status_code=409, detail="A scan is already running")
    return {"started": True}


@app.get("/api/scans/status")
def get_scan_status():
    from .scan_runner import scan_status
    return scan_status()


@app.get("/api/scans")
def list_scans(session = Depends(db_session)):
    stmt = select(BomscopeScan).order_by(BomscopeScan.scan_timestamp.desc())
    scans = session.execute(stmt).scalars().all()
    return [
        {
            "id": s.id,
            "organization_name": s.organization_name,
            "platform": s.platform,
            "scan_timestamp": s.scan_timestamp.isoformat() if s.scan_timestamp else None,
            "total_projects": s.total_projects,
            "analyzed_projects": s.analyzed_projects,
            "total_dependencies": s.total_dependencies,
        }
        for s in scans
    ]


@app.get("/api/scans/{scan_id}")
def get_scan(scan_id: str, session = Depends(db_session)):
    scan = session.get(BomscopeScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan.raw_analysis or {}


@app.get("/api/analysis/latest")
def latest_analysis(session = Depends(db_session)):
    """Return the raw analysis JSON of the most recent scan.

    Same shape as the CLI's analysis.json output, so the existing
    Vue viewer can consume it directly.
    """
    stmt = select(BomscopeScan).order_by(BomscopeScan.scan_timestamp.desc())
    scan = session.execute(stmt).scalars().first()
    if not scan:
        raise HTTPException(status_code=404, detail="No scans found")
    return scan.raw_analysis or {}


@app.get("/api/repositories")
def list_repositories(
    organization: Optional[str] = Query(default=None),
    primary_ecosystem: Optional[str] = Query(default=None),
    uses_trusted: Optional[bool] = Query(default=None),
    has_dockerfile: Optional[bool] = Query(default=None),
    limit: int = Query(default=100, le=1000),
    session = Depends(db_session),
):
    latest_id = _latest_scan_id(session)
    if latest_id is None:
        return []
    stmt = (
        select(BomscopeRepository, BomscopeScan)
        .join(BomscopeScan, BomscopeRepository.scan_id == BomscopeScan.id)
        .where(BomscopeRepository.scan_id == latest_id)
        .order_by(BomscopeRepository.repo_full_name)
    )
    if organization:
        stmt = stmt.where(BomscopeScan.organization_name == organization)
    if primary_ecosystem:
        stmt = stmt.where(BomscopeRepository.primary_ecosystem == primary_ecosystem)
    if uses_trusted is not None:
        stmt = stmt.where(BomscopeRepository.uses_trusted == uses_trusted)
    if has_dockerfile is not None:
        stmt = stmt.where(BomscopeRepository.has_dockerfile == has_dockerfile)
    stmt = stmt.limit(limit)

    rows = session.execute(stmt).all()
    return [
        {
            "repo_full_name": r.repo_full_name,
            "name": r.name,
            "url": r.url,
            "platform": r.platform,
            "organization": s.organization_name,
            "primary_ecosystem": r.primary_ecosystem,
            "dependency_count": r.dependency_count,
            "has_dockerfile": r.has_dockerfile,
            "uses_trusted": r.uses_trusted,
            "workflow_count": r.workflow_count,
            "scanned_at": s.scan_timestamp.isoformat() if s.scan_timestamp else None,
        }
        for r, s in rows
    ]


@app.get("/api/dependencies")
def list_dependencies(
    ecosystem: Optional[str] = Query(default=None),
    package_name: Optional[str] = Query(default=None),
    repo: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=1000),
    session = Depends(db_session),
):
    latest_id = _latest_scan_id(session)
    if latest_id is None:
        return []
    stmt = select(BomscopeDependency).where(
        BomscopeDependency.scan_id == latest_id).order_by(BomscopeDependency.package_name)
    if ecosystem:
        stmt = stmt.where(BomscopeDependency.ecosystem == ecosystem)
    if package_name:
        stmt = stmt.where(BomscopeDependency.package_name.ilike(f"%{package_name}%"))
    if repo:
        stmt = stmt.where(BomscopeDependency.repo_full_name.ilike(f"%{repo}%"))
    stmt = stmt.limit(limit)

    deps = session.execute(stmt).scalars().all()
    return [
        {
            "repo_full_name": d.repo_full_name,
            "ecosystem": d.ecosystem,
            "package_name": d.package_name,
            "version": d.version,
            "latest_version": d.latest_version,
            "freshness": d.freshness,
        }
        for d in deps
    ]


@app.get("/api/stats/overview")
def stats_overview(session = Depends(db_session)):

    latest_scan = session.execute(
        select(BomscopeScan).order_by(BomscopeScan.scan_timestamp.desc())
    ).scalars().first()
    if not latest_scan:
        return {
            "total_repositories": 0,
            "total_dependencies": 0,
            "repositories_with_dockerfile": 0,
            "repositories_using_trusted": 0,
            "trusted_adoption_pct": 0,
            "ecosystems": {},
        }

    total_repos = session.execute(
        select(func.count(BomscopeRepository.id))
        .where(BomscopeRepository.scan_id == latest_scan.id)
    ).scalar() or 0
    total_deps = session.execute(
        select(func.count(BomscopeDependency.id))
        .where(BomscopeDependency.scan_id == latest_scan.id)
    ).scalar() or 0
    trusted_repos = session.execute(
        select(func.count(BomscopeRepository.id)).where(
            BomscopeRepository.scan_id == latest_scan.id,
            BomscopeRepository.uses_trusted.is_(True),
        )
    ).scalar() or 0
    dockerfile_repos = session.execute(
        select(func.count(BomscopeRepository.id)).where(
            BomscopeRepository.scan_id == latest_scan.id,
            BomscopeRepository.has_dockerfile.is_(True),
        )
    ).scalar() or 0

    ecosystem_rows = session.execute(
        select(
            BomscopeDependency.ecosystem,
            func.count(BomscopeDependency.id),
        )
        .where(BomscopeDependency.scan_id == latest_scan.id)
        .group_by(BomscopeDependency.ecosystem)
    ).all()

    return {
        "total_repositories": total_repos,
        "total_dependencies": total_deps,
        "repositories_with_dockerfile": dockerfile_repos,
        "repositories_using_trusted": trusted_repos,
        "trusted_adoption_pct": round(
            (trusted_repos / dockerfile_repos * 100) if dockerfile_repos else 0, 1
        ),
        "ecosystems": {
            eco: count for eco, count in ecosystem_rows
        },
    }


@app.get("/api/insights")
def insights(session = Depends(db_session)):
    """Aggregated 'attention needed' insights: CVEs, risky images, copyleft,
    stale dependencies — grouped with affected repositories."""


    # Latest scan only — insights should reflect current state
    latest_scan = session.execute(
        select(BomscopeScan).order_by(BomscopeScan.scan_timestamp.desc())
    ).scalars().first()
    if not latest_scan:
        return {"scan_id": None, "insights": []}

    repos = session.execute(
        select(BomscopeRepository).where(BomscopeRepository.scan_id == latest_scan.id)
    ).scalars().all()

    def repo_entry(r):
        return {
            "repo_full_name": r.repo_full_name,
            "dependency_count": r.dependency_count,
        }

    groups = []

    cve_repos = sorted(
        [r for r in repos if r.vuln_critical > 0],
        key=lambda r: -r.vuln_critical,
    )
    if cve_repos:
        groups.append({
            "id": "critical-cves",
            "severity": "critical",
            "title": "Critical vulnerabilities",
            "description": f"{sum(r.vuln_critical for r in cve_repos)} critical CVEs across {len(cve_repos)} repos",
            "count": len(cve_repos),
            "repos": [{**repo_entry(r), "vuln_critical": r.vuln_critical, "vuln_high": r.vuln_high} for r in cve_repos],
        })

    risky_repos = sorted(
        [r for r in repos if r.risky_image_count > 0],
        key=lambda r: -r.risky_image_count,
    )
    if risky_repos:
        groups.append({
            "id": "risky-images",
            "severity": "high",
            "title": "Risky base images",
            "description": f"{sum(r.risky_image_count for r in risky_repos)} EOL/unpinned base images in {len(risky_repos)} repos",
            "count": len(risky_repos),
            "repos": [{**repo_entry(r), "risky_image_count": r.risky_image_count} for r in risky_repos],
        })

    eol_repos = sorted(
        [r for r in repos if r.eol_count > 0],
        key=lambda r: -r.eol_count,
    )
    if eol_repos:
        groups.append({
            "id": "eol",
            "severity": "critical",
            "title": "End-of-life software",
            "description": f"{sum(r.eol_count for r in eol_repos)} EOL runtimes/images across {len(eol_repos)} repos",
            "count": len(eol_repos),
            "repos": [{**repo_entry(r), "eol_count": r.eol_count, "eol_approaching_count": r.eol_approaching_count} for r in eol_repos],
        })

    approaching_repos = sorted(
        [r for r in repos if r.eol_count == 0 and r.eol_approaching_count > 0],
        key=lambda r: -r.eol_approaching_count,
    )
    if approaching_repos:
        groups.append({
            "id": "eol-approaching",
            "severity": "medium",
            "title": "Approaching end-of-life",
            "description": f"{sum(r.eol_approaching_count for r in approaching_repos)} items EOL within 90 days in {len(approaching_repos)} repos",
            "count": len(approaching_repos),
            "repos": [{**repo_entry(r), "eol_approaching_count": r.eol_approaching_count} for r in approaching_repos],
        })

    copyleft_repos = sorted(
        [r for r in repos if r.copyleft_count > 0],
        key=lambda r: -r.copyleft_count,
    )
    if copyleft_repos:
        groups.append({
            "id": "copyleft",
            "severity": "medium",
            "title": "Strong copyleft licenses",
            "description": f"{sum(r.copyleft_count for r in copyleft_repos)} GPL/AGPL-style packages in {len(copyleft_repos)} repos",
            "count": len(copyleft_repos),
            "repos": [{**repo_entry(r), "copyleft_count": r.copyleft_count} for r in copyleft_repos],
        })

    # Stale dependencies (only meaningful when freshness checking was enabled)
    stale_rows = session.execute(
        select(
            BomscopeDependency.repo_full_name,
            func.count(BomscopeDependency.id),
        )
        .where(
            BomscopeDependency.scan_id == latest_scan.id,
            BomscopeDependency.freshness == "stale",
        )
        .group_by(BomscopeDependency.repo_full_name)
        .order_by(func.count(BomscopeDependency.id).desc())
    ).all()
    if stale_rows:
        total_stale = sum(c for _, c in stale_rows)
        groups.append({
            "id": "stale-deps",
            "severity": "medium",
            "title": "Stale dependencies",
            "description": f"{total_stale} packages ≥3 releases behind across {len(stale_rows)} repos",
            "count": len(stale_rows),
            "repos": [{"repo_full_name": n, "stale_count": c} for n, c in stale_rows],
        })

    no_trusted = sorted(
        [r for r in repos if r.has_dockerfile and not r.uses_trusted],
        key=lambda r: -r.dependency_count,
    )
    if no_trusted:
        groups.append({
            "id": "no-trusted",
            "severity": "medium",
            "title": "Not using trusted images",
            "description": f"{len(no_trusted)} repos with Dockerfiles not using a trusted registry",
            "count": len(no_trusted),
            "repos": [repo_entry(r) for r in no_trusted],
        })

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    groups.sort(key=lambda g: severity_order.get(g["severity"], 4))

    return {
        "scan_id": latest_scan.id,
        "scan_timestamp": latest_scan.scan_timestamp.isoformat() if latest_scan.scan_timestamp else None,
        "insights": groups,
    }


@app.get("/api/trends")
def trends(session = Depends(db_session)):
    """Time-series of key metrics across all scans (DevLake-style trends)."""
    stmt = select(BomscopeScan).order_by(BomscopeScan.scan_timestamp.asc())
    scans = session.execute(stmt).scalars().all()

    series = []
    for s in scans:
        repos = session.execute(
            select(BomscopeRepository).where(BomscopeRepository.scan_id == s.id)
        ).scalars().all()
        total = len(repos)
        dockerfiles = sum(1 for r in repos if r.has_dockerfile)
        trusted = sum(1 for r in repos if r.uses_trusted)
        series.append(
            {
                "scan_id": s.id,
                "organization_name": s.organization_name,
                "scan_timestamp": s.scan_timestamp.isoformat() if s.scan_timestamp else None,
                "total_projects": s.total_projects,
                "analyzed_projects": s.analyzed_projects,
                "total_dependencies": s.total_dependencies,
                "repos_with_dockerfile": dockerfiles,
                "repos_using_trusted": trusted,
                "trusted_adoption_pct": round(
                    (trusted / dockerfiles * 100) if dockerfiles else 0, 1
                ),
            }
        )
    return series


@app.get("/api/repositories/{full_name:path}")
def get_repository(full_name: str, session = Depends(db_session)):
    """Latest detail for a single repository, including raw analysis."""
    stmt = (
        select(BomscopeRepository, BomscopeScan)
        .join(BomscopeScan, BomscopeRepository.scan_id == BomscopeScan.id)
        .where(BomscopeRepository.repo_full_name == full_name)
        .order_by(BomscopeScan.scan_timestamp.desc())
    )
    row = session.execute(stmt).first()
    if not row:
        raise HTTPException(status_code=404, detail="Repository not found")
    r, s = row

    deps = session.execute(
        select(BomscopeDependency).where(
            BomscopeDependency.scan_id == r.scan_id,
            BomscopeDependency.repo_full_name == full_name,
        )
    ).scalars().all()

    return {
        "repo_full_name": r.repo_full_name,
        "name": r.name,
        "url": r.url,
        "platform": r.platform,
        "organization": s.organization_name,
        "default_branch": r.default_branch,
        "language": r.language,
        "primary_ecosystem": r.primary_ecosystem,
        "dependency_count": r.dependency_count,
        "has_dockerfile": r.has_dockerfile,
        "uses_trusted": r.uses_trusted,
        "workflow_count": r.workflow_count,
        "scanned_at": s.scan_timestamp.isoformat() if s.scan_timestamp else None,
        "dockerfile_adoption": (r.raw_data or {}).get("dockerfile_adoption"),
        "vulnerability_summary": (r.raw_data or {}).get("vulnerability_summary"),
        "license_summary": (r.raw_data or {}).get("license_summary"),
        "vuln_critical": r.vuln_critical,
        "vuln_high": r.vuln_high,
        "vuln_total": r.vuln_total,
        "risky_image_count": r.risky_image_count,
        "copyleft_count": r.copyleft_count,
        "eol_summary": (r.raw_data or {}).get("eol_summary"),
        "eol_count": r.eol_count,
        "eol_approaching_count": r.eol_approaching_count,
        "dependencies": [
            {
                "ecosystem": d.ecosystem,
                "package_name": d.package_name,
                "version": d.version,
                "latest_version": d.latest_version,
                "freshness": d.freshness,
            }
            for d in deps
        ],
    }


# Serve the built Vue dashboard (docs/ output of `npm run build`).
# Mount last so /api/* routes take precedence.
static_dir = Path(__file__).resolve().parent.parent / "docs"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    from fastapi.responses import FileResponse

    index_html = static_dir / "index.html"

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        """Serve the SPA index.html for all non-API routes (history-mode routing)."""
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not found")
        target = static_dir / full_path
        if full_path and target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(index_html))
