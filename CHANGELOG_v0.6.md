# AETHER v0.6 — Institutional Portfolio Management

## Added
- NSE/BSE instrument-master CSV import with validation and upsert by symbol + exchange.
- Searchable instrument reference API with ISIN, segment, type, lot size and tick size.
- Configurable benchmark registry and per-portfolio benchmark assignment.
- Portfolio transaction ledger (BUY/SELL), fees and trade dates; rejects sells beyond recorded net quantity.
- Holdings aggregation with weighted average cost, realized/unrealized P&L and valuation status.
- Benchmark total-return calculation from imported daily benchmark bars.
- Audit events for reference imports and recorded trades.

## Templates
- `samples/instrument_master_template.csv`
- `samples/benchmark_bars_template.csv`

## Limitations
Instrument master and benchmark values are user-supplied. No NSE/BSE directory is fetched. Benchmark return is price return over the available imported series, not total return (dividends), and is not annualized. Holdings valuation uses the latest imported daily close and marks missing prices as unpriced. Average-cost accounting is used; tax lots, FIFO/LIFO, corporate-action processing, settlement, cash ledger, fees/taxes, FX, derivatives margin and live broker execution are not implemented. This release adds tables using SQLAlchemy `create_all`; production deployments need Alembic migrations and access controls.
\n## Verification\n- 23 automated tests passed.\n- API smoke test passed: portfolio create, instrument import, benchmark create/assignment, BUY transaction and holdings retrieval; oversell correctly rejected with HTTP 422.\n