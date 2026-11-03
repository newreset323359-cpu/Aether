# AETHER v0.9 — Institutional Portfolio Management

## Delivered
- Backend-connected Institutional workspace in the Android-first PWA: configure API URL, optional API key, list/create/select backend portfolios, view NAV, TWR, XIRR, risk ratios, contribution and consolidated portfolio report.
- Multi-portfolio consolidation grouped by base currency; no silent FX conversion.
- Daily security return contribution aggregated to sector and asset class using prior-close weights and dated imported bars.
- Admin-managed user and portfolio role registry (`owner`, `manager`, `analyst`, `trader`, `viewer`) with audit events.
- Optional global API-key guard (`AETHER_API_KEY`) for all `/api/*` routes.
- Separate admin key (`AETHER_ADMIN_KEY`) required for user creation and portfolio role assignment.
- Provider interface contracts for authorized market-data and broker adapters.
- Institutional portfolio summary report endpoint.

## New endpoints
- `GET /api/v1/portfolios/consolidated`
- `GET /api/v1/reports/portfolio-summary`
- `GET /api/v1/portfolios/{id}/performance/attribution/contribution`
- `POST /api/v1/access/users`
- `POST /api/v1/access/portfolios/{id}/grant`
- `GET /api/v1/access/portfolios/{id}`

## Configure
- `AETHER_API_KEY`: optional shared API key. When set, all `/api/*` requests require `X-Aether-API-Key`.
- `AETHER_ADMIN_KEY`: required for access-registry administration endpoints; pass as `X-Aether-Admin-Key`.
- PWA Institutional workspace stores API URL and optional API key in browser local storage. For Android, the backend must be reachable from the phone; `127.0.0.1` refers to the phone itself, not a remote computer.

## Limitations that remain
- User/role registry is an administrative entitlement directory, not full login/identity management. It does not yet enforce per-user row-level access across every legacy endpoint. Use the global API key and network/TLS controls; production SSO, password lifecycle, MFA, tenant isolation and role enforcement remain required.
- No live NSE/BSE provider or broker adapter is activated. Contracts are supplied; credentials, commercial data entitlements and broker-specific order semantics are required.
- Contribution uses prior-close weights and close-to-close returns. Trades are assumed executed at close on their trade date. It excludes fees, cash return, FX, corporate actions and securities without matched adjacent bars.
- Consolidation groups portfolios by currency and does not translate FX.
- Daily TWR assumes external flows at end of day; exact intraday flow timing requires intraday valuation/flow timestamps.
- No automatic reconciliation with custodian/broker statements, derivatives margin valuation, accrued income or tax accounting.
