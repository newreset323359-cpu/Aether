import numpy as np
from app.engines.factors import factor_regression
from app.engines.walkforward import walk_forward
from app.engines.stress import portfolio_stress
from app.engines.options_surface import build_iv_surface
from app.engines.options import black_scholes

def test_factor_regression():
    x=np.linspace(-.02,.02,100); y=.001+1.2*x
    r=factor_regression(y,x,["market"])
    assert abs(r["factor_loadings"]["market"]-1.2)<1e-8
def test_walkforward():
    x=np.ones((100,2))*.001
    r=walk_forward(x,{"equal":[.5,.5]},train_window=60,test_window=20)
    assert r["strategies"]["equal"]["out_of_sample_periods"]==40
def test_stress():
    r=portfolio_stress([.5,.5],[[1,0],[.5,1]],[-.1,.02],1000)
    assert r["scenario_pnl"]<0
def test_surface():
    p=black_scholes(100,100,1,.03,.2)["price"]
    r=build_iv_surface([{"strike":100,"time_years":1,"market_price":p}],100,.03)
    assert abs(r["points"][0]["implied_volatility"]-.2)<1e-4
