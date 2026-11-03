# AETHER v3.1 — Institutional Investment Intelligence & Research

**Research and paper-trading software. Not investment advice. No profitability guarantee.**

# AETHER v3.1 — Institutional Investment Intelligence & Research

**Research and paper-trading software. Not investment advice. No profitability guarantee.**

# AETHER v3.1 — Institutional Investment Intelligence & Research

**Research and paper-trading software. Not investment advice. No profitability guarantee.**

# AETHER v3.1 — Institutional Investment Intelligence & Research

**Research and paper-trading software. Not investment advice. No profitability guarantee.**

# AETHER v3.1 — Institutional Investment Intelligence & Research

**Research and paper-trading software. Not investment advice. No profitability guarantee.**

# AETHER v3.1 — Institutional Investment Intelligence & Research

**Research and paper-trading software. Not investment advice. No profitability guarantee.**


## Performance analytics (v0.8)
See `CHANGELOG_v0.8.md`. The new performance endpoints are in the FastAPI backend.
The PWA's pre-existing local demo portfolio remains a separate LocalStorage prototype;
it is not automatically synchronized with backend portfolios. Use the API endpoints
with ledger transactions and imported daily bars for calculated NAV and analytics.


## v0.9
See `CHANGELOG_v0.9.md` for connected PWA, consolidated reporting, attribution contribution, access registry and integration contracts.
\n\nAndroid backend setup: see `ANDROID_BACKEND_SETUP.md`.\n

## Previous release: v0.9
See `CHANGELOG_v0.9.md` and `ANDROID_BACKEND_SETUP.md` for the institutional PWA/backend workflow and setup.


## Current release v1.0
See `CHANGELOG_v1.0.md` and `SECURITY_AND_INTEGRATIONS_v1.0.md` for authentication, enforced portfolio access controls, secure PWA sign-in and deployment configuration.

## Current release: v1.0
See `CHANGELOG_v1.0.md`, `SECURITY_AND_INTEGRATIONS_v1.0.md`, and `ANDROID_BACKEND_SETUP.md`.

## v1.0 deployment
A Docker Compose PostgreSQL + Nginx deployment starter is included. Copy `.env.example` to `.env`, configure secrets and exact CORS origin, then follow `ANDROID_BACKEND_SETUP.md`. Review `SECURITY_AND_INTEGRATIONS_v1.0.md` before exposing the service.


## AutoTrader v2.0
See `AUTOTRADER_v2.0.md` for the Groww read-only adapter and paper-trading workspace.
Real Groww order execution is intentionally not included. Start with `cd backend && pip install -r requirements.txt && uvicorn app.main:app --host 0.0.0.0 --port 8000`.


## v2.1 Groww live automation (gated)
See `GROWW_LIVE_AUTOTRADING_v2.1.md`. The build contains a real Groww order adapter and a separate auto-strategy worker, but all live-trading server flags default OFF. Do not enable until Groww confirms API/algo permission and static-IP requirements are satisfied.


## Current release: v3.0 Adaptive Quant Research
See `AETHER_v3.0_ADAPTIVE_RESEARCH.md` and `CHANGELOG_v3.0.md`. New authenticated research endpoints provide regime-aware ensemble signals and strict one-step-ahead walk-forward diagnostics. These are research-only and are not connected to Groww order execution. All v2.1 live flags remain OFF.
