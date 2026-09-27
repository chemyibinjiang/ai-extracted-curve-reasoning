"""Profile scale-only template fits using an interpolated inverse."""
import numpy as np
from numba import njit, prange
import model as inverse
import effective_bv as bv
VT=bv.VT

@njit(cache=True)
def objective(j,lj,y,a,s,q,z,vals,ders):
    r = q*np.exp(-z)
    loss = 0.
    for i in range(len(j)):
        residual = VT/s * inverse.interp(lj[i]-z,a,vals,ders)+r*j[i]-y[i]
        loss += residual*residual
    return loss


@njit(cache=True)
def profile(j,lj,y,a,s,q,vals,ders):
    lo = -12*np.log(10.) if q<=0 else max(-12*np.log(10.),np.log(q)-np.log(100.))
    hi = 8*np.log(10.)
    if hi<=lo:
        return hi,objective(j,lj,y,a,s,q,hi,vals,ders)
    zz = np.linspace(lo,hi,35)
    losses = np.array([objective(j,lj,y,a,s,q,z,vals,ders) for z in zz])
    ib = np.argmin(losses)
    bestz,bestloss = zz[ib],losses[ib]
    golden = .6180339887498949
    for k in range(len(zz)):
        if k>0 and losses[k]>losses[k-1]:
            continue
        if k<len(zz)-1 and losses[k]>losses[k+1]:
            continue
        left,right = zz[max(0,k-1)],zz[min(len(zz)-1,k+1)]
        c,d = right-golden*(right-left),left+golden*(right-left)
        fc,fd = objective(j,lj,y,a,s,q,c,vals,ders),objective(j,lj,y,a,s,q,d,vals,ders)
        for _ in range(43):
            if fc<fd:
                right,d,fd = d,c,fc
                c = right-golden*(right-left)
                fc = objective(j,lj,y,a,s,q,c,vals,ders)
            else:
                left,c,fc = c,d,fd
                d = left+golden*(right-left)
                fd = objective(j,lj,y,a,s,q,d,vals,ders)
        z = (left+right)/2
        loss = objective(j,lj,y,a,s,q,z,vals,ders)
        if loss<bestloss:
            bestz,bestloss = z,loss
    return bestz,bestloss


@njit(parallel=True,cache=True)
def profile_candidates(J,Y,N,candidates):
    S,Z = np.empty((len(candidates),len(N))),np.empty((len(candidates),len(N)))
    lj = np.log(J)
    for k in prange(len(candidates)):
        a,s,q = candidates[k]
        vals,ders = inverse.table(a)
        for i,n in enumerate(N):
            z,loss = profile(J[i,:n],lj[i,:n],Y[i,:n],a,s,q,vals,ders)
            S[k,i],Z[k,i] = loss,z
    return S,Z
