"""BV+jR voltage prediction with an optional potential offset."""
import numpy as np
from strict_bv import A_STAR, strict_bv_x


def predict(j, fit):
    j = np.asarray(j, dtype=float)
    return fit["offset_mV"] + A_STAR * strict_bv_x(j / np.exp(fit["log_j0"]), fit["alpha"]) + fit["r_ohm_cm2"] * j
