"""Simple long-only, periodic rebalanced backtest with explicit cost assumptions."""
import numpy as np

def run_backtest(asset_returns, weights, transaction_cost_bps=10, rebalance_every=1):
    r=np.asarray(asset_returns,dtype=float); w=np.asarray(weights,dtype=float)
    if r.ndim!=2 or r.shape[1]!=w.size: raise ValueError("returns must be periods x assets")
    if np.any(~np.isfinite(r)) or np.any(r<=-1): raise ValueError("invalid return series")
    if not np.isclose(w.sum(),1): raise ValueError("weights must sum to 1")
    if rebalance_every<1: raise ValueError("rebalance_every must be >=1")
    nav=1.0; current=w.copy(); series=[]; turnover_total=0
    for i,row in enumerate(r):
        if i%rebalance_every==0:
            turnover=float(np.abs(current-w).sum()/2)
            nav*=max(0,1-turnover*transaction_cost_bps/10000)
            turnover_total+=turnover
            current=w.copy()
        pr=float(current@row)
        nav*=1+pr
        current=current*(1+row); current=current/current.sum()
        series.append(nav)
    arr=np.asarray(series)
    peak=np.maximum.accumulate(np.r_[1.0,arr])[1:]
    return {"periods":len(series),"final_nav":float(nav),"total_return":float(nav-1),
            "max_drawdown":float((arr/peak-1).min()),"turnover_proxy":float(turnover_total),
            "nav_series":arr.tolist(),"assumptions":{"transaction_cost_bps":transaction_cost_bps,"rebalance_every":rebalance_every}}
