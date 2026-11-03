import numpy as np
import pytest
from app.engines.adaptive import adaptive_signal, detect_regime, validate_walk_forward


def _bars(n=360, seed=11):
    rng=np.random.default_rng(seed)
    rets=rng.normal(0.0005,0.012,n)
    close=100*np.cumprod(1+rets)
    high=close*(1+rng.uniform(0.001,0.015,n))
    low=close*(1-rng.uniform(0.001,0.015,n))
    vol=rng.integers(100000,500000,n).astype(float)
    return close,high,low,vol


def test_signal_has_explainable_components_and_no_probability_claim():
    c,h,l,v=_bars()
    out=adaptive_signal(c,h,l,v,min_confidence=0.0)
    assert out["action"] in {"BUY","SHORT_BIAS","NO_TRADE"}
    assert set(out["component_votes"]) == {"trend","momentum","breakout","mean_reversion"}
    assert "NOT a calibrated probability" in out["caveat"]


def test_no_short_mode_never_returns_short():
    c,h,l,v=_bars()
    out=adaptive_signal(c,h,l,v,min_confidence=0.0,allow_short=False)
    assert out["direction"] >= 0


def test_walk_forward_is_strict_and_reports_costs_and_limits():
    c,h,l,v=_bars()
    out=validate_walk_forward(c,h,l,v,train_window=120,bootstrap_iterations=100)
    assert out["method"] == "strict_chronological_one_step_ahead_walk_forward"
    assert out["out_of_sample_observations"] == len(c)-120
    assert out["strategy"]["observations"] == len(c)-120
    assert out["bootstrap"]["available"]
    assert out["assumptions"]["short_borrow_cost_included"] is False
    assert "no future bars" in out["limitations"][0]


def test_walk_forward_rejects_insufficient_history():
    with pytest.raises(ValueError):
        validate_walk_forward(np.linspace(100,120,100),train_window=80)
