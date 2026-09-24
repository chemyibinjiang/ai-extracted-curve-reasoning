"""Steady-state reversible Volmer-Heyrovsky-Tafel responses."""
import numpy as np
from numba import njit
THERMAL = 1000 * 8.31446261815324 * 298.15 / 96485.33212
KBT_MEV = 1000 * 8.617333262145e-5 * 298.15


@njit(cache=True)
def state(u, logh, logt, logK, av=.5, ah=.5):
    h, t, K = 10.**logh, (0. if logt <= -90. else 10.**logt), 10.**logK
    a = np.exp(av*u)
    b = np.exp(-(1-av)*u)/K
    c = h*np.exp(ah*u)
    d = h*K*np.exp(-(1-ah)*u)
    scale = max(a,b,c,d,t,t*K*K)
    aa, bb, cc, dd, tf, tr = a/scale, b/scale, c/scale, d/scale, t/scale, t*K*K/scale
    # Rationalized roots avoid cancellation for both small theta and small vacancy.
    A = -2*(tf-tr)
    B = -(aa+bb+cc+dd+4*tr)
    C = aa+dd+2*tr
    theta = 2*C/(-B+np.sqrt(max(0., B*B-4*A*C)))
    Av = -A
    Bv = -(aa+bb+cc+dd+4*tf)
    Cv = bb+cc+2*tf
    vacancy = 2*Cv/(-Bv+np.sqrt(max(0., Bv*Bv-4*Av*Cv)))
    V = a*vacancy-b*theta
    H = c*theta-d*vacancy
    T = t*theta*theta-t*K*K*vacancy*vacancy
    current = V+H
    if t == 0.:
        # In the VH limit, net-rate subtraction loses precision for huge fitted c.
        current = 2*h*np.exp((av+ah)*u)*(-np.expm1(-2*u))/(a+b+c+d)
    return current, theta, vacancy, V, H, T


@njit(cache=True)
def response(x, logh, logt, logK, logc, av=.5, ah=.5, Q=0.):
    out = np.empty(len(x))
    for i in range(len(x)):
        target = x[i]/10.**logc
        lo, hi = 0., 8.
        while state(hi,logh,logt,logK,av,ah)[0] < target and hi < 256.:
            hi *= 2
        for _ in range(44):
            mid = (lo+hi)/2
            if state(mid,logh,logt,logK,av,ah)[0] < target:
                lo = mid
            else:
                hi = mid
        out[i] = THERMAL*(lo+hi)/2 + Q*x[i]
    return out


@njit(cache=True)
def bv_response(x, alpha, Q):
    out = np.empty(len(x))
    for i in range(len(x)):
        lo, hi = 0., np.log1p(x[i])/alpha+2.
        for _ in range(55):
            mid = (lo+hi)/2
            if np.exp(alpha*mid)-np.exp(-(1-alpha)*mid) < x[i]:
                lo = mid
            else:
                hi = mid
        out[i] = THERMAL/2*(lo+hi)/2 + Q*x[i]
    return out


def metrics(y, prediction):
    e = np.asarray(prediction)-np.asarray(y)
    return dict(RMSE_mV=float(np.sqrt(np.mean(e**2))),
        R2=float(1.-np.sum(e**2)/np.sum((y-np.mean(y))**2)), max_abs_mV=float(np.max(abs(e))))
