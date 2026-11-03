from app.engines.risk import historical_var_cvar, drawdown_stats
from app.engines.options import black_scholes
from app.engines.portfolio import equal_weight
from app.engines.backtest import run_backtest

def test_var():
    x=historical_var_cvar([.01,-.02,.005,-.03,.01],.8,100000)
    assert x["var_amount"]>0 and x["cvar_amount"]>=x["var_amount"]
def test_drawdown():
    assert drawdown_stats([.1,-.2])["max_drawdown"]<0
def test_option():
    x=black_scholes(100,100,1,.05,.2)
    assert x["price"]>0 and 0<x["delta"]<1
def test_weights():
    assert equal_weight(4)==[.25]*4
def test_backtest():
    x=run_backtest([[.01,.02],[-.01,0]],[.5,.5])
    assert len(x["nav_series"])==2
