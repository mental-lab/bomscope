# Changelog

All notable changes to bomscope are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project adheres to
[Semantic Versioning](https://semver.org/).

## [0.2.0] — 2026-09-02

### Added

- **Authentication (self-hosted token model)**: all writes gated by
  `BOMSCOPE_ADMIN_TOKEN` (env or auto-bootstrapped to
  `/data/initial_admin_token`, mode 600, logged once on first boot).
  Optional `BOMSCOPE_VIEWER_TOKEN` gates reads. `/api/health` and
  `/api/auth/check` remain public.
- **User-managed access tokens**: Settings → Access Tokens — named tokens
  with `viewer`/`admin` scope, configurable expiry (default 30 days),
  one-time reveal, soft-revoke with audit trail, `last_used_at` tracking.
  Stored as SHA-256 digests; raw tokens never persist.
- **Login UI**: `/login` page, `Authorization: Bearer` injection on all
  API calls, 401 → login redirect, role badge + sign-out in the sidebar,
  Settings hidden for viewer role.
- CORS narrowed to an allow-list (`BOMSCOPE_ALLOWED_ORIGINS`, localhost
  default).
- Dependencies page: repository substring search filter.
- Global button styles (`.btn`) in the shared stylesheet.
- Release workflow: tag-triggered multi-arch image push to ghcr.io,
  cosign keyless signing, SPDX SBOM attachment.
- CI now runs the pytest suite.

### Fixed

- Duplicate dependency rows — deduped at persistence on
  (ecosystem, package, version).
- `apiFetch` import missing from DependenciesPage (runtime error).
- Sign-in button unstyled (scoped CSS leaked nowhere).

## [0.1.0] — 2026-08-31

Initial public build: GitHub/GitLab/Azure DevOps org scanning, syft/grype
dependency and CVE inventory, EOL detection via endoflife.date, license
risk, insights ranking, Vue 3 dashboard, scheduler, Docker Compose install.
