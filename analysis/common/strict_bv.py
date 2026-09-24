"""Butler-Volmer models fitted by bounded voltage-space least squares."""
from __future__ import annotations
import math
from typing import Any
import numpy as np
from scipy.optimize import least_squares
A_STAR_MV = 8.31446261815324 * 298.15 / (2.0 * 96485.33212) * 1000.0
A_STAR = A_STAR_MV
ALPHA_LOW, ALPHA_HIGH = 0.01, 0.99
R_FREE_BOUND, E_FREE_BOUND_MV = 100.0, 200.0
LOW = np.array([math.log(1e-12), ALPHA_LOW])
HIGH = np.array([math.log(1e8), ALPHA_HIGH])


def strict_bv_x(u: np.ndarray | float, alpha: float) -> np.ndarray:
    """Solve j/j0 = exp(alpha*x) - exp(-(1-alpha)*x), with x = eta_BV/a_star."""
    arr = np.asarray(u, dtype=float)
    arr = np.clip(arr, 0.0, np.inf)
    alpha = float(np.clip(alpha, 1e-6, 1.0 - 1e-6))

    x = np.maximum(arr / np.maximum(1.0 + arr, 1.0), np.log1p(arr) / alpha)
    x = np.where(np.isfinite(x), x, np.log1p(arr) / alpha)
    for _ in range(30):
        xa = np.clip(x, 0.0, 140.0)
        ep = np.exp(np.clip(alpha * xa, -700.0, 700.0))
        em = np.exp(np.clip(-(1.0 - alpha) * xa, -700.0, 700.0))
        f = ep - em - arr
        df = alpha * ep + (1.0 - alpha) * em
        step = f / np.maximum(df, 1e-300)
        x_new = np.maximum(0.0, xa - step)
        if np.nanmax(np.abs(x_new - x)) < 1e-11:
            x = x_new
            break
        x = x_new
    return x


def r2_from_sse(y: np.ndarray, sse: float) -> float:
    tss = float(np.sum((y - np.mean(y)) ** 2))
    return float(1.0 - sse / tss) if tss > 0 else np.nan


def predict_variant(
    j: np.ndarray,
    params: np.ndarray,
    *,
    include_ir: bool,
    include_offset: bool,
) -> np.ndarray:
    pos = 0
    log_j0 = float(params[pos])
    pos += 1
    alpha = float(params[pos])
    pos += 1
    r_value = 0.0
    e_offset = 0.0
    if include_ir:
        r_value = float(params[pos])
        pos += 1
    if include_offset:
        e_offset = float(params[pos])
    x = strict_bv_x(j / np.exp(log_j0), alpha)
    return e_offset + A_STAR_MV * x + r_value * j


def start_vectors(
    j: np.ndarray,
    y: np.ndarray,
    include_ir: bool,
    include_offset: bool,
    current: dict[str, float],
) -> list[np.ndarray]:
    j10 = max(float(np.nanpercentile(j, 10)), 1e-9)
    j50 = max(float(np.nanpercentile(j, 50)), 1e-9)
    j90 = max(float(np.nanpercentile(j, 90)), 1e-9)
    y_min = float(np.nanmin(y))
    y_max = float(np.nanmax(y))
    y_span = max(y_max - y_min, 1e-9)

    lower = [math.log(1e-12), ALPHA_LOW]
    upper = [math.log(1e8), ALPHA_HIGH]
    if include_ir:
        lower.append(0.0)
        upper.append(R_FREE_BOUND)
    if include_offset:
        lower.append(-E_FREE_BOUND_MV)
        upper.append(E_FREE_BOUND_MV)
    lower_arr = np.asarray(lower, dtype=float)
    upper_arr = np.asarray(upper, dtype=float)

    r_slope = float(np.clip(y_span / max(j90 - j10, 1e-9), 0.0, R_FREE_BOUND))
    current_j0 = max(float(current.get("j0_mA", j10)), 1e-12)
    current_log_j0 = math.log(current_j0)
    current_a = float(current.get("a_mV", 45.0))
    current_alpha = float(np.clip(A_STAR_MV / max(current_a, 1e-9), ALPHA_LOW, ALPHA_HIGH))
    current_r = float(np.clip(current.get("r_mV_per_mA", 0.0), 0.0, R_FREE_BOUND))
    current_e = float(np.clip(current.get("e_offset_mV", 0.0), -E_FREE_BOUND_MV, E_FREE_BOUND_MV))

    base_starts = [
        (current_log_j0, current_alpha, current_r, current_e),
        (current_log_j0 - math.log(2.0), current_alpha, current_r, current_e),
        (current_log_j0 + math.log(2.0), current_alpha, current_r, current_e),
        (current_log_j0, 0.50, current_r, current_e),
        (math.log(max(j10 / 5.0, 1e-12)), 0.50, min(r_slope, R_FREE_BOUND), 0.0),
        (math.log(max(j50, 1e-12)), 0.35, 0.05, 0.0),
        (math.log(max(j50, 1e-12)), 0.70, 0.2, 0.0),
        (math.log(1e-3), 0.50, 0.0, 0.0),
        (math.log(1.0), 0.90, 0.5, 0.0),
        (math.log(max(j90, 1e-12)), ALPHA_HIGH, min(r_slope, R_FREE_BOUND), y_min),
    ]

    starts: list[np.ndarray] = []
    seen: set[tuple[float, ...]] = set()
    for log_j0, alpha, r_value, e_offset in base_starts:
        start = [log_j0, alpha]
        if include_ir:
            start.append(r_value)
        if include_offset:
            start.append(e_offset)
        arr = np.clip(np.asarray(start, dtype=float), lower_arr + 1e-9, upper_arr - 1e-9)
        key = tuple(np.round(arr, 8))
        if key not in seen:
            starts.append(arr)
            seen.add(key)
    return starts


def fit_variant(
    j: np.ndarray,
    y: np.ndarray,
    *,
    include_ir: bool,
    include_offset: bool,
    current: dict[str, float],
) -> dict[str, Any]:
    lower = [math.log(1e-12), ALPHA_LOW]
    upper = [math.log(1e8), ALPHA_HIGH]
    if include_ir:
        lower.append(0.0)
        upper.append(R_FREE_BOUND)
    if include_offset:
        lower.append(-E_FREE_BOUND_MV)
        upper.append(E_FREE_BOUND_MV)
    lower_arr = np.asarray(lower, dtype=float)
    upper_arr = np.asarray(upper, dtype=float)

    def residual(params: np.ndarray) -> np.ndarray:
        return y - predict_variant(j, params, include_ir=include_ir, include_offset=include_offset)

    best: dict[str, Any] | None = None
    for start in start_vectors(j, y, include_ir, include_offset, current):
        try:
            result = least_squares(
                residual,
                start,
                bounds=(lower_arr, upper_arr),
                x_scale="jac",
                max_nfev=12000,
                ftol=1e-10,
                xtol=1e-10,
                gtol=1e-10,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = type(exc).__name__
            continue
        res = residual(result.x)
        sse = float(np.dot(res, res))
        if best is None or sse < best["sse_mV2"]:
            pos = 0
            log_j0 = float(result.x[pos])
            pos += 1
            alpha = float(result.x[pos])
            pos += 1
            r_value = 0.0
            e_offset = 0.0
            if include_ir:
                r_value = float(result.x[pos])
                pos += 1
            if include_offset:
                e_offset = float(result.x[pos])
            best = {
                "ok": True,
                "error": "" if result.success else str(result.message),
                "log_j0": log_j0,
                "j0_mA": float(np.exp(log_j0)),
                "alpha": alpha,
                "r_mV_per_mA": r_value,
                "e_offset_mV": e_offset,
                "sse_mV2": sse,
                "rmse_mV": float(np.sqrt(sse / len(j))),
                "r2": r2_from_sse(y, sse),
                "nfev": int(result.nfev),
                "b_tafel_mV_dec": float(2.303 * A_STAR_MV / alpha),
                "at_alpha_low": bool(alpha <= ALPHA_LOW + 1e-4),
                "at_alpha_high": bool(alpha >= ALPHA_HIGH - 1e-4),
                "at_r_upper_bound": bool(include_ir and r_value >= R_FREE_BOUND - 1e-4),
                "at_e_upper_bound": bool(include_offset and e_offset >= E_FREE_BOUND_MV - 1e-4),
                "at_e_lower_bound": bool(include_offset and e_offset <= -E_FREE_BOUND_MV + 1e-4),
            }
    if best is None:
        return {"ok": False, "error": locals().get("last_error", "least_squares_failed")}
    return best
