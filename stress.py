"""Correlated historical-style factor shock stress testing."""
import numpy as np

def portfolio_stress(weights, factor_exposures, factor_shocks, portfolio_value=1.0, asset_names=None):
    w=np.asarray(weights,dtype=float); b=np.asarray(factor_exposures,dtype=float); s=np.asarray(factor_shocks,dtype=float)
    if b.ndim!=2 or b.shape[0]!=len(w) or b.shape[1]!=len(s): raise ValueError("exposure dimensions mismatch")
    if not np.isclose(w.sum(),1): raise ValueError("weights must sum to one")
    if portfolio_value<=0: raise ValueError("portfolio_value must be positive")
    asset_r=b@s; port_r=float(w@asset_r)
    names=asset_names or [f"asset_{i+1}" for i in range(len(w))]
    return {"scenario_return":port_r,"scenario_pnl":port_r*portfolio_value,
            "asset_returns":{n:float(v) for n,v in zip(names,asset_r)},
            "factor_shocks":s.tolist(),"portfolio_value":portfolio_value}

def historical_scenario_library():
    return [
      {"name":"Equity selloff","shocks":{"market":-0.10,"rates":0.0,"fx":0.0}},
      {"name":"Rate shock","shocks":{"market":-0.02,"rates":0.01,"fx":0.0}},
      {"name":"INR depreciation","shocks":{"market":-0.03,"rates":0.0,"fx":0.05}},
      {"name":"Combined liquidity shock","shocks":{"market":-0.15,"rates":0.015,"fx":0.08}}
    ]
