# AETHER API v0.7

## Run
```bash
cd backend
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Interactive API documentation: `/docs`.

## New v0.3 quantitative modules
- `POST /api/v1/quant/garch` — Gaussian GARCH(1,1) MLE
- `POST /api/v1/quant/egarch` — EGARCH(1,1) MLE with asymmetric shock term
- `POST /api/v1/quant/hmm` — Gaussian HMM regime classification (2–4 states)
- `POST /api/v1/risk/monte-carlo` — multivariate normal portfolio simulation, terminal percentiles, loss VaR/CVaR
- `POST /api/v1/derivatives/implied-volatility` — Black-Scholes implied volatility inversion
- `POST /api/v1/portfolio/optimize/risk-parity` — iterative equal-risk-contribution allocation
- `POST /api/v1/portfolio/black-litterman` — equilibrium prior and optional investor views

All return series must be decimal periodic returns, not percentage numbers (1% = 0.01). GARCH/HMM require at least 30 observations. Monte Carlo expected returns and covariance must use the same periodic frequency, such as daily.

## Validation and limitations
These are research implementations, not production-validated investment models. GARCH/EGARCH use Gaussian likelihood; HMM is a compact univariate Gaussian model; Monte Carlo assumes multivariate-normal returns and does not capture fat tails, jumps or changing correlations. Black-Litterman requires carefully calibrated inputs and explicit view uncertainty. Validate with independent datasets, walk-forward tests, model diagnostics and governance before investment use.

The demo market-data provider remains synthetic. No licensed live NSE/BSE feed or broker execution is included.


## v0.4 additions
- `POST /api/v1/research/factor-regression` — OLS factor exposure, alpha, R² and standard errors.
- `POST /api/v1/research/fama-french-style` — three-factor regression helper (user-supplied factor returns).
- `POST /api/v1/research/walk-forward` — out-of-sample strategy evaluation on supplied fixed weights.
- `POST /api/v1/risk/stress` — portfolio stress from asset-factor exposures and factor shocks.
- `GET /api/v1/risk/stress/scenarios` — illustrative equity/rate/FX scenario library.
- `POST /api/v1/derivatives/iv-surface` — IV grid from option quotes.

Factor returns and asset returns must be aligned, same-frequency decimal returns. The walk-forward endpoint currently evaluates ex-ante supplied weights; it does not retrain or optimize weights in each training window. Scenario shocks and factor exposures are user-supplied. The options surface is an implied-volatility grid, not an arbitrage-free fitted surface.


## v0.5 market-data infrastructure
- `GET /api/v1/data/providers` — available demo/CSV/provider adapter status.
- `POST /api/v1/data/ingest/bars` — ingest OHLCV CSV as JSON `{ "csv_text": "...", "source": "vendor-or-file", "interval": "1d", "adjusted": false }`.
- `GET /api/v1/data/bars/{symbol}` — retrieve stored bars.
- `POST /api/v1/data/ingest/corporate-actions` — ingest corporate-action CSV as JSON `{ "csv_text": "...", "source": "..." }`.
- `GET /api/v1/data/corporate-actions/{symbol}` — retrieve events.
- `GET /api/v1/data/ingestions` — ingestion audit/provenance history.\n- `GET /api/v1/data/freshness?max_age_days=3` — calendar-day staleness report per symbol.

OHLCV headers: `symbol,date,open,high,low,close,volume`. Dates: YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY or YYYYMMDD. Corporate action headers: `symbol,ex_date,action_type,value` (optional `currency`). Duplicate symbol/date/interval bars are rejected rather than silently overwritten. Invalid rows are returned with reasons.

`adjusted=true` records the uploader's assertion; AETHER does not calculate adjusted prices. Data is not live unless a separately licensed provider is configured. The demo quote adapter remains synthetic. For production, add Alembic migrations, access controls, provider credentials via environment secrets, vendor entitlements, exchange calendar handling, corporate-action adjustment logic and independent reconciliation.


## v0.6 institutional portfolio and reference data
- `POST /api/v1/reference/instruments/import` — import NSE/BSE instrument master CSV (`symbol,exchange,name`; optional `isin,segment,instrument_type,lot_size,tick_size`).
- `GET /api/v1/reference/instruments?exchange=NSE&query=RELIANCE` — search imported reference data.
- `POST /api/v1/benchmarks` / `GET /api/v1/benchmarks` — configure benchmark symbols and names.
- `PUT /api/v1/portfolios/{id}/benchmark` — assign a benchmark.
- `POST /api/v1/portfolios/{id}/transactions` — record BUY/SELL with quantity, price, fees and ISO trade date.
- `GET /api/v1/portfolios/{id}/transactions` — transaction ledger.
- `GET /api/v1/portfolios/{id}/holdings` — average-cost holdings, realized/unrealized P&L and data coverage.
- `GET /api/v1/portfolios/{id}/benchmark-performance` — benchmark price return from imported daily bars.

Instrument and benchmark reference data are user-imported/configured. To calculate benchmark performance, import daily bars under the benchmark symbol using the v0.5 OHLCV ingestion route. This endpoint computes price return only; it does not include dividends or represent a live index feed. Holdings use weighted average cost and latest imported daily close; no tax-lot, settlement, cash, corporate-action or derivatives-margin accounting is implemented.


## v0.7 cash and portfolio analytics
- `POST /api/v1/portfolios/{id}/cash-entries` — record DEPOSIT, WITHDRAWAL, DIVIDEND, INTEREST, FEE, TAX or ADJUSTMENT.
- `GET /api/v1/portfolios/{id}/cash-ledger` — running cash balance by currency; BUY/SELL transactions create cash entries automatically.
- `GET /api/v1/portfolios/{id}/fifo-lots` — FIFO open lots and estimated realized P&L.
- `GET /api/v1/portfolios/{id}/exposure` — market-value positions, asset-type exposure, unpriced positions and top-five concentration.

Cash ledger begins at zero; enter opening cash as a DEPOSIT. FIFO includes buy fees in lot cost but displayed realized P&L excludes sell-side fees and taxes. This is not tax reporting or bank/broker reconciliation. Exposure is based on latest imported daily bars and excludes cash, derivatives, accrued income and unpriced positions.
