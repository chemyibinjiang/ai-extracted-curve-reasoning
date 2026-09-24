"""Reversible mean-field Volmer-Tafel kinetics with no explicit jR or offset."""
import numpy as np
from scipy.optimize import least_squares
from scipy.special import expit

VT = 8.31446261815324 * 298.15 / 96485.33212 * 1000


def coverage_from_current(j, jt, p):
    j = np.atleast_1d(j).astype(float)
    if np.any(j <= 0) or np.any(j >= jt) or not 0 < p < 1:
        raise ValueError("Reversible Tafel inversion requires 0 < j < JT and 0 < p < 1")
    y = j / jt
    # theta = p + (1-p)z; this form avoids subtracting two equilibrium rates.
    z = y / (p + np.sqrt((1-y)*p*p+y*(1-p)**2))
    return p + (1-p)*z, z


def inverse(j, parameters, kind="finite_volmer"):
    """eta in mV for j in mA/cm2; parameters are ln(JT), logit(p), [ln(A), alpha]."""
    pars = np.asarray(parameters)
    if kind == "low_coverage":
        j=np.atleast_1d(j).astype(float)
        if np.any(j<=0):
            raise ValueError("Positive current required")
        log_occ=.5*np.logaddexp(0,np.log(j)-pars[1])
        return VT*_invert_volmer(np.log(j)-pars[0],log_occ,np.zeros_like(j),pars[2])
    jt, p = np.exp(pars[0]), expit(pars[1])
    theta, z = coverage_from_current(j, jt, p)
    log_occ = np.log1p((1-p)/p*z)
    y=np.atleast_1d(j)/jt
    root=np.sqrt((1-y)*p*p+y*(1-p)**2)
    log_vac=np.log((1-y)/(1-p+root))
    ueq = log_occ - log_vac
    if kind == "quasi_equilibrium":
        return VT*ueq
    if kind != "finite_volmer":
        raise ValueError(kind)
    alpha = pars[3]
    log_j_a = np.log(np.atleast_1d(j))-pars[2]
    return VT*_invert_volmer(log_j_a,log_occ,log_vac,alpha)


def _invert_volmer(log_j_a,log_occ,log_vac,alpha):
    ueq=log_occ-log_vac
    lo = ueq.copy()
    hi = np.maximum.reduce([lo, (log_j_a-log_vac+np.log(2))/alpha,
                            log_occ-log_vac+np.log(2)])+1
    u = (lo+hi)/2
    for _ in range(60):
        reverse = log_occ-(1-alpha)*u
        denom = np.logaddexp(log_j_a, reverse)
        error = log_vac+alpha*u-denom
        active = np.abs(error)>2e-13
        if not np.any(active):
            break
        hi = np.where(active & (error>0), u, hi)
        lo = np.where(active & (error<=0), u, lo)
        slope = alpha+(1-alpha)*np.exp(reverse-denom)
        trial = u-error/slope
        u = np.where(active, np.where((trial>lo)&(trial<hi),trial,(lo+hi)/2),u)
    if np.max(np.abs(log_vac+alpha*u-np.logaddexp(log_j_a,log_occ-(1-alpha)*u)))>1e-8:
        raise ArithmeticError("Volmer inversion did not converge")
    return u


def state(eta, parameters, kind="finite_volmer"):
    eta=np.atleast_1d(eta).astype(float)
    if np.any(eta<0):
        raise ValueError("Only positive cathodic overpotential is implemented")
    pars=np.asarray(parameters)
    if kind=="low_coverage":
        a,b,alpha=np.exp(pars[0]),np.exp(pars[1]),pars[2]
        u=eta/VT
        av=a*np.exp(alpha*u)
        bv=a*np.exp(-(1-alpha)*u)
        constant=av*(-np.expm1(-u))
        linear=2*b+bv
        z=2*constant/(linear+np.sqrt(linear**2+4*b*constant))
        current=b*z*(z+2)
        return dict(current=current,relative_H_coverage=z+1,
                    volmer_forward=av,volmer_reverse=bv*(z+1),
                    tafel_forward=b*(z+1)**2,tafel_reverse=np.full_like(u,b))
    jt,p=np.exp(pars[0]),expit(pars[1])
    u=eta/VT
    if kind=="quasi_equilibrium":
        theta=expit(pars[1]+u)
        current=jt*theta**2*(-np.expm1(-2*u))
        return dict(current=current,theta=theta,theta_volmer_equilibrium=theta)
    if kind!="finite_volmer":
        raise ValueError(kind)
    capacity,alpha=np.exp(pars[2]),pars[3]
    av=capacity*np.exp(alpha*u)
    bv=capacity*np.exp(-(1-alpha)*u)
    c=(1-p)/p
    linear=2*jt*p+av+c*bv
    constant=av*(-np.expm1(-u))
    quadratic=jt*(1-2*p)
    discriminant=linear**2+4*quadratic*constant
    if np.any(discriminant<=0):
        raise ArithmeticError("Nonpositive physical discriminant")
    z=2*constant/(linear+np.sqrt(discriminant))
    current=jt*z*(2*p+(1-2*p)*z)
    theta=p+(1-p)*z
    return dict(current=current,theta=theta,theta_volmer_equilibrium=expit(pars[1]+u),
        volmer_forward=av*(1-z),volmer_reverse=bv*(1+c*z),
        tafel_forward=jt*theta**2,
        tafel_reverse=jt*(p/(1-p))**2*((1-p)*(1-z))**2)


def scaled_parameters(parameters, factor, kind):
    if not 0 < factor <= 1:
        raise ValueError("Unit-count factor must be in (0,1]")
    out=np.array(parameters,dtype=float).copy()
    if kind=="low_coverage":
        out[:2]+=np.log(factor)
        return out
    out[0]+=np.log(factor)
    if kind=="finite_volmer":
        out[2]+=np.log(factor)
    return out


def fit(j, eta, kind, extra_starts=(), seed=20260910):
    j,eta=np.asarray(j),np.asarray(eta)
    maxj=max(j)
    if kind=="low_coverage":
        return fit_low_coverage(j,eta,extra_starts,seed)
    low=np.array([np.log(maxj)+1e-6,-20,-20,.2])
    high=np.array([np.log(maxj)+14,12,20,.8])
    dim=2 if kind=="quasi_equilibrium" else 4
    low,high=low[:dim],high[:dim]
    rng=np.random.default_rng(seed)
    starts=[np.array([np.log(maxj*mult),z,-3,.5])[:dim]
            for mult in [1.15,2,6,30] for z in [-8,-4,0]]
    if dim==4:
        starts += [np.r_[np.log(maxj)+rng.uniform(.1,7),rng.uniform(-10,1),
                           rng.uniform(-12,6),rng.uniform(.21,.79)] for _ in range(12)]
    starts += [np.asarray(p)[:dim] for p in extra_starts]
    attempts=[]
    for start in starts:
        start=np.clip(start,low+1e-7,high-1e-7)
        opt=least_squares(lambda p:inverse(j,p,kind)-eta,start,bounds=(low,high),
                          x_scale="jac",max_nfev=600,ftol=1e-10,xtol=1e-10,gtol=1e-10)
        attempts.append(dict(parameters=opt.x.tolist(),success=bool(opt.success),
                             sse_mV2=float(opt.fun@opt.fun),nfev=opt.nfev))
    completed=[r for r in attempts if r["success"]]
    if not completed:
        raise RuntimeError("No fit converged")
    best=min(completed,key=lambda r:r["sse_mV2"])
    p=np.array(best["parameters"])
    predicted=inverse(j,p,kind)
    theta,_=coverage_from_current(j,np.exp(p[0]),expit(p[1]))
    row=dict(kind=kind,parameters=p.tolist(),JT_mA_cm2=float(np.exp(p[0])),
        theta0=float(expit(p[1])),rmse_mV=float(np.sqrt(np.mean((predicted-eta)**2))),
        max_abs_mV=float(np.max(np.abs(predicted-eta))),prediction_mV=predicted.tolist(),
        theta=theta.tolist(),residual_mV=(predicted-eta).tolist(),
        bounds=dict(lower=low.tolist(),upper=high.tolist()),
        active_bounds=[name for name,value,l,h in zip(
            ["ln_JT","logit_theta0","ln_A","alpha_V"],p,low,high)
            if min(value-l,h-value)<1e-4],attempts=attempts,
        n_converged=len(completed),n_near_best=sum(r["sse_mV2"]<best["sse_mV2"]+.01 for r in completed))
    if dim==4:
        row.update(A_mA_cm2=float(np.exp(p[2])),alpha_V=float(p[3]))
    return row


def fit_low_coverage(j,eta,extra_starts=(),seed=20260910):
    low,high=np.array([-20,-20,.2]),np.array([20,20,.8])
    rng=np.random.default_rng(seed)
    starts=[np.array([aa,bb,alpha]) for aa in [0,4,8] for bb in [-8,-3,1]
            for alpha in [.3,.6]]
    starts += [rng.uniform(low+[2,2,.001],high-[2,2,.001]) for _ in range(10)]
    starts += list(extra_starts)
    attempts=[]
    for start in starts:
        opt=least_squares(lambda p:inverse(j,p,"low_coverage")-eta,
                          np.clip(start,low+1e-7,high-1e-7),bounds=(low,high),
                          x_scale="jac",max_nfev=600,ftol=1e-10,xtol=1e-10,gtol=1e-10)
        attempts.append(dict(parameters=opt.x.tolist(),success=bool(opt.success),
                             sse_mV2=float(opt.fun@opt.fun),nfev=opt.nfev))
    completed=[r for r in attempts if r["success"]]
    best=min(completed,key=lambda r:r["sse_mV2"])
    p=np.array(best["parameters"])
    pred=inverse(j,p,"low_coverage")
    return dict(kind="low_coverage",parameters=p.tolist(),JT_mA_cm2=None,theta0=None,
        A_mA_cm2=float(np.exp(p[0])),B_mA_cm2=float(np.exp(p[1])),alpha_V=float(p[2]),
        rmse_mV=float(np.sqrt(np.mean((pred-eta)**2))),max_abs_mV=float(np.max(np.abs(pred-eta))),
        prediction_mV=pred.tolist(),residual_mV=(pred-eta).tolist(),
        bounds=dict(lower=low.tolist(),upper=high.tolist()),
        active_bounds=[name for name,value,l,h in zip(["ln_A","ln_B","alpha_V"],p,low,high)
                       if min(value-l,h-value)<1e-4],attempts=attempts,
        n_converged=len(completed),n_near_best=sum(r["sse_mV2"]<best["sse_mV2"]+.01 for r in completed))
