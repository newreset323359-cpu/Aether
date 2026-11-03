"""Gaussian GARCH(1,1) and EGARCH(1,1) maximum-likelihood estimators."""
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

def _series(returns):
    x=np.asarray(returns,dtype=float)
    x=x[np.isfinite(x)]
    if x.size<30: raise ValueError("At least 30 finite return observations are required")
    if np.max(np.abs(x))>2: raise ValueError("Supply decimal returns (e.g. 0.01 for 1%)")
    return x

def fit_garch11(returns):
    x=_series(returns); mu0=float(x.mean()); v=max(float(x.var()),1e-8)
    def unpack(p):
        mu=p[0]; omega=np.exp(p[1]); a=expit(p[2]); b=(1-a)*expit(p[3])*.999
        return mu,omega,a,b
    def objective(p):
        mu,omega,a,b=unpack(p); e=x-mu; h=np.empty_like(x); h[0]=v
        for t in range(1,len(x)): h[t]=omega+a*e[t-1]**2+b*h[t-1]
        h=np.maximum(h,1e-12)
        return .5*np.sum(np.log(2*np.pi)+np.log(h)+e**2/h)
    p0=np.array([mu0,np.log(v*.05),-2.2,2.5])
    res=minimize(objective,p0,method="L-BFGS-B",options={"maxiter":3000})
    if not res.success and not np.isfinite(res.fun): raise ValueError("GARCH optimizer failed")
    mu,omega,a,b=unpack(res.x); e=x-mu; h=np.empty_like(x); h[0]=v
    for t in range(1,len(x)): h[t]=omega+a*e[t-1]**2+b*h[t-1]
    persistence=a+b
    forecast=omega+(a+b)*h[-1]
    long_run=omega/(1-persistence) if persistence<1 else None
    return {"model":"GARCH(1,1)","mu":float(mu),"omega":float(omega),"alpha":float(a),"beta":float(b),
            "persistence":float(persistence),"last_conditional_variance":float(h[-1]),
            "next_variance_forecast":float(forecast),"long_run_variance":None if long_run is None else float(long_run),
            "converged":bool(res.success),"negative_log_likelihood":float(res.fun),"observations":int(len(x))}

def fit_egarch11(returns):
    x=_series(returns); mu0=float(x.mean()); z=x-mu0
    logv0=np.log(max(float(x.var()),1e-8))
    # log(h_t)=omega+beta*log(h[t-1])+alpha*(|z[t-1]/sqrt(h)|-E|N|)+gamma*z[t-1]/sqrt(h)
    def unpack(p): return p[0],p[1],expit(p[2])*.999,p[3]
    def calc(p):
        mu,omega,beta,alpha=unpack(p); gamma=p[4]; e=x-mu
        lh=np.empty(len(x)); lh[0]=logv0
        for t in range(1,len(x)):
            prev=e[t-1]/np.sqrt(np.exp(np.clip(lh[t-1],-30,30)))
            lh[t]=omega+beta*lh[t-1]+alpha*(abs(prev)-np.sqrt(2/np.pi))+gamma*prev
        h=np.exp(np.clip(lh,-30,30))
        nll=.5*np.sum(np.log(2*np.pi)+np.log(h)+e**2/h)
        return nll,lh
    def obj(p): return calc(p)[0]
    p0=np.array([mu0,logv0*.05,2.0,.1,0.0])
    res=minimize(obj,p0,method="L-BFGS-B",options={"maxiter":3000})
    mu,omega,beta,alpha=unpack(res.x); gamma=res.x[4]
    nll,lh=calc(res.x); next_logv=omega+beta*lh[-1]+alpha*(abs((x[-1]-mu)/np.sqrt(np.exp(lh[-1])))-np.sqrt(2/np.pi))+gamma*((x[-1]-mu)/np.sqrt(np.exp(lh[-1])))
    return {"model":"EGARCH(1,1)","mu":float(mu),"omega":float(omega),"beta":float(beta),
            "alpha":float(alpha),"gamma":float(gamma),"last_conditional_variance":float(np.exp(lh[-1])),
            "next_variance_forecast":float(np.exp(np.clip(next_logv,-30,30))),
            "converged":bool(res.success),"negative_log_likelihood":float(nll),"observations":int(len(x))}
