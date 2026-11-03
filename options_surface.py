"""European Black-Scholes implied-volatility surface grid."""
from .implied_vol import implied_volatility

def build_iv_surface(quotes, spot, rate, dividend_yield=0.0):
    # quotes: [{strike, time_years, option_type, market_price}]
    points=[]
    for q in quotes:
        iv=implied_volatility(q["market_price"],spot,q["strike"],q["time_years"],rate,
                              q.get("option_type","call"),dividend_yield)
        points.append({"strike":float(q["strike"]),"time_years":float(q["time_years"]),
                       "option_type":q.get("option_type","call"),**iv})
    expiries=sorted({p["time_years"] for p in points})
    strikes=sorted({p["strike"] for p in points})
    return {"spot":spot,"rate":rate,"expiries_years":expiries,"strikes":strikes,
            "points":points,"model":"Black-Scholes implied volatility",
            "note":"European option model; ensure quotes are synchronized, liquid and contract-adjusted."}
