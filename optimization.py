"""Risk parity and Black-Litterman posterior expected returns."""
import numpy as np

def risk_parity_weights(covariance, max_iter=10000, tol=1e-10):
    cov=np.asarray(covariance,dtype=float); n=cov.shape[0]
    if cov.shape!=(n,n) or n<1: raise ValueError("covariance must be square")
    if np.linalg.eigvalsh((cov+cov.T)/2).min()<=0: raise ValueError("covariance must be positive definite")
    w=np.ones(n)/n
    for _ in range(max_iter):
        vol=np.sqrt(w@cov@w); mrc=cov@w/vol; rc=w*mrc
        target=vol/n
        grad=rc-target
        w*=np.exp(-.05*grad/(np.abs(rc).mean()+1e-12))
        w=np.maximum(w,1e-12);w/=w.sum()
        if np.max(np.abs(rc-target))<tol:break
    return {"weights":w.tolist(),"risk_contributions":(w*(cov@w)/np.sqrt(w@cov@w)).tolist(),"iterations":_+1}

def black_litterman_prior(covariance, market_weights, risk_aversion=2.5, tau=.05,
                          pick_matrix=None, views=None, view_uncertainty=None):
    cov=np.asarray(covariance,dtype=float); w=np.asarray(market_weights,dtype=float)
    if cov.shape!=(len(w),len(w)) or not np.isclose(w.sum(),1): raise ValueError("invalid covariance or market weights")
    pi=risk_aversion*cov@w
    if pick_matrix is None or views is None:
        return {"implied_equilibrium_returns":pi.tolist(),"posterior_returns":pi.tolist(),"views_applied":False}
    P=np.asarray(pick_matrix,dtype=float); Q=np.asarray(views,dtype=float).reshape(-1)
    if P.shape[1]!=len(w) or P.shape[0]!=len(Q): raise ValueError("view dimensions mismatch")
    omega=np.asarray(view_uncertainty,dtype=float) if view_uncertainty is not None else np.diag(np.diag(P@(tau*cov)@P.T))
    middle=np.linalg.inv(P@(tau*cov)@P.T+omega)
    post=np.linalg.inv(np.linalg.inv(tau*cov)+P.T@np.linalg.inv(omega)@P)@(np.linalg.inv(tau*cov)@pi+P.T@np.linalg.inv(omega)@Q)
    return {"implied_equilibrium_returns":pi.tolist(),"posterior_returns":post.tolist(),"views_applied":True}
