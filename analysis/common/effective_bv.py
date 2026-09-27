"""Effective BV in voltage space, with independently fitted effective coefficients.

j is the positive cathodic current magnitude. The optimizer uses fraction and
log(sum) coordinates to enforce nonnegative coefficients with sum <= 2.
"""
from __future__ import annotations

import math
import numpy as np
from numba import njit
from scipy.optimize import least_squares

VT = 1000 * 8.31446261815324 * 298.15 / 96485.33212
PROTOCOL = dict(temperature_K=298.15, coefficient_sum_bounds=[.001, 2.],
                cathodic_fraction_bounds=[.01, .99], j0_bounds=[1e-12, 1e8],
                R_bounds=[0., 100.], voltage_offset=False,
                objective="Equal-point voltage-space sum of squared residuals")


@njit(cache=True)
def inverse(u, fraction):
    if u <= 0:
        return 0.
    if u < 1e-8:
        return u + (.5 - fraction) * u * u
    lo, hi = 0., np.log1p(u) / fraction
    v = hi
    for _ in range(100):
        ep, em = np.exp(fraction * v), np.exp((fraction - 1) * v)
        f = np.expm1(fraction * v) - np.expm1((fraction - 1) * v) - u
        if abs(f) <= 2e-13 * u:
            return v
        if f > 0:
            hi = v
        else:
            lo = v
        vv = v - f / (fraction * ep + (1 - fraction) * em)
        if vv <= lo or vv >= hi:
            vv = (lo + hi) / 2
        if abs(vv - v) < 2e-14 * max(1., abs(v)):
            return vv
        v = vv
    return v


@njit(cache=True)
def evaluate(j, p, resistance):
    logj0, a, s = p[0], p[1], np.exp(p[2])
    r = p[3] if resistance else 0.
    A = VT / s
    pred, jac = np.empty(len(j)), np.empty((len(j), len(p)))
    for i in range(len(j)):
        u = j[i] * np.exp(-logj0)
        t = inverse(u, a)
        d = a * np.exp(a * t) + (1 - a) * np.exp((a - 1) * t)
        pred[i] = A * t + r * j[i]
        jac[i, 0] = -A * u / d
        jac[i, 1] = -A * t * u / d
        jac[i, 2] = -A * t
        if resistance:
            jac[i, 3] = j[i]
    return pred, jac


def seed(row):
    return (row["log_j0"], row["fraction"], row["coefficient_sum"], row["R"])


def predict(j, row):
    z, a, s, r = seed(row)
    return evaluate(np.asarray(j, dtype=float), np.array([z, a, math.log(s), r]), True)[0]


def fit(j, y, resistance=False, seeds=(), weights=None):
    j, y = np.asarray(j, dtype=float), np.asarray(y, dtype=float)
    if j.ndim != 1 or j.shape != y.shape or len(j) < 3:
        raise ValueError("Require matching vectors of at least three points")
    if not np.isfinite(j).all() or not np.isfinite(y).all() or np.any(j <= 0):
        raise ValueError("Finite observations and strictly positive currents required")
    w = np.ones_like(j) if weights is None else np.asarray(weights, dtype=float)
    if w.shape != j.shape or not np.isfinite(w).all() or np.any(w <= 0):
        raise ValueError("Require positive finite weights")
    rootw = np.sqrt(w)
    lo = np.array([math.log(1e-12), .01, math.log(.001)] + ([0.] if resistance else []))
    hi = np.array([math.log(1e8), .99, math.log(2.)] + ([100.] if resistance else []))
    slope = np.clip(np.ptp(y) / max(np.ptp(j), 1e-9), 0, 100)
    starts = list(seeds) + [
        (math.log(max(np.quantile(j, .1) / 5, 1e-12)), .5, 2., 0.),
        (math.log(max(np.median(j), 1e-12)), .9, 1., slope * .5),
        (math.log(1e-3), .5, 2., 0.), (0., .9, 2., .5)]

    def pack(values):
        z, a, s, r = values
        return np.clip(np.array([z, a, math.log(s)] + ([r] if resistance else [])), lo, hi)

    def fun(p):
        return rootw * (evaluate(j, p, resistance)[0] - y)

    def jac(p):
        return rootw[:, None] * evaluate(j, p, resistance)[1]

    base = min(starts, key=lambda v: float(fun(pack(v)) @ fun(pack(v))))
    starts += [(base[0], base[1], s, base[3]) for s in (1.5, 1., .5, .15)]
    best, trials = None, []
    for values in starts:
        p = pack(values)
        loss = float(fun(p) @ fun(p))
        if best is None or loss < best[0]:
            best = (loss, p.copy(), False, 0, "feasible_seed")
        result = least_squares(fun, np.clip(p, lo + 1e-12, hi - 1e-12), jac=jac,
            bounds=(lo, hi), x_scale="jac", max_nfev=1800,
            ftol=1e-10, xtol=1e-10, gtol=1e-9)
        loss = float(result.fun @ result.fun)
        trials.append((loss, result.x.copy(), bool(result.success)))
        if loss < best[0]:
            best = (loss, result.x.copy(), bool(result.success), result.nfev, str(result.message))
    objective, p, converged, nfev, message = best
    # A retained feasible seed is reported separately from optimizer convergence.
    equivalent_converged = any(ok and loss <= objective * (1 + 1e-8) + 1e-8 for loss, _, ok in trials)
    s, r = float(np.exp(p[2])), float(p[3]) if resistance else 0.
    error = evaluate(j, p, resistance)[0] - y
    sse = float(error @ error)
    ss = float(np.sum((y - y.mean()) ** 2))
    singular = np.linalg.svd(jac(p), compute_uv=False)
    return dict(log_j0=float(p[0]), j0=float(np.exp(p[0])), fraction=float(p[1]),
        coefficient_sum=s, alpha_c=s * float(p[1]), alpha_a=s * (1 - float(p[1])),
        R=r, Q=r * float(np.exp(p[0])), b_mV_dec=VT * math.log(10) / (s * p[1]),
        sse=sse, rmse=math.sqrt(sse / len(y)), r2=1 - sse / ss if ss > 0 else None,
        weighted_sse=objective, n=len(y), k=len(p),
        optimizer_converged=converged, equivalent_converged=equivalent_converged,
        nfev=int(nfev), message=message, starts=len(starts),
        jac_condition=float(singular[0] / max(singular[-1], 1e-300)))


def fit_pair(j, y, references=None):
    references = references or {}
    rows = {}
    for name, resistance in [("BV", False), ("BV+jR", True)]:
        seeds = [seed(references[name])] if name in references else []
        if resistance:
            seeds.append(seed(rows["BV"]))
        rows[name] = fit(j, y, resistance, seeds)
    assert rows["BV+jR"]["sse"] <= rows["BV"]["sse"] * (1 + 1e-8) + 1e-7
    return rows
