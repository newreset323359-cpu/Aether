import math
import pytest
from app.engines.performance import xirr, performance_metrics, relative_metrics, attribution

def test_xirr_one_year():
    assert xirr([-100,110],["2024-01-01","2025-01-01"]) == pytest.approx((1.10**(365/366))-1,abs=2e-6)

def test_metrics_basic():
    m=performance_metrics([.01,-.005,.012,-.003,.004,.006],periods_per_year=252)
    assert m["observations"]==6
    assert m["annualized_volatility"]>0
    assert m["max_drawdown"]<0
    assert m["sharpe_ratio"] is not None

def test_relative_metrics():
    r=relative_metrics([.02,.01,-.01],[.01,.01,-.02])
    assert r["tracking_error"]>0
    assert r["information_ratio"] is not None

def test_attribution_sums_to_one():
    a=attribution([{"symbol":"AAA","market_value":60,"asset_class":"EQUITY"},
                   {"symbol":"BBB","market_value":40,"asset_class":"ETF"}],
                  {"AAA":"IT","BBB":"BANKS"})
    assert sum(x["weight"] for x in a["sector_exposure"])==pytest.approx(1)
    assert sum(x["weight"] for x in a["asset_exposure"])==pytest.approx(1)

def test_invalid_xirr():
    with pytest.raises(ValueError):
        xirr([100,110],["2024-01-01","2025-01-01"])
