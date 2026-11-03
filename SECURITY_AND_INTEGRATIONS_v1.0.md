# AETHER v1.0 security and integration setup

## Required server configuration

Generate secrets with a cryptographically secure random generator. Example:
`python -c "import secrets; print(secrets.token_hex(32))"`

Set:
- `AETHER_JWT_SECRET`: 64+ hex characters; used to sign short-lived (60-minute) bearer tokens.
- `AETHER_BOOTSTRAP_KEY`: one-time secret used to create the first administrator.
- `AETHER_DATABASE_URL`: persistent database. SQLite is suitable for local evaluation; use PostgreSQL for multi-user deployments.
- `AETHER_CORS_ORIGINS`: exact HTTPS origin(s) of the deployed PWA, comma-separated.
- Optional `AETHER_API_KEY`: extra shared perimeter key, in addition to individual JWT login.

Never commit secrets to source control. Use a secret manager or protected environment variables. Use TLS/HTTPS. Restrict firewall access and back up the database.

## First-time setup

1. Install backend requirements and configure environment variables from `backend/.env.example`.
2. Start the backend with `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
3. In the PWA Institutional workspace, enter backend URL, username, password, and bootstrap key.
4. Choose **First-time admin setup**. Bootstrap is permanently closed after the first administrator exists.
5. Sign in normally on later sessions.
6. Admin creates users using `POST /api/v1/admin/users` and grants portfolio access using `POST /api/v1/admin/portfolios/{portfolio_id}/grant`.
7. Admin can disable accounts with `POST /api/v1/admin/users/{username}/status` and revoke access with `DELETE /api/v1/admin/portfolios/{portfolio_id}/users/{username}`.

## Security model

- Passwords are salted PBKDF2-HMAC-SHA256 hashes; plaintext passwords are never stored.
- JWT access tokens expire after 60 minutes and are sent as `Authorization: Bearer ...`.
- PWA stores access tokens in sessionStorage (cleared when the browser session ends).
- Every `/api/*` route except bootstrap and login requires authentication.
- Portfolio IDs are checked against grants on all `/api/v1/portfolios/{id}` routes.
- Viewer/analyst roles are read-only. Trader may write trade transactions only. Owner/manager can perform portfolio writes.
- Global API key is optional extra protection, not a replacement for user authentication.
- Admin bootstrap key is not the same as API key or JWT secret.

## Provider integrations

No exchange data or broker API is activated by default. The package includes typed provider contracts in `backend/app/integrations/contracts.py` and a live integration status endpoint. You need an account, documented API, required commercial entitlements, and provider-specific adapter implementation. Store credentials in a secret manager/environment. Never paste broker passwords, TOTP seeds, API secrets or access tokens into chat or source files.

A provider adapter must implement authenticated quote/history access, retries, throttling, symbol mapping, corporate actions, exchange calendar, timestamps/timezone normalization, and provenance. Broker execution additionally requires order validation, idempotency keys, risk limits, order-state reconciliation, audit trails and user confirmation.

## Operational endpoints

- `/health`: process health.
- `/ready`: database readiness.
- `/api/v1/integrations/status`: configured vs unconfigured provider state.
- `/api/v1/audit`: audit events (authenticated; admin-only access is recommended in deployment gateway policy).

## Production caveats

This is a production-infrastructure foundation, not a certified production trading system. It does not include SSO/OIDC, MFA, refresh-token rotation/revocation list, database row-level security, distributed rate limiting, secrets-vault integration, broker adapters, market-data vendor adapters, order execution, custodian reconciliation, disaster-recovery automation, or independent penetration testing. The in-process API must be deployed behind a hardened HTTPS reverse proxy/API gateway and PostgreSQL with least-privilege credentials.


## Docker deployment
The repository includes a Dockerfile, Docker Compose PostgreSQL service and Nginx reverse proxy. Copy root `.env.example` to `.env`, set strong random secrets and the exact PWA origin, then run `docker compose up --build -d`. The included HTTP listener is for trusted LAN evaluation; configure TLS before public exposure. The database is not published to the host.

## Test-mode warning
`AETHER_ENV=test` activates a test-only authentication bypass from `backend/tests/conftest.py`. Never set this variable in a deployed environment.
