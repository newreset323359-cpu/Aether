"""Risk calculations based on supplied periodic portfolio returns."""
import numpy as np

def _clean(returns):
    x = np.asarray(returns, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 2:
        raise ValueError("At least two finite returns are required")
    if np.any(x <= -1):
        raise ValueError("Returns must be greater than -100%")
    return x

def historical_var_cvar(returns, confidence=0.95, portfolio_value=1.0):
    x = _clean(returns)
    if not 0.5 < confidence < 1:
        raise ValueError("confidence must be between 0.5 and 1")
    losses = -x
    var = float(np.quantile(losses, confidence, method="linear"))
    tail = losses[losses >= var]
    cvar = float(tail.mean()) if tail.size else var
    return {"method":"historical", "confidence":confidence, "observations":int(x.size),
            "var_fraction":var, "cvar_fraction":cvar,
            "var_amount":var*portfolio_value, "cvar_amount":cvar*portfolio_value}

def parametric_var_cvar(returns, confidence=0.95, portfolio_value=1.0):
    from scipy.stats import norm
    x = _clean(returns)
    mu, sigma = float(x.mean()), float(x.std(ddof=1))
    z = float(norm.ppf(confidence))
    # Loss quantile and expected shortfall for a normal return distribution.
    var = -(mu - z*sigma)
    cvar = -mu + sigma * float(norm.pdf(z))/(1-confidence)
    return {"method":"parametric_normal", "confidence":confidence, "observations":int(x.size),
            "mean_return":mu, "volatility":sigma, "var_fraction":var,
            "cvar_fraction":cvar, "var_amount":var*portfolio_value,
            "cvar_amount":cvar*portfolio_value}

def drawdown_stats(returns):
    x = _clean(returns)
    wealth = np.cumprod(1+x)
    peaks = np.maximum.accumulate(np.r_[1.0, wealth])[1:]
    dd = wealth/peaks - 1
    return {"max_drawdown":float(dd.min()), "cumulative_return":float(wealth[-1]-1)}
