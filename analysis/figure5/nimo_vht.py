"""Fit NiMo polarization with detailed-balance VHT, without jR or an offset.

The steady-state solver is shared with Figure 6. u = F*|eta|/(R*T),
K = theta_eq/(1-theta_eq), h = kH/kV, t = kT/kV, and c = 1000*F*kV.
All logarithms in the parameter vector are base 10. c has units mA/cm2.
Both elementary transfer coefficients are fixed at 0.5.
"""
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "figure6/vendor/vht"))
from independent_model import THERMAL, response, state

PARAMETERS = ("log10_h", "log10_t", "log10_K", "log10_c_mA_cm2")
LOW = np.array([-5., -5., -3., -6.])
HIGH = np.array([5., 5., 3., 6.])


def inverse(current, parameters):
    """Positive overpotential in mV at positive cathodic current in mA/cm2."""
    current = np.asarray(current, dtype=float)
    if np.any(current < 0) or not np.all(np.isfinite(current)):
        raise ValueError("Current must be finite and nonnegative")
    return response(current, *np.asarray(parameters, dtype=float), Q=0.)


def forward(voltage, parameters):
    p = np.asarray(parameters, dtype=float)
    rows = np.array([state(float(v) / THERMAL, *p[:3]) for v in np.asarray(voltage)])
    scale = 10.**p[3]
    return dict(current=scale * rows[:, 0], theta=rows[:, 1], vacancy=rows[:, 2],
                V=scale * rows[:, 3], H=scale * rows[:, 4], T=scale * rows[:, 5])


def mirror(parameters):
    """Swap V/H and forward/reverse T: identical current, theta -> 1-theta."""
    h, t, K, c = np.asarray(parameters, dtype=float)
    return np.array([-h, t + 2*K - h, -K, c + h])


def increasing_branch(parameters, voltage):
    p = np.asarray(parameters, dtype=float)
    theta = forward(np.array([min(voltage), max(voltage)]), p)["theta"]
    return mirror(p) if theta[-1] < theta[0] else p.copy()


def metrics(observed, predicted):
    error = np.asarray(predicted) - observed
    sse = float(error @ error)
    return dict(RMSE_mV=float(np.sqrt(np.mean(error**2))),
                R2=float(1 - sse / np.sum((observed - np.mean(observed))**2)),
                max_abs_error_mV=float(np.max(abs(error))), SSE_mV2=sse)


def fit(current, voltage, starts=64, seed=20260923, initial=None, bounds=None, tafel=True):
    """Equal-weight voltage residuals; retain every multistart result for audit."""
    if starts < 1:
        raise ValueError("At least one start is required")
    current, voltage = np.asarray(current), np.asarray(voltage)
    low, high = (LOW, HIGH) if bounds is None else bounds
    active = np.array([0, 1, 2, 3] if tafel else [0, 2, 3])

    def expand(p):
        full = np.array([0., -99., 0., 0.])
        full[active] = p
        return full

    rng = np.random.default_rng(seed)
    candidates = [] if initial is None else [np.asarray(initial)]
    while len(candidates) < starts:
        p = rng.uniform(np.maximum(low, [-4., -4., -2.5, -4.]),
                        np.minimum(high, [4., 4., 2.5, 4.]))
        unit_j = forward(np.array([np.median(voltage)]), np.r_[p[:3], 0.])["current"][0]
        p[3] = np.log10(np.median(current) / unit_j)
        candidates.append(p)
    records = []
    for index, start in enumerate(candidates[:starts]):
        solution = least_squares(lambda p: inverse(current, expand(p)) - voltage,
            np.clip(start, low + 1e-7, high - 1e-7)[active], bounds=(low[active], high[active]),
            diff_step=1e-4, x_scale="jac", max_nfev=1800,
            ftol=1e-10, xtol=1e-10, gtol=1e-8)
        full = expand(solution.x)
        records.append(dict(start=index, parameters=full.tolist(),
            success=bool(solution.success), status=int(solution.status), nfev=int(solution.nfev),
            optimality=float(solution.optimality),
            bound_parameters=[PARAMETERS[i] for i in active
                              if min(full[i]-low[i], high[i]-full[i]) < 1e-3],
            **metrics(voltage, inverse(current, full))))
    successful = [r for r in records if r["success"]]
    if not successful:
        raise RuntimeError("No VHT start converged")
    best = min(successful, key=lambda r: r["RMSE_mV"])
    return dict(best=best, starts=records, seed=seed, bounds=[low.tolist(), high.tolist()],
                parameters=list(PARAMETERS), alphaV=.5, alphaH=.5, tafel_enabled=tafel,
                resistance_ohm_cm2=0., offset_mV=0., temperature_K=298.15)
