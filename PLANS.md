# bomscope — Path to Production-Ready

Phases are ordered by what blocks real orgs from putting this on a network.
Each phase is independently ship-able; shippable work is committed, the rest
is planned below. Updated as each phase lands.

## Phase 1 — Safe to deploy (auth + endpoint hygiene) — ✔ LANDED 2026-09-02

**Goal:** anyone who can reach the port cannot see data, mutate config, or
exhaust the service without credentials.

Implemented, verified live:

- ✔ **1.1** Token auth: `BOMSCOPE_ADMIN_TOKEN` gates all writes; optional
  `BOMSCOPE_VIEWER_TOKEN` gates reads. If admin token is unset, one is
  auto-generated, written to `/data/initial_admin_token` (0600), logged once
  — closed-by-default, zero lockout.
- ✔ **1.2** `/login` page, token in `localStorage`, `Authorization: Bearer`
  on every request via `apiFetch`, 401 → login redirect; role badge +
  "Sign out" in the sidebar; viewer role hides Settings.
- ✔ **1.3** CORS allow-listed (`BOMSCOPE_ALLOWED_ORIGINS`, localhost default).
- ✔ **1.4** Existing 1-concurrent-scan lock; counted on-path.
- ✔ **1.5** SECURITY.md v1.0: threat model, token model, rotation, TLS/proxy
  guidance, CORS rationale.

Verified live: anonymous GET/PUT/POST → 401 (writes) / 200 (reads);
bootstrapped admin token authenticates; PUT with admin → 200.

**User-managed personal access tokens** (later addition): Settings → Access
Tokens — named tokens with `admin`/`viewer` scope, configurable expiry
(default 30d), one-time reveal, soft-revoke with `last_used_at` audit trail.
Storage = SHA-256 digest + 8-char prefix (raw token never persisted or
returned again). Creating the first live token closes reads instance-wide.

## Phase 2 — Release mechanics — ✔ SHIPPED v0.2.0, 2026-09-02

- ✔ Repo live at github.com/mental-lab/bomscope (public), branch renamed
  master→main, commits authored as mental-lab noreply
- ✔ v0.2.0 released: github.com/mental-lab/bomscope/releases/tag/v0.2.0
  with changelog-extracted notes + SPDX SBOM asset
- ✔ Multi-arch image public on ghcr.io/mental-lab/bomscope/bomscope-web,
  cosign keyless-signed
- ✔ CI green: pytest, pip-audit (pytest→9.0.3 for PYSEC-2026-1845), Trivy
  gate (`.trivyignore` documents the pip-vendored msgpack/setuptools
  findings — unreachable from the app venv), syft SBOM, stack-boot smoke test
- Release flow from here: bump version in pyproject + `__version__` +
  CHANGELOG, `git tag vX.Y.Z && git push origin vX.Y.Z`

## Phase 3 — Professional face (draugr.dev-grade polish)

- Dashboard design pass: typography scale, spacing rhythm, empty-state copy,
  loading skeletons, logo/wordmark placement, chart labels/locales
- Landing page in `docs/` (hero, feature table, screenshots, deploy guide)
- README screenshots of the real dashboard

## Phase 4 — Docs

- Per-platform deploy guides (GitHub / GitLab / Azure DevOps)
- Upgrade & backup runbook (volume snapshots, restore)
- docstring-pass on public modules; PLANS.md per feature work

## DevOps primer (side work, not staged)

`docs/DevOps_Primer.md` — foundational artifact: what source platforms,
trends, and telemetry bomscope expects; forward pointer to the optional
DevLake/DORA integration (EE-scale engineering intelligence).
