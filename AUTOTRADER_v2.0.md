# AETHER AutoTrader v2.0 — Groww Edition

## Configured profile
- Virtual capital: INR 50,000 per authenticated AETHER user.
- Segments: NSE/BSE CASH and FNO.
- Styles: INTRADAY and SWING.
- Execution: PAPER ONLY. This release contains no Groww order-placement method or live-order route.

## Paper-trading guardrails
- Risk budget per new BUY: 1% of initial capital (₹500).
- Daily realized-loss lockout: 2% of initial capital (₹1,000); new BUYs blocked after breach.
- Maximum single paper position/order: 25% of initial capital (₹12,500).
- Maximum gross exposure: 100% of initial capital (₹50,000).
- F&O is long-only in this simulator; full contract notional is reserved, not exchange/broker margin.
- SELL can only reduce an existing long paper position.
- Default estimated transaction costs: 5 bps; slippage: 2.5 bps. These are configurable illustrative assumptions, not Groww's actual charges.
- Duplicate client order IDs are rejected.
- Each authenticated user has a separate paper account and order history.

## API endpoints
- `GET /api/v1/autotrader/config`
- `GET /api/v1/autotrader/summary`
- `GET /api/v1/autotrader/orders`
- `POST /api/v1/autotrader/orders`
- `POST /api/v1/autotrader/mark`
- `POST /api/v1/autotrader/reset?confirm=true`
- `POST /api/v1/autotrader/signals/evaluate`
- `GET /api/v1/groww/status`
- `POST /api/v1/groww/ltp` (read-only; requires backend `GROWW_ACCESS_TOKEN` and optional SDK)

## Groww read-only quote setup
1. Obtain Groww API access under your own account and ensure the applicable API subscription and entitlements are active.
2. Install the optional SDK in the backend virtual environment: `pip install growwapi`.
3. Set `GROWW_ACCESS_TOKEN` in the backend environment. Do not put it in the browser, PWA, source files, or chat.
4. Groww access tokens expire daily at 06:00 IST according to its current cURL docs; renew/rotate as required.
5. Obtain the correct `exchange_token` from Groww's instrument master. Then call `POST /api/v1/groww/ltp` with `{ "exchange":"NSE", "segment":"CASH", "exchange_token":"..." }`.
6. The LTP endpoint is read-only. It does not route orders and does not automatically mark paper positions.

## Start locally
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS/Termux: source .venv/bin/activate
pip install -r requirements.txt
pip install growwapi  # optional, only for Groww read-only LTP
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Open `/docs` to inspect the API. Configure the PWA backend URL in Institutional, bootstrap/login, then open AutoTrader.

## Important limitations
- No real Groww orders can be submitted by this build; the backend does not expose a broker order-placement endpoint.
- No automatic signal-to-order execution. Signal evaluation returns research-only BUY/HOLD/EXIT_OR_AVOID heuristics.
- No continuous feed worker, quote cache, automatic paper marking, intraday square-off, derivatives expiry settlement, short selling, leverage or broker margin calculation.
- No verified profitability. Backtests and paper fills do not predict future returns.
- Estimated costs/slippage are simplified. Replace with instrument-, segment- and order-specific actual charges before evaluating strategy profitability.
- Before any future live order feature, verify Groww API access, exchange/broker algo requirements, static IP requirements, risk controls and current SEBI/NSE rules.
