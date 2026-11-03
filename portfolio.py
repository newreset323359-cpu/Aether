"""Portfolio valuation, weights and basic optimization helpers."""
import numpy as np

def portfolio_summary(positions):
    # positions: list of {symbol, quantity, price, cost_price}
    values=np.array([p["quantity"]*p["price"] for p in positions],dtype=float)
    costs=np.array([p["quantity"]*p.get("cost_price",p["price"]) for p in positions],dtype=float)
    total=float(values.sum())
    rows=[]
    for p,v,c in zip(positions,values,costs):
        rows.append({"symbol":p["symbol"],"market_value":float(v),"weight":float(v/total) if total else 0,
                     "unrealized_pnl":float(v-c)})
    return {"market_value":total,"cost_value":float(costs.sum()),"unrealized_pnl":float((values-costs).sum()),"positions":rows}

def equal_weight(n):
    if n<1: raise ValueError("n must be positive")
    return [1.0/n]*n

def mean_variance_weights(expected_returns, covariance, risk_aversion=4.0, long_only=True, iterations=4000):
    mu=np.asarray(expected_returns,dtype=float); cov=np.asarray(covariance,dtype=float)
    n=mu.size
    if cov.shape!=(n,n): raise ValueError("covariance shape mismatch")
    if risk_aversion<=0: raise ValueError("risk_aversion must be positive")
    # Projected gradient ascent on mu'w - lambda/2*w'Cov*w, simplex constraints.
    w=np.ones(n)/n
    eig=max(float(np.linalg.eigvalsh((cov+cov.T)/2).max()),1e-8)
    step=1/(risk_aversion*eig+1e-8)
    for _ in range(iterations):
        grad=mu-risk_aversion@cov@w if False else mu-risk_aversion*(cov@w)
        z=w+step*grad
        if long_only:
            u=np.sort(z)[::-1]; cssv=np.cumsum(u)-1
            rho=np.where(u-cssv/(np.arange(n)+1)>0)[0][-1]
            theta=cssv[rho]/(rho+1); w=np.maximum(z-theta,0)
        else:
            w=z/z.sum()
    return w.tolist()
