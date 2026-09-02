# Contributing to bomscope

Thanks for helping make supply-chain intelligence accessible. A few conventions:

## Getting started

```bash
git clone https://github.com/mental-lab/bomscope.git
cd bomscope
docker compose up -d
```

The stack is Python (analyzer + FastAPI) and Vue 3 (dashboard). Everything runs in
Docker, so no local Python/Node setup is required — but you can run tests locally
with `pytest` inside the container if preferred.

## Where things live

- `bomscope/` — Python package: analyzer, DB models, API, scan runner, scheduler
- `main.py` — CLI entrypoint (Click)
- `viewer/src/` — Vue dashboard
- `landing/` — static landing page for bomscope.dev
- `docker-compose.yml` — the whole stack

## Conventions

- **No telemetry, ever.** If it phones home, it doesn't merge.
- **Env vars beat settings, settings beat defaults.** Config precedence is
  CLI flag → env var → dashboard Settings → built-in default.
- **Migrations are idempotent.** All DB changes go in the `migrations` list in
  `bomscope/database.py` and must be safe to re-run (`IF NOT EXISTS` etc.).
- **Scans stay cheap.** Unchanged repos reuse prior results. Never regress this.

## Testing

CI runs `pytest` and a front-end build. Before opening a PR:

```bash
docker compose exec web python -m pytest  # backend
docker compose build web                   # frontend build must succeed
```

## PRs

- Small, focused PRs. One behavior change per PR.
- Describe the *user-facing* change first, then the implementation.
- If you touched Settings/API, keep the README and landing page in sync.
