# Security Policy

## Reporting a vulnerability

Please do **not** open a public issue for security problems in bomscope.

Email: security@bomscope.dev

If the address above isn't reachable yet, open a private security advisory on
GitHub (Security → Report a vulnerability) — those are visible only to maintainers.

Include:

- Affected version / commit
- Steps to reproduce (minimal if possible)
- Impact assessment (what an attacker could do)

We aim to acknowledge within 72 hours and release a fix or mitigation within 14 days
for critical issues.

## Scope

- The API served by `bomscope-web`
- The analyzer (git/syft/grype orchestration)
- The compose stack and Dockerfile
- The CLI in `main.py`

Out of scope: vulnerabilities in syft/grype themselves (report upstream —
[Anchore](https://github.com/anchore)) or the base-image vendors whose registries
you scan.

## Threat model & access control

bomscope assumes it runs on a **trusted internal network or behind a terminating
reverse proxy** — it does not terminate TLS itself. Pair the built-in auth with
TLS at the proxy layer for any deployment reachable beyond localhost.

**Token model (self-hosted, zero-friction bootstrap):**

- `BOMSCOPE_ADMIN_TOKEN` — gates **all writes** (`POST /api/scans/run`,
  `PUT /api/config/*`). If unset, a token is generated on first boot, written to
  `/data/initial_admin_token` (mode 600) and printed **once** to container logs.
- `BOMSCOPE_VIEWER_TOKEN` — optional read-only seat. When set, **all reads**
  under `/api/*` also require a token. When unset, reads remain open but writes
  are still admin-gated.
- Only `/api/health` and `/api/auth/check` are anonymously reachable
  (load balancer health checks / UI unlock handshake).
- Env and bootstrap tokens resolve from env or the bootstrap file, **never the
  DB**, so dropping the database can't lock you out and query bugs can't
  exfiltrate them.
- **User-managed access tokens** (Settings → Access Tokens, admin-gated):
  named, scoped (`viewer` read-only; `admin` full), expiring (default 30 days;
  0 = never), one-time reveal of the `bsc_…` secret — only a SHA-256 digest and
  an 8-character display prefix are stored. Revocation is soft (`revoked_at`),
  keeping an audit trail; `last_used_at` updates on every authenticated call.
- **Read-open rule:** if no viewer env-token is set **and** no live user tokens
  exist, reads stay open (early-boot convenience). The moment an admin mints
  any token, instance reads go closed-by-default — set `BOMSCOPE_VIEWER_TOKEN`
  to pin read-access at the OS level instead.

**Hygiene:**            `q1
- Rotate the root credential: set a new `BOMSCOPE_ADMIN_TOKEN` env and
  restart — old bootstrapped credential is superseded.
- Prefer user-managed tokens (they revoke/expire without a restart) for
  day-to-day sharing; treat the root token strictly as bootstrap.
- The platform source token is Fernet-encrypted at rest and never in responses.
- Log scrubbing strips tokens before persistence to scan logs.

## CORS & transport

- CORS is allow-listed, defaulting to localhost origins only
  (`BOMSCOPE_ALLOWED_ORIGINS` to expose cross-origin).
- Railway/Render/other PaaS: front the service with their TLS-terminating
  router, do not publish `:8000` directly to the internet.

## Secret handling

All third-party tokens (platform PATs, registry creds) live **only** in:

- The `bomscope_settings` database table — **encrypted at rest with Fernet**
  (symmetric AES). The key comes from `BOMSCOPE_SECRET_KEY` or is generated
  once into `<data_dir>/.secret` (mode 0600). Tokens are never returned by the
  API.
- Environment variables you set at install time (these take precedence over
  settings stored via the dashboard).

Tokens are never logged — git stderr is scrubbed for credentials before it hits
any log line — never sent to any endpoint except the platform/vendor they
belong to, and never included in scans, exports, or error messages.
