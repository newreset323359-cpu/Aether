"""Expanding-window walk-forward portfolio strategy comparison."""
import numpy as np

def walk_forward(asset_returns, strategies, train_window=60, test_window=20, transaction_cost_bps=10):
    r=np.asarray(asset_returns,dtype=float)
    if r.ndim!=2 or not np.isfinite(r).all() or np.any(r<=-1): raise ValueError("asset_returns must be finite periods x assets decimal returns")
    if train_window<10 or test_window<1 or r.shape[0] <= train_window: raise ValueError("invalid windows or insufficient observations")
    n=r.shape[1]; output={}
    for name,weights in strategies.items():
        w=np.asarray(weights,dtype=float)
        if w.shape!=(n,) or not np.isclose(w.sum(),1): raise ValueError(f"{name}: weights must match assets and sum to one")
        nav=1.0; series=[]; periods=[]
        start=train_window
        while start<r.shape[0]:
            end=min(start+test_window,r.shape[0])
            # Static strategy weights are applied only to the held-out segment.
            segment=r[start:end]@w
            cost=transaction_cost_bps/10000 * .5*np.abs(w).sum()
            nav*=max(0,1-cost)
            for val in segment:
                nav*=1+float(val); series.append(nav); periods.append(float(val))
            start=end
        a=np.asarray(series); peak=np.maximum.accumulate(np.r_[1.0,a])[1:]
        output[name]={"out_of_sample_periods":len(series),"total_return":float(nav-1),
                      "annualized_return":float(nav**(252/len(series))-1) if series else 0.0,
                      "annualized_volatility":float(np.std(periods,ddof=1)*np.sqrt(252)) if len(periods)>1 else 0.0,
                      "max_drawdown":float((a/peak-1).min()) if len(a) else 0.0,
                      "nav_series":series}
    return {"method":"expanding_window_out_of_sample_static_weights","train_window":train_window,
            "test_window":test_window,"transaction_cost_bps":transaction_cost_bps,"strategies":output,
            "note":"Weights are supplied ex ante; this function does not train a strategy inside each window."}
