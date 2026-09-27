"""Analytic HER concentration-polarization boundary from Prats and Chan (2021)."""
import math
from pathlib import Path
import sys

import numpy as np
from numba import njit, prange
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'analysis/common'))
import effective_bv as bv

THERMAL = bv.VT / 2
LOG_BOUNDS = (math.log(1e-12), math.log(1e8))
R_MAX = 100.


def predict(j, row):
    j = np.asarray(j, dtype=float)
    if np.any(j <= 0) or not np.isfinite(j).all():
        raise ValueError('Finite positive current magnitudes required')
    return THERMAL*np.logaddexp(0., np.log(j)-row['log_jL']) + row['R']*j


def metrics(y, prediction):
    y, prediction = np.asarray(y), np.asarray(prediction)
    error = prediction-y
    sse = float(error@error)
    tss = float(np.sum((y-y.mean())**2))
    return dict(n=len(y), sse=sse, rmse=float(np.sqrt(sse/len(y))),
                r2=1-sse/tss, max_abs_mV=float(np.max(abs(error))))


def fit(j, y, resistance=True):
    """Profile the bounded linear R coefficient exactly at each trial log(jL)."""
    j, y = np.asarray(j, dtype=float), np.asarray(y, dtype=float)
    if j.ndim != 1 or j.shape != y.shape or len(j) < 3 or not np.isfinite(y).all():
        raise ValueError('Matching finite vectors with at least three observations required')
    if not np.isfinite(j).all() or np.any(j <= 0):
        raise ValueError('Finite positive currents required')
    logj = np.log(j)
    def objective(z, parameters=False):
        nernst = THERMAL*np.logaddexp(0., logj-z)
        r = float(np.clip(j@(y-nernst)/(j@j), 0., R_MAX)) if resistance else 0.
        error = nernst+r*j-y
        return (float(error@error), r) if parameters else float(error@error)
    grid = np.linspace(*LOG_BOUNDS, 161)
    losses = np.array([objective(z) for z in grid])
    choices = [(losses[i], z) for i, z in enumerate(grid)]
    for i in range(len(grid)):
        if (i and losses[i] > losses[i-1]) or (i+1 < len(grid) and losses[i] > losses[i+1]):
            continue
        result = minimize_scalar(objective, bounds=(grid[max(i-1,0)], grid[min(i+1,len(grid)-1)]),
                                 method='bounded', options={'xatol': 1e-12})
        choices.append((float(result.fun), float(result.x)))
    loss, z = min(choices)
    r = objective(z, True)[1]
    row = dict(log_jL=float(z), jL=float(np.exp(z)), R=r, Q=float(np.exp(z)*r),
               k=2 if resistance else 1, alpha_c=2., alpha_a=0.)
    return dict(row, **metrics(y, predict(j, row)))


@njit(cache=True)
def template_loss(j, y, q, z):
    loss = 0.
    for i in range(len(j)):
        u = np.log(j[i])-z
        softplus = max(u, 0.) + np.log1p(np.exp(-abs(u)))
        error = THERMAL*softplus + q*np.exp(u)-y[i]
        loss += error*error
    return loss


@njit(cache=True)
def profile(j, y, q):
    lo = max(LOG_BOUNDS[0], np.log(q/R_MAX)) if q > 0 else LOG_BOUNDS[0]
    hi = LOG_BOUNDS[1]
    grid = np.linspace(lo, hi, 61)
    loss = np.array([template_loss(j,y,q,z) for z in grid])
    k = np.argmin(loss)
    best, zbest = loss[k], grid[k]
    golden = .6180339887498949
    for k in range(len(grid)):
        if (k and loss[k] > loss[k-1]) or (k+1 < len(grid) and loss[k] > loss[k+1]):
            continue
        left, right = grid[max(0,k-1)], grid[min(len(grid)-1,k+1)]
        c, d = right-golden*(right-left), left+golden*(right-left)
        fc, fd = template_loss(j,y,q,c), template_loss(j,y,q,d)
        for _ in range(65):
            if fc < fd:
                right,d,fd = d,c,fc
                c = right-golden*(right-left)
                fc = template_loss(j,y,q,c)
            else:
                left,c,fc = c,d,fd
                d = left+golden*(right-left)
                fd = template_loss(j,y,q,d)
        z = (left+right)/2
        value = template_loss(j,y,q,z)
        if value < best:
            best,zbest = value,z
    return best,zbest


@njit(parallel=True, cache=True)
def profile_grid(J, Y, N, candidates):
    losses = np.empty((len(candidates), len(N)))
    scales = np.empty_like(losses)
    for k in prange(len(candidates)):
        for i in range(len(N)):
            losses[k,i], scales[k,i] = profile(J[i,:N[i]],Y[i,:N[i]],candidates[k])
    return losses, scales
