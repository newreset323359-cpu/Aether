import numpy as np
from app.engines.garch import fit_garch11, fit_egarch11
from app.engines.hmm import fit_gaussian_hmm
from app.engines.monte_carlo import simulate_portfolio
from app.engines.implied_vol import implied_volatility
from app.engines.optimization import risk_parity_weights

def sample_returns():
    rng=np.random.default_rng(4)
    return rng.normal(.0002,.01,180).tolist()

def test_garch():
    x=fit_garch11(sample_returns()); assert x["next_variance_forecast"]>0
def test_egarch():
    x=fit_egarch11(sample_returns()); assert x["next_variance_forecast"]>0
def test_hmm():
    x=fit_gaussian_hmm(sample_returns()); assert len(x["state_means"])==2
def test_mc():
    x=simulate_portfolio(100000,[.5,.5],[.0002,.0001],[[.0001,0],[0,.0002]],horizon_days=10,simulations=500)
    assert x["mean_terminal_value"]>0
def test_iv():
    from app.engines.options import black_scholes
    p=black_scholes(100,100,1,.04,.25)["price"]
    x=implied_volatility(p,100,100,1,.04)
    assert abs(x["implied_volatility"]-.25)<1e-4
def test_risk_parity():
    x=risk_parity_weights([[.04,0],[0,.01]])
    assert abs(sum(x["weights"])-1)<1e-6
