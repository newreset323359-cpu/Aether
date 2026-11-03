# AETHER v0.8 — Performance & Risk Intelligence

## New capabilities
- Daily portfolio NAV reconstruction from the portfolio transaction/cash ledgers and imported daily OHLCV closes.
- Daily time-weighted return (TWR), chain-linked after treating dated external cash flows as end-of-day flows.
- Annualized money-weighted return (XIRR) using external deposits/withdrawals and terminal NAV.
- Benchmark-relative cumulative active return, tracking error and information ratio when a benchmark is assigned and benchmark bars are imported.
- Sector and asset-class market-value exposure attribution, with optional symbol-to-sector JSON overrides.
- Annualized volatility, Sharpe, Sortino, maximum drawdown, CAGR and Calmar ratios.
- Risk dashboard with transparent threshold flags.

## API additions
- `GET /api/v1/portfolios/{id}/performance/nav`
- `GET /api/v1/portfolios/{id}/performance/analytics`
- `GET /api/v1/portfolios/{id}/performance/attribution`
- `POST /api/v1/performance/metrics`
- `POST /api/v1/performance/xirr`
- `GET /api/v1/risk/dashboard/{id}`

## Methodology and limitations
- Annualization defaults to 252 trading days; callers can choose another period count for metric endpoints.
- NAV uses imported daily close bars, the last available close on or before each date, and recorded ledger cash. Rows with any unpriced open holding are omitted.
- TWR assumes external cash flows occur at end of day. Exact intraday flow timing is not available.
- XIRR uses actual calendar days and a numerical root solver.
- Benchmark relative statistics require matched portfolio NAV dates and imported benchmark bars.
- Attribution is exposure attribution, not security/sector return contribution. True contribution requires time-varying holdings weights and dated security/sector returns.
- No FX translation, derivatives valuation/margin, accrued interest, tax-lot accounting, broker reconciliation, or live market data. Imported prices and user-entered ledger records remain the source of truth.
- Sharpe/Sortino/Calmar are historical descriptive statistics, not forecasts or investment advice.
