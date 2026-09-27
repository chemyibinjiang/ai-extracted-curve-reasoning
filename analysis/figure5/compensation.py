"""Electrical compensation accounting on the published MoS2 curves."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent

def read(name):
    return pd.read_csv(HERE / "inputs" / name, float_precision="round_trip")


def reference(name):
    return json.loads((HERE / "reference" / name).read_text(encoding="utf-8"))


def panel_a(out):
    native = read("A_SOURCE_ENDPOINTS.csv")
    expected = reference("A_FROZEN_ACCOUNTING.json")
    assert native["sample"].eq("treated_1cm2").all() and native.area_cm2.eq(1).all()
    current = np.linspace(50, 950, 181)
    design = np.column_stack([np.ones(len(current)), np.log10(current), current])
    mapped, fits = {}, {}
    for label in ("raw", "corrected"):
        points = native[native.correction.eq(label)]
        unique, inverse = np.unique(points.j_cathodic_mA_cm2.to_numpy(), return_inverse=True)
        voltage = np.bincount(inverse, weights=points.eta_mV) / np.bincount(inverse)
        assert unique.min() <= current.min() and unique.max() >= current.max()
        mapped[label] = np.interp(current, unique, voltage)
        coefficients = np.linalg.lstsq(design, mapped[label], rcond=None)[0]
        saved = expected[label + "_fit"]
        np.testing.assert_allclose(coefficients, [saved["a_mV"], saved["b_mV_dec"], saved["Rgeom_ohm_cm2"]], atol=1e-9)
        fits[label] = dict(a_mV=coefficients[0], b_mV_dec=coefficients[1], R_ohm_cm2=coefficients[2])
    gap = mapped["raw"] - mapped["corrected"]
    removed = float(current @ gap / (current @ current))
    estimate = fits["corrected"]["R_ohm_cm2"] - (1 - 0.85) / 0.85 * removed
    np.testing.assert_allclose(estimate, reference("A_100_PERCENT_METHOD.json")["Rapp_100_estimated_ohm_cm2"], atol=1e-10)
    pd.DataFrame(dict(j_mA_cm2=current, raw_eta_mV=mapped["raw"], corrected_eta_mV=mapped["corrected"],
                      gap_mV=gap, j_delta_R_mV=current * removed)).to_csv(out / "A_MATCHED_GRID.csv", index=False)
    return dict(fits=fits, removed_R_ohm_cm2=removed, Rapp_100_estimated_ohm_cm2=float(estimate),
                note="100 percent is an estimate from the published 85 percent trace, not a new measurement")
