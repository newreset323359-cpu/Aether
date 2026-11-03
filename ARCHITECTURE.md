# AETHER — India-first Institutional Investment Platform

## Product boundary
AETHER is an investment-management and risk-research software foundation. It is not affiliated with BlackRock and does not reproduce proprietary BlackRock code, models, data or interfaces.

## Module map
1. Core platform: API, persistence, audit event foundation.
2. Market data: provider-neutral adapter; current adapter is synthetic demo data.
3. Portfolio book: portfolio/position persistence, valuation and weights.
4. Risk: historical and parametric VaR/CVaR, drawdown, stress testing.
5. Quant research: backtest engine; GARCH/HMM/experiment tracking are next expansions.
6. Derivatives: European Black-Scholes price and first-order Greeks.
7. Optimization: equal weight and long-only mean-variance optimizer scaffold.
8. Execution: paper trading is in the Android PWA; live broker gateway is intentionally not enabled.
9. Reporting: CSV export in PWA; server-side report generation to follow.
10. Governance: audit events foundation; production controls not yet implemented.

## Android deployment topology
- Installable PWA: static files, cached shell, localStorage demo book.
- API: FastAPI service on same device where compatible, or a trusted reachable server.
- Database: SQLite for development; PostgreSQL for multi-user deployment.
- Never expose an unauthenticated API or database publicly.


## v0.4 additions
- Factor analytics and factor regression
- Out-of-sample walk-forward evaluation
- Factor shock stress testing and scenario library
- Options implied-volatility surface grid
\n\n## v0.6 additions\nInstrument reference master, configurable benchmarks, portfolio transaction ledger and average-cost holdings analytics. Instrument/benchmark data remains user-supplied; production schema changes require Alembic migrations.\n\n\n## v0.7 additions\nPortfolio cash ledger, automated trade cash movements, manual cash events, FIFO open-lot analytics and market-value exposure/concentration analytics. Currency balances are separate; no FX conversion or tax-grade accounting is performed.\n

## v0.8
See `CHANGELOG_v0.8.md` for performance and risk analytics endpoints.


## v0.9
See `CHANGELOG_v0.9.md` for connected PWA, consolidated reporting, attribution contribution, access registry and integration contracts.


## Current release v1.0
See `CHANGELOG_v1.0.md` and `SECURITY_AND_INTEGRATIONS_v1.0.md` for authentication, enforced portfolio access controls, secure PWA sign-in and deployment configuration.
