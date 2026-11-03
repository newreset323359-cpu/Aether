"""Monte Carlo portfolio terminal-value simulation using multivariate normal returns."""
import numpy as np

def simulate_portfolio(initial_value, weights, expected_returns, covariance, horizon_days=252, simulations=10000, seed=17):
    w=np.asarray(weights,dtype=float); mu=np.asarray(expected_returns,dtype=float); cov=np.asarray(covariance,dtype=float)
    n=w.size
    if initial_value<=0 or horizon_days<1 or simulations<100: raise ValueError("invalid simulation parameters")
    if mu.shape!=(n,) or cov.shape!=(n,n): raise ValueError("dimension mismatch")
    if not np.isclose(w.sum(),1): raise ValueError("weights must sum to 1")
    cov=(cov+cov.T)/2
    eig=np.linalg.eigvalsh(cov)
    if eig.min() < -1e-8: raise ValueError("covariance matrix must be positive semidefinite")
    rng=np.random.default_rng(seed); vals=np.full(simulations,float(initial_value))
    # Approximate daily geometric return parameters supplied as daily arithmetic inputs.
    chol=np.linalg.cholesky(cov+np.eye(n)*1e-12)
    for _ in range(horizon_days):
        z=rng.standard_normal((simulations,n))
        asset_r=mu+z@chol.T
        port_r=asset_r@w
        vals*=np.maximum(1+port_r,0)
    losses=initial_value-vals
    return {"method":"multivariate_normal_monte_carlo","simulations":simulations,"horizon_days":horizon_days,
            "initial_value":float(initial_value),"mean_terminal_value":float(vals.mean()),
            "median_terminal_value":float(np.median(vals)),
            "terminal_value_percentiles":{"p01":float(np.quantile(vals,.01)),"p05":float(np.quantile(vals,.05)),"p50":float(np.quantile(vals,.5)),"p95":float(np.quantile(vals,.95)),"p99":float(np.quantile(vals,.99))},
            "loss_var_95":float(np.quantile(losses,.95)),"loss_cvar_95":float(losses[losses>=np.quantile(losses,.95)].mean()),
            "probability_of_loss":float(np.mean(vals<initial_value))}
