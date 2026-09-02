<p align="center">
  <img src="assets/logo.svg" alt="bomscope logo" width="96">
</p>

<h1 align="center">bomscope</h1>

<p align="center"><b>Supply-chain intelligence for your org's code — one dashboard, self-hosted, no SaaS.</b></p>

bomscope scans every repository in your GitHub org, GitLab group, or Azure DevOps
project and turns the dependency inventory into answers:

- **End-of-life runtimes and images** — which repos run EOL Node/Python, and since when
- **Risky base images** — EOL, unpinned, or pulled from untrusted registries
- **Stale dependencies** — packages ≥3 releases behind, grouped per repo
- **Copyleft exposure** — GPL/AGPL/SSPL counts per repo for license review
- **CVE posture** — critical/high counts per repo via [grype](https://github.com/anchore/grype)
- **Trusted-registry adoption** — measured and trended over time, reclassified in the background when you change patterns

Everything is searchable across the whole org: "who uses lodash" is one query.

## Why

Scanners generate findings; platform teams need **answers ranked by blast radius**.
bomscope's Insights view tells you which repos to fix first and why — not a flat list of 10,000 CVEs.

It runs **entirely on your infrastructure** — your token never leaves your network,
there is no telemetry, and there is nothing to sign up for.

## Install

Prerequisites: Docker + Docker Compose. That's it.

```bash
git clone https://github.com/mental-lab/bomscope.git
cd bomscope
docker compose up -d
```

1. Open **http://localhost:8000** → **Settings**
2. Paste a read-only platform token and your org/group name
3. (Optional) Set a repository scope to pilot on a few repos first
4. Hit **Run scan now** — progress streams live in the Settings console

From then on a built-in scheduler rescans automatically
(`SCAN_INTERVAL_HOURS=24` by default; `0` disables).

### What gets installed

Two containers, one volume:

| Container | Role |
|---|---|
| `web` | FastAPI API + Vue dashboard + background scan runner (git/syft/grype baked in) |
| `postgres` | All state: scans, settings, history |

**Upgrade:** `docker compose pull && docker compose up -d` — database migrations are
idempotent and run automatically on startup.

**Backup:** everything lives in the `postgres-data` volume.

```bash
docker compose exec postgres pg_dump -U bomscope bomscope > backup.sql
```

## Configuration

All day-to-day config lives in the dashboard's **Settings** page and is stored
server-side (shared across viewers):

- **Platform connection** — platform, instance URL, org, token, repo scope
- **Adoption source** — label + regex patterns for your trusted registries
  (e.g. `cgr.dev,registry.example.com/secure`). Saving triggers a background
  rescan so adoption numbers reclassify immediately.

Environment variables remain available for automation/CI and take precedence:

`PLATFORM`, `SOURCE`, `TOKEN`, `ORG`, `REPO_SCOPE`, `TRUSTED_REGISTRIES`,
`SCAN_INTERVAL_HOURS`, `POSTGRES_PASSWORD`, `DATABASE_URL`.

Performance and security knobs:

| Variable | Default | Effect |
|---|---|---|
| `SCAN_WORKERS` | `4` | repos scanned in parallel |
| `REPO_CACHE_DIR` | `/data/repo-cache` | persistent git mirrors — re-scans fetch deltas instead of full clones |
| `BOMSCOPE_SECRET_KEY` | generated in `/data` | Fernet key for encrypting stored tokens at rest |
| `CORS_ORIGINS` | localhost | allowed API origins |

## CLI

Everything the dashboard triggers is also a CLI (useful in CI):

```bash
docker compose --profile analyze run --rm analyzer \
  -p github -s https://github.com -t $TOKEN -o your-org -O output/analysis.json
```

Common flags:

| Flag | Effect |
|---|---|
| `-r owner/repo` | scan a single repository |
| `--trusted-registries "a,b"` | trusted image regex patterns |
| `--vulns / --no-vulns` | grype CVE scan per repo (default: off) |
| `--no-freshness` | skip upstream latest-version lookups (faster) |
| `--no-incremental` | force full rescan |
| `--database URL` | persist results to Postgres (default: `DATABASE_URL` env) |

## API

The dashboard is a consumer of the same REST API you can integrate with:
`http://localhost:8000/docs` (OpenAPI). Highlights:

- `GET /api/insights` — ranked org-wide findings
- `GET /api/repositories` — per-repo posture (`?uses_trusted=false`, `?search=…`)
- `GET /api/dependencies` — org-wide package search
- `GET /api/stats/overview`, `GET /api/stats/trends`
- `POST /api/scans/run` — trigger a background scan

## How it works

syft generates an SBOM per repo (npm, pip, Maven, Go, Dockerfiles, GitHub Actions),
grype matches CVEs, endoflife.date provides EOL status, and release registries
(PyPI/Maven/npm) provide freshness. Repos are scanned by a parallel worker pool
(`SCAN_WORKERS`), clones come from a persistent mirror cache (`REPO_CACHE_DIR` —
delta fetches, not full clones), and API endpoints never echo your token back.
Unchanged repos (same HEAD) reuse prior results — the 10th scan costs about
what the first one did.

## Project status

Early but functional: used against real orgs. Expect the schema and API to evolve;
migrations are handled automatically.

## Open core

bomscope is open core. Everything at the repository root is Apache-2.0 and free
forever. Enterprise-governance capabilities (SSO, RBAC, audit logging, policy
controls, multi-tenancy) will live in `ee/` under a commercial license as they
ship — the core never shrinks and needs nothing from `ee/` to run.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Report vulnerabilities per
[SECURITY.md](SECURITY.md).

## License

Core: [Apache-2.0](LICENSE) · Enterprise: `ee/` (commercial, future)
