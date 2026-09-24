"""Local polynomial derivatives on the original irregular current grid."""
import numpy as np


def polynomial_operator(x,center,degree=2):
    """Return linear derivative weights; x may be irregularly spaced."""
    x=np.asarray(x,float)
    dx=x-center
    h=1.01*np.max(np.abs(dx))
    if not np.isfinite(x).all() or h<=0:
        raise ValueError('Invalid polynomial neighborhood')
    u=dx/h
    w=(1-np.abs(u)**3)**3
    design=np.vander(u,N=degree+1,increasing=True)
    wd=np.sqrt(w)[:,None]*design
    cond=float(np.linalg.cond(wd))
    op=np.linalg.pinv(wd) * np.sqrt(w)[None,:]
    derivative=op[1]/h
    return derivative,op,design,w,cond


def curve_derivatives(j,eta,k=9,degree=2):
    j,eta=np.asarray(j,float),np.asarray(eta,float)
    if j.ndim!=1 or eta.shape!=j.shape or not np.isfinite(np.r_[j,eta]).all() or np.any(j<=0) or np.any(np.diff(j)<=0):
        raise ValueError('Invalid frozen curve')
    if k%2!=1 or k<5 or degree not in (1,2):
        raise ValueError('Invalid method')
    x=np.log10(j);half=k//2
    rows=[]
    for i in range(len(j)):
        info={'native_index':i,'j':float(j[i]),'eta_mV':float(eta[i]),'neighbors':k,'degree':degree}
        if i<half or i+half>=len(j):
            rows.append(info|{'status':'edge_support'});continue
        ids=np.arange(i-half,i+half+1)
        dx=x[ids]-x[i]
        radius=float(np.max(np.abs(dx)))
        span=float(np.ptp(dx))
        left,right=-float(dx[0]),float(dx[-1])
        info.update(logj_radius=radius,logj_span=span,left_log_span=left,right_log_span=right,
                    eta_span_mV=float(np.ptp(eta[ids])),left_index=int(ids[0]),right_index=int(ids[-1]))
        if radius>.45:
            rows.append(info|{'status':'too_wide_in_logcurrent'});continue
        if span<.04:
            rows.append(info|{'status':'too_narrow_in_logcurrent'});continue
        if min(left,right)<.15*radius:
            rows.append(info|{'status':'one_sided_support'});continue
        d,op,design,w,cond=polynomial_operator(x[ids],x[i],degree)
        effective=float(w.sum()**2/(w@w))
        if cond>1e4 or effective<degree+2:
            rows.append(info|{'status':'ill_conditioned_support'});continue
        coeff=op@eta[ids]
        fitted=design@coeff
        residual=eta[ids]-fitted
        rows.append(info|{'status':'eligible','slope_mV_dec':float(d@eta[ids]),
                          'local_eta_fit_mV':float(coeff[0]),'eta_rmse_mV':float(np.sqrt(w@(residual**2)/w.sum())),
                          'eta_noise_gain':float(np.linalg.norm(d)),'design_condition':cond,
                          'effective_points':effective})
    return rows
