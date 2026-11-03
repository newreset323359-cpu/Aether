"""AETHER v0.8 performance and risk analytics.
All returns are decimal fractions; daily NAV uses imported daily closes and ledger events.
"""
from datetime import date
import math
import numpy as np

def _dates(values):
    out=[]
    for v in values:
        try: out.append(date.fromisoformat(str(v)[:10]))
        except Exception: raise ValueError(f"Invalid ISO date: {v}")
    return out

def xirr(cash_flows, dates, guess=0.1):
    """Annualized money-weighted return. cash_flows use investor perspective."""
    if len(cash_flows)!=len(dates) or len(cash_flows)<2: raise ValueError("At least two matched cash flows and dates are required")
    ds=_dates(dates); t=np.array([(d-min(ds)).days/365.0 for d in ds],float)
    cf=np.asarray(cash_flows,float)
    if not (np.any(cf<0) and np.any(cf>0)): raise ValueError("XIRR requires at least one negative and one positive cash flow")
    def f(r):
        if r<=-0.999999: return float("inf")
        return float(np.sum(cf/np.power(1+r,t)))
    lo,hi=-0.9999,10.0
    flo,fhi=f(lo),f(hi)
    while flo*fhi>0 and hi<1e6:
        hi=hi*2+1; fhi=f(hi)
    if flo*fhi>0: raise ValueError("Could not bracket an XIRR solution for these cash flows")
    for _ in range(250):
        mid=(lo+hi)/2; fm=f(mid)
        if abs(fm)<1e-10: return float(mid)
        if flo*fm<=0: hi=mid; fhi=fm
        else: lo=mid; flo=fm
    return float((lo+hi)/2)

def performance_metrics(returns, periods_per_year=252, risk_free_rate=0.0):
    r=np.asarray(returns,dtype=float); r=r[np.isfinite(r)]
    if len(r)<2: raise ValueError("At least two periodic returns are required")
    if np.any(r<=-1): raise ValueError("Returns must be greater than -100%")
    if periods_per_year<=0: raise ValueError("periods_per_year must be positive")
    rf_period=(1+risk_free_rate)**(1/periods_per_year)-1
    excess=r-rf_period
    vol=float(np.std(r,ddof=1)*math.sqrt(periods_per_year))
    sharpe=float(np.mean(excess)/np.std(r,ddof=1)*math.sqrt(periods_per_year)) if np.std(r,ddof=1)>0 else None
    downside=np.minimum(excess,0)
    downside_dev=float(np.sqrt(np.mean(downside**2))*math.sqrt(periods_per_year))
    sortino=float(np.mean(excess)*periods_per_year/downside_dev) if downside_dev>0 else None
    wealth=np.cumprod(1+r); peaks=np.maximum.accumulate(np.r_[1.0,wealth])[1:]
    dd=wealth/peaks-1; maxdd=float(dd.min())
    years=len(r)/periods_per_year
    cagr=float(wealth[-1]**(1/years)-1) if wealth[-1]>0 and years>0 else None
    calmar=float(cagr/abs(maxdd)) if cagr is not None and maxdd<0 else None
    return {"observations":int(len(r)),"annualized_volatility":vol,"sharpe_ratio":sharpe,
            "sortino_ratio":sortino,"max_drawdown":maxdd,"cagr":cagr,"calmar_ratio":calmar,
            "cumulative_return":float(wealth[-1]-1),"best_period":float(r.max()),"worst_period":float(r.min())}

def relative_metrics(portfolio_returns, benchmark_returns, periods_per_year=252):
    p=np.asarray(portfolio_returns,float); b=np.asarray(benchmark_returns,float)
    if p.shape!=b.shape or p.ndim!=1 or len(p)<2: raise ValueError("Portfolio and benchmark returns must be matched one-dimensional series with at least two observations")
    active=p-b; te=float(np.std(active,ddof=1)*math.sqrt(periods_per_year))
    ir=float(np.mean(active)*periods_per_year/te) if te>0 else None
    return {"tracking_error":te,"information_ratio":ir,"active_cumulative_return":float(np.prod(1+p)-np.prod(1+b)),
            "portfolio_cumulative_return":float(np.prod(1+p)-1),"benchmark_cumulative_return":float(np.prod(1+b)-1)}

def attribution(holdings, symbol_sectors=None):
    """Cross-sectional exposure attribution, not return contribution without period weights/returns."""
    symbol_sectors=symbol_sectors or {}
    total=sum(max(0,float(h.get("market_value",0))) for h in holdings)
    by_sector={}; by_asset={}
    for h in holdings:
        value=max(0,float(h.get("market_value",0))); w=value/total if total else 0
        sec=symbol_sectors.get(h["symbol"],h.get("sector","UNKNOWN")) or "UNKNOWN"
        asset=h.get("asset_class","UNKNOWN") or "UNKNOWN"
        for bucket,key in ((by_sector,sec),(by_asset,asset)):
            bucket[key]=bucket.get(key,0.0)+w
    return {"method":"market_value_weighted_exposure","total_market_value":total,
            "sector_exposure":[{"name":k,"weight":v,"market_value":v*total} for k,v in sorted(by_sector.items(),key=lambda x:-x[1])],
            "asset_exposure":[{"name":k,"weight":v,"market_value":v*total} for k,v in sorted(by_asset.items(),key=lambda x:-x[1])],
            "note":"Exposure attribution only. Return contribution requires dated holdings weights and security/sector returns."}
