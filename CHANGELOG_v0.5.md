# AETHER v0.5 — Indian Market Data Infrastructure

## Added
- Validated CSV ingestion for daily/weekly/monthly OHLCV bars.
- Corporate-action CSV ingestion for dividends, splits, bonus, rights, buybacks and merger/other events.
- Persistent market bars, corporate actions and ingestion-job provenance.\n- Per-symbol data freshness/staleness endpoint.
- Duplicate protection for symbol/date/interval bars.
- Rejection reporting with source line numbers and reasons.
- Data provider registry distinguishing synthetic demo, user CSV and unconfigured licensed-provider adapter.
- APIs for historical bars, corporate actions and ingestion history.

## Data formats
OHLCV CSV headers: `symbol,date,open,high,low,close,volume`.
Dates accepted: YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY, YYYYMMDD.
Corporate actions headers: `symbol,ex_date,action_type,value` (optional `currency`).

## Limitations
CSV ingestion does not fetch exchange data, adjust prices for corporate actions, or certify data quality. `adjusted=true` is a user assertion, not an adjustment performed by AETHER. Existing SQLite databases receive additive tables through SQLAlchemy `create_all`; production schema evolution should use Alembic migrations. Licensed NSE/BSE feeds, entitlements, exchange agreements and broker connectivity remain separate integrations.
