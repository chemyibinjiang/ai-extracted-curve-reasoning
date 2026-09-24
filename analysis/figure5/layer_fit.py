"""NiFeP layer-normalized BV+jR fitting and summary statistics."""
import numpy as np
from scipy.optimize import least_squares
import strict_bv as strict
from strict_predict import predict as strict_predict
strict.predict = strict_predict
R_UPPER = 100.0


def predict(q, fit):
    return strict.predict(np.asarray(q), fit)


def fit_zero_offset(q, eta, include_r=True, weights=None):
    q, eta = np.asarray(q), np.asarray(eta)
    w = np.ones_like(q) if weights is None else np.asarray(weights)
    lower = [float(strict.LOW[0]), float(strict.LOW[1])]
    upper = [float(strict.HIGH[0]), float(strict.HIGH[1])]
    if include_r:
        lower.append(0.0)
        upper.append(R_UPPER)

    def residual(p):
        r = p[2] if include_r else 0.0
        return np.sqrt(w) * (strict.A_STAR * strict.strict_bv_x(q / np.exp(p[0]), p[1]) + r * q - eta)

    candidates = []
    for j0 in (0.001, 0.01, 0.1, 1.0):
        for alpha in (0.2, 0.5, 0.8):
            start = [np.log(j0), alpha] + ([18.0] if include_r else [])
            result = least_squares(residual, start, bounds=(lower, upper), x_scale="jac",
                                   max_nfev=1000, ftol=1e-11, xtol=1e-11, gtol=1e-11)
            candidates.append(dict(success=bool(result.success), parameters=result.x.tolist(),
                                   weighted_sse=float(result.fun @ result.fun), nfev=result.nfev))
    good = [c for c in candidates if c["success"]]
    assert good
    best = min(good, key=lambda c: c["weighted_sse"])
    p = best["parameters"]
    fit = dict(log_j0=p[0], j0_mA_cm2=float(np.exp(p[0])), alpha=p[1],
               r_ohm_cm2=p[2] if include_r else 0.0, offset_mV=0.0,
               b_asymptotic_mV_dec=float(np.log(10) * strict.A_STAR / p[1]),
               free_parameters=3 if include_r else 2, attempts=candidates)
    error = predict(q, fit) - eta
    fit.update(rmse_mV=float(np.sqrt(np.mean(error**2))),
               weighted_rmse_mV=float(np.sqrt(np.sum(w * error**2) / np.sum(w))),
               max_abs_error_mV=float(np.max(np.abs(error))),
               at_bound=bool(any(abs(v - lo) < 1e-5 or abs(v - hi) < 1e-5
                                 for v, lo, hi in zip(p, lower, upper))))
    near = [c for c in good if c["weighted_sse"] <= best["weighted_sse"] + 1e-5]
    fit["near_best_parameter_spread"] = np.ptp([c["parameters"] for c in near], axis=0).tolist()
    return fit


def stats(residual):
    return dict(rmse_mV=float(np.sqrt(np.mean(residual**2))),
                mean_model_minus_data_mV=float(np.mean(residual)),
                max_abs_error_mV=float(np.max(np.abs(residual))))
