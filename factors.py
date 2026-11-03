"""Factor analytics: OLS factor regression and cross-sectional factor exposure helpers."""
import numpy as np

def factor_regression(asset_returns, factor_returns, factor_names=None):
    y=np.asarray(asset_returns,dtype=float).reshape(-1)
    x=np.asarray(factor_returns,dtype=float)
    if x.ndim==1: x=x.reshape(-1,1)
    if x.shape[0]!=len(y) or len(y)<x.shape[1]+5: raise ValueError("Insufficient or mismatched observations")
    if not np.isfinite(x).all() or not np.isfinite(y).all(): raise ValueError("Returns must be finite")
    design=np.column_stack([np.ones(len(y)),x])
    beta=np.linalg.lstsq(design,y,rcond=None)[0]
    fitted=design@beta; resid=y-fitted
    ssr=float(resid@resid); sst=float(((y-y.mean())**2).sum())
    r2=1-ssr/sst if sst>0 else 0.0
    dof=len(y)-design.shape[1]
    sigma2=ssr/dof if dof>0 else float("nan")
    cov=sigma2*np.linalg.pinv(design.T@design)
    se=np.sqrt(np.maximum(np.diag(cov),0))
    names=factor_names or [f"factor_{i+1}" for i in range(x.shape[1])]
    if len(names)!=x.shape[1]: raise ValueError("factor_names length mismatch")
    return {"alpha_per_period":float(beta[0]),"factor_loadings":{n:float(v) for n,v in zip(names,beta[1:])},
            "standard_errors":{"alpha":float(se[0]),**{n:float(v) for n,v in zip(names,se[1:])}},
            "r_squared":float(r2),"observations":int(len(y)),"residual_volatility":float(np.sqrt(sigma2))}

def fama_french_style_regression(asset_returns, market, size, value, factor_names=None):
    return factor_regression(asset_returns,np.column_stack([market,size,value]),factor_names or ["market","size","value"])
