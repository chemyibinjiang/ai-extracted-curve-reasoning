"""Degree of rate control with independent mass-action checks."""
import numpy as np
from scipy.optimize import brentq
import independent_model as engine
EPSILON = 1e-3
LN10 = np.log(10.)


def coordinates(row):
    return (row.log10_kH_over_kV, row.log10_kT_over_kV,
            -row.DeltaG_eff_meV / (engine.KBT_MEV * LN10), row.alphaV, row.alphaH)


def state(row, eta_mV, log_multipliers=None):
    """Return j, theta, vacancy, rV, rH, rT in the unperturbed kV units."""
    dv, dh, dt = np.zeros(3) if log_multipliers is None else log_multipliers
    lh, lt, lk, av, ah = coordinates(row)
    values = np.array(engine.state(eta_mV / engine.THERMAL,
        lh + (dh - dv) / LN10, lt + (dt - dv) / LN10, lk, av, ah))
    # kV=1 is an internal solver gauge, not permission to renormalize away dv.
    values[[0, 3, 4, 5]] *= np.exp(dv)
    return values


def elementary_rates(row, eta_mV, theta, log_multipliers=None):
    dv, dh, dt = np.zeros(3) if log_multipliers is None else log_multipliers
    h, t = row.kH_over_kV, row.kT_over_kV
    K = np.exp(-row.DeltaG_eff_meV / engine.KBT_MEV)
    u, vacant = eta_mV / engine.THERMAL, 1 - theta
    return np.array([
        np.exp(dv + row.alphaV*u)*vacant,
        np.exp(dv - (1-row.alphaV)*u)*theta/K,
        np.exp(dh + row.alphaH*u)*h*theta,
        np.exp(dh - (1-row.alphaH)*u)*h*K*vacant,
        np.exp(dt)*t*theta**2,
        np.exp(dt)*t*K*K*vacant**2])


def rate_control(row, eta_mV, epsilon=EPSILON):
    result = []
    for i in range(3):
        perturbation = np.zeros(3)
        perturbation[i] = epsilon
        plus = state(row, eta_mV, perturbation)[0]
        minus = state(row, eta_mV, -perturbation)[0]
        assert plus > 0 and minus > 0
        result.append((np.log(plus)-np.log(minus))/(2*epsilon))
    return np.array(result)


def independent_state(row, eta_mV, perturbation):
    """Explicit mass-action/root-solver cross-check, without the kV gauge."""
    def balance(theta):
        vf, vr, hf, hr, tf, tr = elementary_rates(row, eta_mV, theta, perturbation)
        return vf-vr-hf+hr-2*(tf-tr)
    theta = brentq(balance, 0., 1., xtol=1e-14)
    vf, vr, hf, hr, tf, tr = elementary_rates(row, eta_mV, theta, perturbation)
    return np.array([vf-vr+hf-hr, theta, 1-theta, vf-vr, hf-hr, tf-tr])
