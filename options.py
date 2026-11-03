"""Black-Scholes European option analytics. Inputs use annualized rates/volatility."""
import math
from scipy.stats import norm

def black_scholes(spot, strike, time_years, rate, volatility, option_type="call", dividend_yield=0.0):
    vals = [spot, strike, time_years, volatility]
    if any(v <= 0 for v in vals) or option_type not in ("call","put"):
        raise ValueError("spot, strike, time and volatility must be positive; type call/put")
    d1=(math.log(spot/strike)+(rate-dividend_yield+0.5*volatility**2)*time_years)/(volatility*math.sqrt(time_years))
    d2=d1-volatility*math.sqrt(time_years)
    disc_q=math.exp(-dividend_yield*time_years); disc_r=math.exp(-rate*time_years)
    if option_type=="call":
        price=spot*disc_q*norm.cdf(d1)-strike*disc_r*norm.cdf(d2)
        delta=disc_q*norm.cdf(d1)
    else:
        price=strike*disc_r*norm.cdf(-d2)-spot*disc_q*norm.cdf(-d1)
        delta=disc_q*(norm.cdf(d1)-1)
    gamma=disc_q*norm.pdf(d1)/(spot*volatility*math.sqrt(time_years))
    vega=spot*disc_q*norm.pdf(d1)*math.sqrt(time_years)/100
    theta_call=-(spot*disc_q*norm.pdf(d1)*volatility)/(2*math.sqrt(time_years))-rate*strike*disc_r*norm.cdf(d2)+dividend_yield*spot*disc_q*norm.cdf(d1)
    theta_put=-(spot*disc_q*norm.pdf(d1)*volatility)/(2*math.sqrt(time_years))+rate*strike*disc_r*norm.cdf(-d2)-dividend_yield*spot*disc_q*norm.cdf(-d1)
    return {"price":float(price),"delta":float(delta),"gamma":float(gamma),
            "vega_per_1pct":float(vega),"theta_per_year":float(theta_call if option_type=="call" else theta_put),
            "d1":float(d1),"d2":float(d2),"model":"Black-Scholes-Merton"}
