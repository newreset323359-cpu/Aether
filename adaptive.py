"""AETHER v3.0 adaptive ensemble research engine.

Research-only: produces signals and out-of-sample diagnostics. It never places orders.
Inputs are chronological, adjusted daily OHLCV bars. All thresholds are explicit.
"""
from __future__ import annotations
import math
import numpy as np


def _arr(values, name, minimum=2):
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or x.size < minimum or not np.isfinite(x).all():
        raise ValueError(f"{name} must be a finite 1-D array with at least {minimum} values")
    return x


def _ema(x, span):
    alpha = 2.0 / (span + 1.0)
    out = np.empty_like(x, dtype=float)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = alpha * x[i] + (1-alpha) * out[i-1]
    return out


def detect_regime(closes):
    c = _arr(closes, "closes", 60)
    r = np.diff(np.log(c))
    vol20 = float(np.std(r[-20:], ddof=1) * math.sqrt(252))
    vol60 = float(np.std(r[-60:], ddof=1) * math.sqrt(252))
    fast = float(_ema(c, 20)[-1])
    slow = float(_ema(c, 50)[-1])
    slope = float((_ema(c, 20)[-1] / _ema(c, 20)[-6]) - 1.0)
    if vol20 > max(0.35, vol60 * 1.6):
        regime = "HIGH_VOLATILITY"
    elif fast > slow and slope > 0.002:
        regime = "BULL_TREND"
    elif fast < slow and slope < -0.002:
        regime = "BEAR_TREND"
    else:
        regime = "SIDEWAYS"
    return {"regime": regime, "annualized_volatility_20d": vol20,
            "annualized_volatility_60d": vol60, "ema20": fast, "ema50": slow,
            "ema20_slope_5d": slope}


def adaptive_signal(closes, highs=None, lows=None, volumes=None,
                    min_confidence=0.60, allow_short=True):
    """Return ensemble direction, confidence and auditable component votes."""
    c = _arr(closes, "closes", 60)
    if np.any(c <= 0):
        raise ValueError("closes must be positive")
    h = _arr(highs, "highs", 60) if highs is not None else c
    lo = _arr(lows, "lows", 60) if lows is not None else c
    v = _arr(volumes, "volumes", 60) if volumes is not None else np.ones_like(c)
    if not (len(h) == len(lo) == len(v) == len(c)):
        raise ValueError("OHLCV arrays must have equal lengths")
    if np.any(h < c) or np.any(lo > c) or np.any(h < lo) or np.any(v < 0):
        raise ValueError("invalid OHLCV values")
    regime = detect_regime(c)
    r = np.diff(np.log(c))
    ema20, ema50 = _ema(c, 20), _ema(c, 50)
    trend_strength = (ema20[-1] / ema50[-1] - 1.0)
    mom20 = c[-1] / c[-21] - 1.0
    prior_high = float(np.max(h[-21:-1]))
    prior_low = float(np.min(lo[-21:-1]))
    breakout = 1 if c[-1] > prior_high else (-1 if c[-1] < prior_low else 0)
    vol_base = float(np.mean(v[-21:-1]))
    volume_ratio = float(v[-1] / vol_base) if vol_base > 0 else 1.0
    vol_confirm = volume_ratio >= 1.15
    # Robust mean-reversion z-score using recent price deviations from a 20d mean.
    recent = c[-20:]
    mean20 = float(np.mean(recent))
    sd20 = float(np.std(recent, ddof=1))
    zscore = float((c[-1] - mean20) / sd20) if sd20 > 0 else 0.0
    votes = {
        "trend": 1 if trend_strength > 0.002 else (-1 if trend_strength < -0.002 else 0),
        "momentum": 1 if mom20 > 0.015 else (-1 if mom20 < -0.015 else 0),
        "breakout": breakout,
        "mean_reversion": -1 if zscore > 1.5 else (1 if zscore < -1.5 else 0),
    }
    # Regime-aware weighting: trend-following dominates directional regimes;
    # mean reversion receives more weight in sideways markets.
    if regime["regime"] in ("BULL_TREND", "BEAR_TREND"):
        weights = {"trend": 0.35, "momentum": 0.30, "breakout": 0.25, "mean_reversion": 0.10}
    elif regime["regime"] == "SIDEWAYS":
        weights = {"trend": 0.15, "momentum": 0.15, "breakout": 0.15, "mean_reversion": 0.55}
    else:
        weights = {"trend": 0.25, "momentum": 0.20, "breakout": 0.20, "mean_reversion": 0.35}
    score = sum(weights[k] * votes[k] for k in votes)
    if vol_confirm:
        score += 0.05 * (1 if score > 0 else (-1 if score < 0 else 0))
    direction = 1 if score > 0 else (-1 if score < 0 else 0)
    confidence = min(0.99, abs(score) * 0.90 + (0.05 if vol_confirm else 0.0))
    if regime["regime"] == "HIGH_VOLATILITY":
        confidence *= 0.80
    if not allow_short and direction < 0:
        direction = 0
    action = "BUY" if direction > 0 else ("SHORT_BIAS" if direction < 0 else "NO_TRADE")
    if confidence < min_confidence:
        direction, action = 0, "NO_TRADE"
    return {
        "action": action, "direction": direction, "confidence": round(float(confidence), 4),
        "threshold": float(min_confidence), "score": round(float(score), 4),
        "regime": regime, "component_votes": votes, "component_weights": weights,
        "features": {"momentum_20d": float(mom20), "trend_strength": float(trend_strength),
                     "breakout_direction": int(breakout), "volume_ratio": volume_ratio,
                     "volume_confirmed": bool(vol_confirm), "mean_reversion_zscore": zscore},
        "research_only": True,
        "caveat": "Confidence is a heuristic ensemble agreement score, NOT a calibrated probability of profit."
    }


def _metrics(x, positions, cost_bps):
    x = np.asarray(x, dtype=float)
    p = np.asarray(positions, dtype=float)
    turnover = np.abs(np.diff(np.r_[0.0, p]))
    net = p * x - turnover * (cost_bps / 10000.0)
    nav = np.cumprod(1.0 + net)
    peaks = np.maximum.accumulate(np.r_[1.0, nav])[1:]
    dd = nav / peaks - 1.0
    n = len(net)
    std = float(np.std(net, ddof=1)) if n > 1 else 0.0
    downside = net[net < 0]
    gross_profit = float(net[net > 0].sum())
    gross_loss = float(-net[net < 0].sum())
    trade_changes = np.flatnonzero(np.diff(np.r_[0, p]) != 0)
    trades = int(len(trade_changes))
    return {
        "observations": n, "trades_entry_or_flip": trades,
        "total_return_net": float(nav[-1] - 1.0),
        "annualized_return_net": float(nav[-1] ** (252.0/n) - 1.0) if nav[-1] > 0 else -1.0,
        "annualized_volatility": float(std * math.sqrt(252)),
        "sharpe_zero_rf": float(np.mean(net) / std * math.sqrt(252)) if std > 0 else 0.0,
        "sortino_zero_target": float(np.mean(net) / (np.std(downside, ddof=1) * math.sqrt(252)) * math.sqrt(252)) if len(downside) > 1 and np.std(downside, ddof=1) > 0 else 0.0,
        "max_drawdown": float(dd.min()),
        "win_rate_daily_active": float(np.mean(net[p != 0] > 0)) if np.any(p != 0) else 0.0,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else (None if gross_profit > 0 else 0.0),
        "average_daily_net_return": float(np.mean(net)),
        "turnover_units": float(turnover.sum()),
        "net_daily_returns": net.tolist(),
        "nav": nav.tolist(),
    }


def _block_bootstrap_ci(daily_returns, iterations=1000, block=5, seed=17):
    x = np.asarray(daily_returns, dtype=float)
    n = len(x)
    if n < 30:
        return {"available": False, "reason": "At least 30 out-of-sample observations required"}
    rng = np.random.default_rng(seed)
    vals = np.empty(iterations)
    blocks_needed = int(math.ceil(n / block))
    for j in range(iterations):
        starts = rng.integers(0, n, size=blocks_needed)
        sample = np.concatenate([x[(s + np.arange(block)) % n] for s in starts])[:n]
        vals[j] = np.prod(1.0 + sample) - 1.0
    return {"available": True, "method": "circular_moving_block_bootstrap",
            "iterations": iterations, "block_length": block,
            "total_return_95pct_interval": [float(np.quantile(vals, .025)), float(np.quantile(vals, .975))],
            "probability_positive_bootstrap": float(np.mean(vals > 0)),
            "warning": "Bootstrap estimate is conditional on this sample and is not a guarantee or calibrated future probability."}


def validate_walk_forward(closes, highs=None, lows=None, volumes=None,
                          train_window=120, cost_bps_per_turnover=15.0,
                          min_confidence=0.60, allow_short=True,
                          bootstrap_iterations=1000):
    """Strict chronological one-step-ahead walk-forward; signal at t-1 earns t return."""
    c = _arr(closes, "closes", max(150, train_window + 2))
    if np.any(c <= 0):
        raise ValueError("closes must be positive")
    n = len(c)
    def optional(a, name, default):
        if a is None: return default
        q = _arr(a, name, n)
        if len(q) != n: raise ValueError(f"{name} length must match closes")
        return q
    h = optional(highs, "highs", c)
    lo = optional(lows, "lows", c)
    v = optional(volumes, "volumes", np.ones(n))
    if train_window < 60 or train_window >= n - 1:
        raise ValueError("train_window must be >=60 and less than observations-1")
    if cost_bps_per_turnover < 0 or not 0 <= min_confidence <= 1:
        raise ValueError("invalid cost or confidence threshold")
    positions, realized, dates_idx, regimes = [], [], [], []
    # At index t, only bars through t-1 are passed into signal generation.
    for t in range(train_window, n):
        sig = adaptive_signal(c[:t], h[:t], lo[:t], v[:t],
                              min_confidence=min_confidence, allow_short=allow_short)
        positions.append(sig["direction"])
        realized.append(float(c[t] / c[t-1] - 1.0))
        dates_idx.append(t)
        regimes.append(sig["regime"]["regime"])
    m = _metrics(realized, positions, cost_bps_per_turnover)
    active = int(np.count_nonzero(positions))
    benchmark = _metrics(realized, np.ones(len(realized)), cost_bps_per_turnover)
    ci = _block_bootstrap_ci(m["net_daily_returns"], iterations=max(100, min(int(bootstrap_iterations), 5000)))
    return {
        "method": "strict_chronological_one_step_ahead_walk_forward",
        "train_window_bars": train_window, "out_of_sample_observations": len(realized),
        "first_test_index": dates_idx[0], "last_test_index": dates_idx[-1],
        "strategy": {k:v for k,v in m.items() if k not in ("net_daily_returns", "nav")},
        "benchmark_buy_hold_with_same_cost_model": {k:v for k,v in benchmark.items() if k not in ("net_daily_returns", "nav")},
        "bootstrap": ci,
        "active_exposure_fraction": float(active / len(positions)),
        "regime_counts": {r: regimes.count(r) for r in sorted(set(regimes))},
        "assumptions": {"transaction_cost_bps_per_one_unit_turnover": cost_bps_per_turnover,
                        "shorts_enabled_in_research_simulation": bool(allow_short),
                        "short_borrow_cost_included": False, "financing_and_margin_costs_included": False,
                        "taxes_and_exchange_charges_must_be_added_or_refined_for_instrument": True},
        "limitations": [
            "Signals use only information available before each tested return; no future bars are passed to the signal.",
            "This is a research simulation, not a live execution model. It omits queue position, partial fills, market impact and broker rejections.",
            "Short exposure is theoretical unless separately enabled and permitted for the instrument; borrow, funding and margin costs are not modeled.",
            "Bootstrap probability is sample-conditional and must not be interpreted as a guaranteed probability of future profit.",
            "Use adjusted prices and a survivorship-bias-aware universe for portfolio-level conclusions."
        ],
        "research_only": True
    }
