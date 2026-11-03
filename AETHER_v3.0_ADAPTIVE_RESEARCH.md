# AETHER v3.0 — Adaptive Quant Research

## Scope
Balanced research configuration for NSE/BSE cash and F&O instruments. v3.0 adds an explainable regime-aware ensemble and strict chronological one-step-ahead walk-forward validation. It is additive to v2.1; the Groww adapter and all v2.1 live-trading safeguards remain unchanged.

## New research endpoints
All endpoints require the existing AETHER API authentication.

### `POST /api/v1/research/adaptive-signal`
Request:
```json
{
  "closes": [100, 101, 99],
  "highs": [102, 102, 100],
  "lows": [99, 100, 98],
  "volumes": [1000, 1100, 1200],
  "min_confidence": 0.60,
  "allow_short": false
}
```
The example arrays above are illustrative only; at least 60 chronological observations are required. Returns market regime, component votes and weights, ensemble score, heuristic confidence and BUY/SHORT_BIAS/NO_TRADE action. `confidence` is NOT a calibrated probability of profit.

### `POST /api/v1/research/walk-forward`
Request:
```json
{
  "closes": [/* at least 150 chronological adjusted closes */],
  "highs": [/* optional, same length */],
  "lows": [/* optional, same length */],
  "volumes": [/* optional, same length */],
  "train_window": 120,
  "cost_bps_per_turnover": 15,
  "min_confidence": 0.60,
  "allow_short": false,
  "bootstrap_iterations": 1000
}
```
At each test date, the signal receives only bars strictly before the return being tested. Reports net-of-assumed-turnover-cost strategy metrics, a buy-and-hold comparison, exposure, regime counts and circular moving-block bootstrap interval.

## Model design
- Regime detector: EMA20/EMA50 relationship, EMA20 five-session slope and 20/60-session realized volatility.
- Ensemble: trend, 20-session momentum, 20-session breakout and mean-reversion z-score.
- Regime-aware weights: trend regimes emphasize trend/momentum/breakout; sideways regimes emphasize mean reversion; high-volatility regimes reduce confidence.
- Volume confirmation adds only a small score adjustment.
- Confidence threshold defaults to 0.60; uncertain or conflicting signals return NO_TRADE.
- `allow_short=false` suppresses negative signals, appropriate for cash-only evaluation.

## Important limitations
- This release does not claim improved profitability. The model is a transparent baseline requiring validation and tuning on licensed, adjusted, survivorship-bias-aware data.
- The ensemble confidence is a heuristic agreement score, not a probability calibration.
- Walk-forward is one-step-ahead, but it is a single-instrument signal simulation, not a portfolio optimizer.
- Cost is a simplified bps-per-unit-turnover assumption. Refine it per segment/instrument to include brokerage, STT, exchange transaction charges, GST, SEBI charges, stamp duty, slippage, impact, financing and taxes.
- Short-side results omit borrow availability/cost, funding, margin, expiry, lot sizing, and instrument-specific restrictions. Do not interpret synthetic short exposure as an executable F&O trade.
- Bootstrap interval is conditional on the observed out-of-sample sample and is not a future guarantee.
- It does not use live data, send orders, alter strategy configs, or connect the adaptive signal to the Groww worker.

## Live safeguards retained
All v2.1 live flags remain OFF by default:
`AETHER_LIVE_TRADING_ENABLED=false`
`AETHER_GROWW_ALGO_APPROVED=false`
`AETHER_AUTO_WORKER_ENABLED=false`

No v3.0 endpoint can arm live trading or place broker orders. Do not enable v2.1 live flags until Groww/API, exchange/SEBI compliance, static IP, deployment security and broker-side risk requirements are independently confirmed.

## Running tests
From `backend/`:
```bash
pip install -r requirements.txt
pytest -q
```
