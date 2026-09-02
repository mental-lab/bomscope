"""PostgreSQL persistence backend for bomscope scan results.

Stores normalized scan, repository, and dependency data so it can be joined
with engineering telemetry (e.g. DevLake) using ``repo_full_name`` as the
natural key.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB as _PG_JSONB
from sqlalchemy.orm import declarative_base, sessionmaker

# JSON column that uses JSONB on Postgres, generic JSON elsewhere (SQLite).
JSONB = JSON().with_variant(_PG_JSONB, "postgresql")

Base = declarative_base()


class BomscopeScan(Base):
    __tablename__ = "bomscope_scan"

    id = Column(String(64), primary_key=True)
    organization_name = Column(String(255), nullable=False)
    platform = Column(String(64), nullable=False)
    scan_timestamp = Column(DateTime, nullable=False, index=True)
    total_projects = Column(Integer, nullable=False, default=0)
    analyzed_projects = Column(Integer, nullable=False, default=0)
    total_dependencies = Column(Integer, nullable=False, default=0)
    trusted_registries = Column(JSONB, nullable=True)
    raw_analysis = Column(JSONB, nullable=True)

    repositories = None  # type: ignore  # set by relationship via backref
    dependencies = None  # type: ignore

    __table_args__ = (
        Index("idx_scan_org_time", "organization_name", "scan_timestamp"),
    )


class BomscopeRepository(Base):
    __tablename__ = "bomscope_repository"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(
        String(64),
        ForeignKey("bomscope_scan.id", ondelete="CASCADE"),
        nullable=False,
    )
    repo_full_name = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(512), nullable=True)
    platform = Column(String(64), nullable=True)
    default_branch = Column(String(255), nullable=True)
    language = Column(String(64), nullable=True)
    head_sha = Column(String(64), nullable=True)
    primary_ecosystem = Column(String(64), nullable=True)
    dependency_count = Column(Integer, nullable=False, default=0)
    has_dockerfile = Column(Boolean, nullable=False, default=False)
    uses_trusted = Column(Boolean, nullable=False, default=False)
    workflow_count = Column(Integer, nullable=False, default=0)
    vuln_critical = Column(Integer, nullable=False, default=0)
    vuln_high = Column(Integer, nullable=False, default=0)
    vuln_total = Column(Integer, nullable=False, default=0)
    risky_image_count = Column(Integer, nullable=False, default=0)
    copyleft_count = Column(Integer, nullable=False, default=0)
    eol_count = Column(Integer, nullable=False, default=0)
    eol_approaching_count = Column(Integer, nullable=False, default=0)
    raw_data = Column(JSONB, nullable=True)

    __table_args__ = (Index("idx_repo_scan", "scan_id", "repo_full_name"),)


class BomscopeSettings(Base):
    """Server-side dashboard settings (single-row key/value store)."""
    __tablename__ = "bomscope_settings"

    key = Column(String(64), primary_key=True)
    value = Column(String(1024), nullable=False, default="")


class BomscopeAuthToken(Base):
    """User-created API access tokens (named, scoped, expiring).

    The raw token is never stored — only a SHA-256 digest and a short
    display prefix, so a DB dump cannot be replayed.
    """
    __tablename__ = "bomscope_auth_token"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    token_prefix = Column(String(16), nullable=False)
    scope = Column(String(16), nullable=False)  # 'admin' | 'viewer'
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)


class BomscopeDependency(Base):
    __tablename__ = "bomscope_dependency"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(
        String(64),
        ForeignKey("bomscope_scan.id", ondelete="CASCADE"),
        nullable=False,
    )
    repo_full_name = Column(String(255), nullable=False, index=True)
    ecosystem = Column(String(64), nullable=False)
    package_name = Column(String(255), nullable=False)
    version = Column(String(255), nullable=True)
    latest_version = Column(String(255), nullable=True)
    freshness = Column(String(32), nullable=True)

    __table_args__ = (
        Index("idx_dep_scan", "scan_id", "ecosystem"),
        Index("idx_dep_package", "ecosystem", "package_name"),
    )


def _repo_full_name(url: str) -> str:
    """Return a normalized ``host/owner/repo`` identifier from a remote URL."""
    if not url:
        return ""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return f"{parsed.netloc}{path}".lower()


def _scan_id(analysis: Dict[str, Any]) -> str:
    org = analysis.get("organization_name", "")
    platform = analysis.get("platform", "")
    timestamp = analysis.get("timestamp", "") or datetime.now(timezone.utc).isoformat()
    seed = f"{org}:{platform}:{timestamp}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def connect(url: str) -> Any:
    """Create a SQLAlchemy engine and ensure the schema exists."""

    if url.startswith("sqlite"):
        # Ensure the SQLite file's parent dir exists (runtimes have no shell
        # to pre-create it)
        path = url.split("///")[-1] if "///" in url else None
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url, future=True)

    # Schema DDL runs once per process per URL. The scheduler thread also calls
    # connect() every tick; running any DDL on every tick can deadlock against
    # scan-time row inserts in Postgres.
    with _migrate_lock:
        already = url in _migrated_urls
        if not already:
            _migrated_urls.add(url)
    if not already:
        Base.metadata.create_all(engine)
    return engine


# Guard for once-per-process schema DDL (see connect()).
_migrated_urls: set = set()
_migrate_lock = threading.Lock()


def load_latest_projects(engine: Any, organization_name: str) -> Dict[str, Dict[str, Any]]:
    """Load per-repo project data from the most recent scan of an org.

    Returns a map of normalized repo_full_name -> {'head_sha': str, 'project': dict}
    for use by incremental scans.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    try:
        latest_scan = session.execute(
            select(BomscopeScan)
            .where(BomscopeScan.organization_name == organization_name)
            .order_by(BomscopeScan.scan_timestamp.desc())
        ).scalars().first()
        if not latest_scan:
            return {}

        repos = session.execute(
            select(BomscopeRepository).where(
                BomscopeRepository.scan_id == latest_scan.id
            )
        ).scalars().all()

        result = {}
        for r in repos:
            if r.raw_data:
                result[r.repo_full_name] = {
                    "head_sha": r.head_sha,
                    "project": r.raw_data,
                }
        return result
    finally:
        session.close()


def load_setting(engine: Any, key: str, default: str = "") -> str:
    """Read a dashboard setting (e.g. adoption_patterns) from the settings table."""
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    try:
        row = session.get(BomscopeSettings, key)
        return row.value if row else default
    finally:
        session.close()


def persist_analysis(engine: Any, analysis: Dict[str, Any]) -> str:
    """Persist a normalized ``analysis`` dict and return the generated scan id."""
    Session = sessionmaker(bind=engine, future=True)
    session = Session()

    scan_id = _scan_id(analysis)
    timestamp = analysis.get("timestamp") or datetime.now(timezone.utc).isoformat()

    scan = BomscopeScan(
        id=scan_id,
        organization_name=analysis.get("organization_name", ""),
        platform=analysis.get("platform", ""),
        scan_timestamp=timestamp,
        total_projects=int(analysis.get("total_projects", 0) or 0),
        analyzed_projects=int(analysis.get("analyzed_projects", 0) or 0),
        total_dependencies=int(analysis.get("total_dependencies", 0) or 0),
        trusted_registries=analysis.get("trusted_registries"),
        raw_analysis=analysis,
    )
    session.add(scan)
    session.flush()  # ensure scan row exists before children reference it

    repo_records: List[BomscopeRepository] = []
    dep_records: List[BomscopeDependency] = []

    for project in analysis.get("projects", []):
        repository = project.get("repository", {})
        url = repository.get("url", "")
        full_name = _repo_full_name(url)

        manifests = project.get("manifests", [])
        primary_eco = manifests[0]["ecosystem"] if manifests else None

        dockerfile_adoption = project.get("dockerfile_adoption") or {}
        has_dockerfile = bool(dockerfile_adoption.get("dockerfiles_found", 0) > 0)
        uses_trusted = bool(dockerfile_adoption.get("adoption_detected", False))
        workflow_count = int(
            dockerfile_adoption.get("workflow_count", 0)
            or len(dockerfile_adoption.get("workflows", []) or [])
        )
        risky_image_count = len(dockerfile_adoption.get("risky_images", []) or [])

        vuln_summary = project.get("vulnerability_summary") or {}
        license_summary = project.get("license_summary") or {}
        eol_summary = project.get("eol_summary") or {}

        repo_records.append(
            BomscopeRepository(
                scan_id=scan_id,
                repo_full_name=full_name,
                name=repository.get("name", ""),
                url=url,
                platform=repository.get("platform", ""),
                default_branch=repository.get("default_branch", ""),
                language=repository.get("language"),
                head_sha=repository.get("head_sha"),
                primary_ecosystem=primary_eco,
                dependency_count=int(project.get("total_dependencies", 0) or 0),
                has_dockerfile=has_dockerfile,
                uses_trusted=uses_trusted,
                workflow_count=workflow_count,
                vuln_critical=int(vuln_summary.get("critical", 0) or 0),
                vuln_high=int(vuln_summary.get("high", 0) or 0),
                vuln_total=int(vuln_summary.get("total", 0) or 0),
                risky_image_count=risky_image_count,
                copyleft_count=int(license_summary.get("copyleft_count", 0) or 0),
                eol_count=int(eol_summary.get("eol_count", 0) or 0),
                eol_approaching_count=int(eol_summary.get("approaching_count", 0) or 0),
                raw_data=project,
            )
        )

        # A scan can find the same package in multiple manifests (e.g. syft
        # reporting actions/checkout@v4 from every workflow file). Dedupe on
        # (ecosystem, package, version) per repo so one row = one dependency.
        seen_deps = set()
        for manifest in manifests:
            ecosystem = manifest.get("ecosystem", "")
            for dep in manifest.get("dependencies", []):
                key = (ecosystem, dep.get("name", ""), dep.get("version"))
                if key in seen_deps:
                    continue
                seen_deps.add(key)
                dep_records.append(
                    BomscopeDependency(
                        scan_id=scan_id,
                        repo_full_name=full_name,
                        ecosystem=ecosystem,
                        package_name=dep.get("name", ""),
                        version=dep.get("version"),
                        latest_version=dep.get("latest_version"),
                        freshness=dep.get("freshness"),
                    )
                )

    session.add_all(repo_records)
    # Batch insert dependencies to avoid large per-object overhead.
    for i in range(0, len(dep_records), 1000):
        session.add_all(dep_records[i : i + 1000])

    session.commit()
    session.close()
    return scan_id
