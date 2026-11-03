"""Implied volatility solver using bisection over Black-Scholes prices."""
from .options import black_scholes

def implied_volatility(market_price, spot, strike, time_years, rate, option_type="call", dividend_yield=0.0, tol=1e-7):
    if market_price<=0: raise ValueError("market_price must be positive")
    lo,hi=1e-4,5.0
    def price(v): return black_scholes(spot,strike,time_years,rate,v,option_type,dividend_yield)["price"]
    plo,phi=price(lo),price(hi)
    if market_price<plo-1e-8 or market_price>phi+1e-8: raise ValueError("market price outside model price bounds")
    for _ in range(150):
        mid=(lo+hi)/2; pm=price(mid)
        if abs(pm-market_price)<tol:return {"implied_volatility":mid,"implied_volatility_percent":mid*100,"iterations":_+1}
        if pm<market_price:lo=mid
        else:hi=mid
    mid=(lo+hi)/2
    return {"implied_volatility":mid,"implied_volatility_percent":mid*100,"iterations":150}
