"""Small dependency-light Gaussian HMM for univariate return regime discovery."""
import numpy as np

def fit_gaussian_hmm(observations, n_states=2, max_iter=250, tol=1e-5, seed=7):
    x=np.asarray(observations,dtype=float).reshape(-1)
    x=x[np.isfinite(x)]
    if len(x)<max(30,n_states*10): raise ValueError("Insufficient finite observations for requested HMM")
    if n_states<2 or n_states>4: raise ValueError("n_states must be between 2 and 4")
    rng=np.random.default_rng(seed); means=np.quantile(x,np.linspace(.2,.8,n_states))
    vars_=np.full(n_states,max(float(x.var()),1e-8)); trans=np.full((n_states,n_states),.05/(n_states-1)); np.fill_diagonal(trans,.95)
    start=np.full(n_states,1/n_states); prev=-np.inf
    def logsumexp(a,axis=None):
        m=np.max(a,axis=axis,keepdims=True); out=m+np.log(np.sum(np.exp(a-m),axis=axis,keepdims=True))
        return np.squeeze(out,axis=axis) if axis is not None else float(np.asarray(out).reshape(-1)[0])
    for iteration in range(max_iter):
        logb=-.5*(np.log(2*np.pi*vars_)[None,:]+(x[:,None]-means[None,:])**2/vars_[None,:])
        la=np.log(start+1e-15)+logb[0]; alphas=[la]
        for t in range(1,len(x)):
            la=logb[t]+np.array([logsumexp(la+np.log(trans[:,j]+1e-15)) for j in range(n_states)])
            alphas.append(la)
        ll=logsumexp(alphas[-1])
        lb=np.zeros((len(x),n_states))
        for t in range(len(x)-2,-1,-1):
            for i in range(n_states):
                lb[t,i]=logsumexp(np.log(trans[i]+1e-15)+logb[t+1]+lb[t+1])
        loggamma=np.vstack(alphas)+lb-ll
        gamma=np.exp(loggamma); gamma/=gamma.sum(axis=1,keepdims=True)
        xi_sum=np.zeros((n_states,n_states))
        for t in range(len(x)-1):
            mat=np.log(gamma[t,:,None]+1e-300)+np.log(trans+1e-15)+logb[t+1,None,:]+lb[t+1,None,:]
            mat-=logsumexp(mat); xi_sum+=np.exp(mat)
        start=gamma[0]/gamma[0].sum()
        trans=xi_sum/(xi_sum.sum(axis=1,keepdims=True)+1e-15)
        weights=gamma.sum(axis=0)+1e-15
        means=(gamma*x[:,None]).sum(axis=0)/weights
        vars_=(gamma*(x[:,None]-means[None,:])**2).sum(axis=0)/weights
        vars_=np.maximum(vars_,1e-10)
        if abs(ll-prev)<tol: break
        prev=ll
    states=np.argmax(gamma,axis=1)
    order=np.argsort(means)
    return {"model":"Gaussian HMM","states":int(n_states),"observations":int(len(x)),
            "log_likelihood":float(ll),"iterations":iteration+1,
            "state_means":means[order].tolist(),"state_volatilities":np.sqrt(vars_[order]).tolist(),
            "transition_matrix":trans[np.ix_(order,order)].tolist(),
            "latest_state":int(np.where(order==states[-1])[0][0]),
            "latest_state_probabilities":gamma[-1,order].tolist(),
            "state_sequence":states.tolist()}
