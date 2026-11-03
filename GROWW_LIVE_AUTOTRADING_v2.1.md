# AETHER v2.1 — Groww connection and gated auto execution

## What this build adds
- Secure "Connect Groww API" endpoint. The user pastes a Groww-generated access token; AETHER encrypts it at rest using Fernet and a server-only key.
- Actual Groww order-create adapter using `POST /v1/order/create`.
- Live order history, live-arm/disarm endpoints and a server-side kill switch.
- Auto strategy watchlist/configuration API.
- Single-instance worker that fetches Groww historical candles and live quotes, evaluates the selected strategy, and may submit bounded entry/exit orders.
- Broker-native protective OCO orders for CASH/MIS and FNO/NRML; GTT stop orders for other product combinations supported by Groww.
- Per-order risk sizing: default 1% capital risk (₹500), max entry notional ₹12,500, max total gross exposure estimate ₹50,000, max 5 live orders/day and max daily submitted notional ₹50,000.
- Default product modes: CASH intraday MIS, CASH swing CNC, FNO intraday MIS, FNO swing NRML.

## Very important — not enabled by default
The following must all be true before the worker can send real orders:
1. `AETHER_LIVE_TRADING_ENABLED=true` server-side.
2. `AETHER_GROWW_ALGO_APPROVED=true` only after Groww confirms the account/API/algo setup and applicable exchange requirements.
3. `AETHER_AUTO_WORKER_ENABLED=true`.
4. The user has connected a valid Groww API access token and explicitly armed live trading in the AETHER UI/API.
5. Strategy configs are explicitly enabled.

All four server flags default false. No actual live order has been sent by creating this package.

## Groww "login" clarification
Groww's published API does not document a third-party OAuth login button. This build implements a secure Connect Groww API token flow. The user generates an API access token from Groww's Trading APIs page and enters it in AETHER over HTTPS. No Groww password, OTP or TOTP is collected. Groww access tokens expire daily at 06:00 IST, so a new token/reconnection may be required each day. API-key/secret daily approval flows are documented by Groww but are not stored by AETHER in this build.

## Setup
1. Install backend dependencies: `pip install -r requirements.txt`.
2. Generate a Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
3. Set `GROWW_TOKEN_ENCRYPTION_KEY` securely on the backend.
4. Deploy backend behind HTTPS with a fixed outbound static IP as required by the broker/exchange framework; configure the exact PWA CORS origin.
5. In Groww, activate the Trading API subscription and generate an API access token.
6. Sign into AETHER and use Connect Groww API. Token is encrypted in the backend database.
7. Ask Groww to confirm that your intended retail API algo use, client-direct API access, static IP mapping, order rate limits, and strategy registration/approval requirements are satisfied.
8. Only after written confirmation, configure the server-side flags. Then arm live trading with the exact confirmation phrase and enable a strategy.
9. Run exactly one worker process: `python -m app.autotrader_worker`.

## API routes
- `POST /api/v1/groww/connect`
- `POST /api/v1/groww/disconnect`
- `GET /api/v1/groww/connection`
- `POST /api/v1/groww/live/enable` (requires confirmation `I UNDERSTAND LIVE TRADING`)
- `POST /api/v1/groww/live/disable`
- `POST /api/v1/groww/orders`
- `GET /api/v1/groww/orders`
- `POST /api/v1/autotrader/strategies`
- `GET /api/v1/autotrader/strategies`
- `POST /api/v1/autotrader/strategies/{id}/enable`
- `POST /api/v1/autotrader/strategies/{id}/disable`
- `DELETE /api/v1/autotrader/strategies/{id}`
- `POST /api/v1/autotrader/worker/scan-once`

## Risk and operational limitations
- The ₹50,000 gross-exposure check is an estimate from Groww's CASH + FNO positions snapshot, not a broker-side guaranteed pre-trade margin check. The low-level manual `/groww/orders` endpoint uses stop_loss_price for risk validation but does not itself create a protective stop; use the automated strategy worker for its OCO/GTT workflow.
- Daily caps count submitted orders/notional, not realized P&L. A robust realized-loss circuit breaker needs tradebook/fill reconciliation and independent testing.
- Automated exits use a marketable LIMIT order; it can remain unfilled. The worker records the order and rechecks on the next scan; monitor the broker order book. Automated entries receive broker-native OCO/GTT protection after the position is visible, subject to Groww's product rules. Protection creation can fail and must be monitored.
- OCO/GTT support/product constraints are Groww-defined and may vary; verify with live test/sandbox or Groww support before enabling.
- Worker is single-instance only; do not run multiple copies. It scans at the configured interval and regular-session window. It is not a low-latency system.
- The current strategy rules are simple research heuristics, not validated profitable strategies. No profit is guaranteed.
- No multi-user redistribution of Groww data is intended; each user must use their own authorized broker credentials and data entitlements.
- Live execution is not certified, independently audited, or production-ready merely because the code is present.


## Live-mode safety checklist before first order
- Keep the PWA and API behind HTTPS.
- Keep the Groww access token encrypted on the backend; do not put it in localStorage or source control.
- Use a fixed public static IP and complete Groww's IP mapping/allowlisting steps if required.
- Obtain written confirmation from Groww that your account/API access and intended automation are permitted under the current retail-algo rules.
- Verify strategy/product/order types and OCO/GTT support for the exact instrument and segment.
- Run the worker with one process only; monitor logs and Groww's order book continuously.
- Begin with one liquid CASH instrument and the smallest permitted quantity. Do not enable FNO automation until contract symbol, lot size, expiry, margin and protection behavior have been checked.
- AETHER's code cannot certify regulatory compliance, profitability or order-fill behavior.
