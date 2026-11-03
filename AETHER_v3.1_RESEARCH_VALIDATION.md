# AETHER v3.1 — Historical Market Intelligence & Strategy Validation

## What changed
- Added validated multi-symbol OHLCV CSV import with duplicate, finite-value, positive-price and OHLC-range checks. Data provenance explicitly marks imports as user CSV, not live feeds; corporate-action adjustment, timezone and survivorship bias are not inferred.
- Added transparent India-segment cost estimator. All tax, exchange, brokerage, GST, stamp, slippage and impact rates are explicit user-supplied decimal rates; no unverified statutory defaults are embedded.
- Added long-only cash-equity close-to-close simulation with prior-close signal timing, capital, turnover events, exposure, drawdown, Sharpe, win rate and profit factor. Costs are supplied per side as a fraction, not guessed.
- Added contract-level futures gross/net P&L using explicit entry/exit, lot size, lots, direction and user-supplied total costs. Margin is deliberately not inferred. This is not an options-pricing or expiry simulator.
- Added conservative research gate. It can return NO_GO or RESEARCH_REVIEW; it never enables live trading.
- Resolved duplicate API route: old generic factor walk-forward is now `/api/v1/research/legacy-walk-forward`; v3.0 adaptive walk-forward retains `/api/v1/research/walk-forward`.
- API version updated to 3.1.0.

## Endpoints
- `POST /api/v1/research/v31/import-csv` body: `{"csv_text":"date,symbol,open,high,low,close,volume\n..."}`
- `POST /api/v1/research/v31/estimate-costs` body: notional, side, segment (`CASH_DELIVERY`, `CASH_INTRADAY`, `FUTURES`, `OPTIONS`), rates. Rate values are decimals; bps fields are basis points.
- `POST /api/v1/research/v31/cash-backtest` body: closes, signals (0/1, length n-1), capital, costs_per_side (fraction).
- `POST /api/v1/research/v31/futures-pnl` body: entry_price, exit_price, lot_size, lots, direction, entry_cost, exit_cost.
- `POST /api/v1/research/v31/gate` body: metrics, optional min_trades and max_drawdown_limit.

## Important boundaries
- No licensed NSE/BSE feed is connected. Upload actual licensed historical data; do not mistake sample/template files for real observations.
- F&O engine currently computes a supplied futures contract P&L; it does not yet model options Greeks, volatility surface, expiry settlement, exercise/assignment, lot/margin changes, spread legs or intraday margin.
- Cost estimates are only as accurate as the rates supplied. Confirm current broker contract notes and applicable official charges.
- No nested parameter tuning, portfolio-level point-in-time universe, purged/embargoed CV or multi-symbol capital allocation is claimed by this release. Those require a dedicated next validation phase.
- Paper-trade for at least 8–12 weeks after robust out-of-sample research, with reconciliation of every simulated fill.
- Groww integration is not changed. All live-trading flags remain OFF. This release is not deployed and has not been tested against a live Groww account.

## Test commands
`cd backend && pytest -q`
`python -m compileall -q backend/app`
