"""VHT response derivatives and support-constrained current scaling."""
import numpy as np
from numba import njit
from scipy.optimize import minimize_scalar
import independent_model as engine


@njit(cache=True)
def kinetic_and_jacobian(p, xx):
    # Implicitly differentiate steady coverage and q(eta)=x/c, without a new solver.
    n, count = xx.shape
    eta = np.empty((n, count))
    jac = np.zeros((n, count, len(p)))
    ln10 = np.log(10.)
    lh, lt, av, ah = p[:4]
    h, t = 10.**lh, 10.**lt
    for g in range(n):
        lk, lc = p[4+g], p[4+n+g]
        K = 10.**lk
        eta[g] = engine.response(xx[g], lh, lt, lk, lc, av, ah, 0.)
        for i in range(count):
            u = eta[g, i]/engine.THERMAL
            q, theta, vacancy, V, H, T = engine.state(u, lh, lt, lk, av, ah)
            a, b = np.exp(av*u), np.exp(-(1-av)*u)/K
            c, d = h*np.exp(ah*u), h*K*np.exp(-(1-ah)*u)
            tr = t*K*K
            Ftheta = -a-b-c-d-4*t*theta-4*tr*vacancy
            Itheta = -a-b+c+d
            Vu = av*a*vacancy + (1-av)*b*theta
            Hu = ah*c*theta + (1-ah)*d*vacancy
            qu = Vu+Hu-Itheta*(Vu-Hu)/Ftheta
            # Derivatives at fixed theta: log h, log t, alphaV, alphaH, log K.
            vp = np.array([0., 0., u*V, 0., ln10*b*theta])
            hp = np.array([ln10*H, 0., 0., u*H, -ln10*d*vacancy])
            tp = np.array([0., ln10*T, 0., 0., -2*ln10*tr*vacancy*vacancy])
            for k in range(5):
                qp = vp[k]+hp[k]-Itheta*(vp[k]-hp[k]-2*tp[k])/Ftheta
                index = k if k < 4 else 4+g
                jac[g, i, index] = -engine.THERMAL*qp/qu
            jac[g, i, 4+n+g] = -engine.THERMAL*ln10*q/qu
    return eta, jac


def optimize_scale(x, y, predictor, qlo, qhi):
    # Point inclusion is fixed before optimization. Scales cannot move scored points
    # beyond the predeclared model support or remove a difficult point from scoring.
    lo = max(-3., float(np.log10(x.max() / qhi)))
    hi = min(3., float(np.log10(x.min() / qlo)))
    assert lo <= 1e-12 and hi >= -1e-12 and lo <= hi
    objective = lambda d: float(np.sum((predictor(x / 10.**d) - y)**2))
    grid = np.linspace(lo, hi, 81)
    scores = np.array([objective(d) for d in grid])
    candidates = [(objective(0.), 0.), (scores[0], lo), (scores[-1], hi)]
    for i in range(len(grid)):
        if i and scores[i] > scores[i - 1]:
            continue
        if i + 1 < len(grid) and scores[i] > scores[i + 1]:
            continue
        a, b = grid[max(0, i - 1)], grid[min(len(grid) - 1, i + 1)]
        if b - a < 1e-12:
            continue
        fit = minimize_scalar(objective, bounds=(a, b), method="bounded", options={"xatol": 1e-10})
        assert fit.success
        candidates.append((float(fit.fun), float(fit.x)))
    score, d = min(candidates)
    xr = x / 10.**d
    assert xr.min() >= qlo * (1 - 1e-10) and xr.max() <= qhi * (1 + 1e-10)
    return 10.**d, lo, hi, abs(d - lo) < 2e-6 or abs(d - hi) < 2e-6
