# bomscope Enterprise Edition (ee/)

This directory will hold bomscope's enterprise features. Nothing lives here yet —
the core product (everything outside this directory) is Apache-2.0 and fully
self-sufficient.

## How the boundary works

- **Core** (everything else in the repo): Apache-2.0, free forever. Scanning,
  dashboard, insights, API, scheduler, self-managed install — all of it.
- **EE** (`ee/`): commercial license, ships separately. Enterprise governance and
  scale features only — SSO/SAML, RBAC, audit logging, policy controls,
  multi-tenancy, compliance exports, air-gapped deployment.

Two rules we commit to:

1. **Core never imports from `ee/`.** The arrow of dependency goes one way.
   `bomscope/core = product`, `bomscope/core + ee/ = enterprise build`.
2. **Nothing moves in.** A feature that ships in core stays in core.
