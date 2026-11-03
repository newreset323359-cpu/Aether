# AETHER v1.0 — Production Infrastructure Foundation

## Delivered
- Individual user authentication with salted PBKDF2-HMAC-SHA256 password hashes.
- Signed HS256 JWT bearer tokens with 60-minute expiry.
- One-time first-administrator bootstrap protected by `AETHER_BOOTSTRAP_KEY`.
- Admin user creation, disable/activate, password change, portfolio grants and revocation.
- Enforced portfolio-level access checks across `/api/v1/portfolios/{id}` routes.
- Role policy: viewer/analyst read-only; trader can submit transaction-ledger writes; owner/manager can write portfolio data.
- Admin-only audit endpoint.
- Optional shared API perimeter key in addition to user JWT.
- Exact-origin CORS allowlist via `AETHER_CORS_ORIGINS`.
- `/ready` database readiness endpoint and `/api/v1/integrations/status`.
- PWA sign-in/bootstrap/logout flow; bearer token kept in sessionStorage.
- v0.9 SQLite schema migration adds authentication fields without deleting existing records.
- Integration status for CSV/demo and configured-but-not-implemented vendor/broker adapters.

## New endpoints
- `POST /api/v1/auth/bootstrap`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/change-password`
- `POST /api/v1/admin/users`
- `GET /api/v1/admin/users`
- `POST /api/v1/admin/users/{username}/status`
- `POST /api/v1/admin/portfolios/{portfolio_id}/grant`
- `DELETE /api/v1/admin/portfolios/{portfolio_id}/users/{username}`
- `GET /api/v1/integrations/status`
- `GET /ready`

## Important production requirements
This is a production infrastructure foundation, not a certified production trading system. No live NSE/BSE data adapter or broker order adapter is activated. Provider contracts and integration status are present; commercial data entitlements, provider-specific adapter code, API credentials and broker approvals remain necessary.
SSO/OIDC, MFA, refresh-token rotation/revocation, distributed rate limiting, PostgreSQL row-level security, secret-manager integration, penetration testing, backups/DR and broker reconciliation remain out of scope. Deploy behind a hardened HTTPS reverse proxy/API gateway; use PostgreSQL, restrict network access, and set exact CORS origins.
