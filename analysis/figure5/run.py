"""Reproduce the numerical analyses of current Figure 5 from digitized inputs.

Default: rerun the published BV/Tafel fits, EIS regression and current scaling.
The KSCN kinetic parameters are replayed; --refit-kscn also reruns its multistart fit.
"""
import argparse
import json
import os
from pathlib import Path
import sys

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(key, "1")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "common"))
import numpy as np
import pandas as pd
import strict_bv as bv
import layer_fit
import kscn_model
import refit_nimo


def read(name):
    return pd.read_csv(HERE / "inputs" / name, float_precision="round_trip")


def reference(name):
    return json.loads((HERE / "reference" / name).read_text(encoding="utf-8"))


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def predict(j, fit):
    return bv.predict_variant(np.asarray(j), np.array([fit["log_j0"], fit["alpha"], fit["r_mV_per_mA"]]),
                              include_ir=True, include_offset=False)


def check_fit(fit, expected, j, tolerance=2e-4):
    if not fit["ok"] or fit["error"]:
        raise ValueError(f"Fit failed: {fit}")
    # Prediction agreement is the primary check; correlated parameters need not be bit-identical.
    np.testing.assert_allclose(predict(j, fit), predict(j, expected), atol=tolerance, rtol=0)
    np.testing.assert_allclose(fit["rmse_mV"], expected["rmse_mV"], atol=2e-6, rtol=1e-6)


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


def panel_b(out):
    native, eis = read("B_POLARIZATION.csv"), read("B_EIS_NATIVE_DATA.csv")
    saved = reference("B_FROZEN_MODELS.json")
    rows, predictions = [], []
    for cycle, points in native.groupby("cycle", sort=True):
        j, eta = points.j_mA_cm2.to_numpy(), points.eta_mV.to_numpy()
        assert ((j >= 5) & (j <= 20)).all()
        fit = bv.fit_variant(j, eta, include_ir=True, include_offset=False, current={})
        expected = next(r for r in saved["fits"] if r["cycle"] == cycle)
        check_fit(fit, expected, j)
        arc = eis[eis.cycle.eq(cycle) & eis.minus_Zimag_ohm.between(1.4, 6)]
        coefficients = np.polynomial.polynomial.polyfit(arc.minus_Zimag_ohm, arc.Zreal_ohm, 2)
        np.testing.assert_allclose(coefficients, saved["EIS"][int(cycle) - 1]["coefficients"], atol=1e-9)
        rows.append(dict(cycle=int(cycle), R_BVjR_ohm_cm2=fit["r_mV_per_mA"], Rs_EIS_ohm=float(coefficients[0])))
        predictions.append(points.assign(predicted_eta_mV=predict(j, fit)))
    data = pd.DataFrame(rows)
    x, y = data.Rs_EIS_ohm.to_numpy(), data.R_BVjR_ohm_cm2.to_numpy()
    slope, intercept = np.polyfit(x, y, 1)
    trend = reference("B_RESISTANCE_TREND.json")
    np.testing.assert_allclose([slope, intercept], [trend["slope_cm2"], trend["intercept_ohm_cm2"]], rtol=1e-5)
    data.to_csv(out / "B_CYCLE_R.csv", index=False)
    pd.concat(predictions).to_csv(out / "B_PREDICTIONS.csv", index=False)
    return dict(cycles=rows, trend_slope=float(slope), trend_intercept=float(intercept),
                note="EIS Rs is in ohms and fitted Rapp in ohm cm2; this trend does not equate the two")


def panel_c(out):
    report = refit_nimo.run(out / "nimo", starts=64, checks=True, plot=False)
    expected = {False: 2.402925032, True: .427313358}
    for include_r, name in [(False, "BV"), (True, "BV+jR")]:
        np.testing.assert_allclose(report["empirical_fits"][name]["rmse_mV"], expected[include_r], atol=2e-6)
    assert report["VHT_best"]["RMSE_mV"] < .67
    return report


def panel_d(out, refit_kscn=False):
    original = read("NiFeP_ORIGINAL_DATA.csv")
    exclusions = read("NiFeP_EXCLUDED_DATA.csv")
    keys = ["curve_uid", "native_index"]
    excluded = set(map(tuple, exclusions[keys].to_numpy()))
    keep = [tuple(row) not in excluded for row in original[keys].to_numpy()]
    data = original.loc[keep].copy()
    assert len(original) == 63 and len(exclusions) == 2 and len(data) == 61
    assert exclusions.layers.eq(12).all() and set(exclusions.native_index) == {0, 1}
    q = data.j_mA_cm2.to_numpy() / data.layers.to_numpy()
    shared = layer_fit.fit_zero_offset(q, data.eta_mV.to_numpy())
    expected = reference("NiFeP_REFIT.json")["dataset"]
    np.testing.assert_allclose(layer_fit.predict(q, shared), layer_fit.predict(q, expected["shared_no_offset"]), atol=2e-4)
    rows = []
    for layers, points in data.groupby("layers", sort=True):
        q = points.j_mA_cm2.to_numpy() / layers
        fit = layer_fit.fit_zero_offset(q, points.eta_mV.to_numpy())
        saved = next(r["independent_no_offset"] for r in expected["curves"] if r["layers"] == layers)
        np.testing.assert_allclose(layer_fit.predict(q, fit), layer_fit.predict(q, saved), atol=2e-4)
        rows.append(dict(layers=int(layers), independent_R=fit["r_ohm_cm2"] / layers))
    r = pd.DataFrame(rows)
    inverse_layers = 1 / r.layers.to_numpy()
    slope = float(inverse_layers @ r.independent_R.to_numpy() / (inverse_layers @ inverse_layers))
    np.testing.assert_allclose(slope, reference("NiFeP_R_SCALING.json")["slope_ohm_cm2_layer"], rtol=1e-5)
    r.to_csv(out / "NiFeP_R.csv", index=False)
    data.to_csv(out / "NiFeP_RETAINED_POINTS.csv", index=False)

    observations, model = read("KSCN_DATA.csv"), reference("KSCN_MODEL.json")
    control = observations[observations.curve.eq("control")].sort_values("prepared_index")
    treated = observations[observations.curve.eq("kscn")].sort_values("prepared_index")
    parameters = np.array(model["parameters"])
    if refit_kscn:
        fitted = kscn_model.fit(control.j_mA_cm2.to_numpy(), control.eta_mV.to_numpy(), "finite_volmer")
        write_json(out / "KSCN_NEW_FIT.json", fitted)
        # Keep replay of the published representative separate from any new optimum.
    cal = treated[treated.role.eq("scale_calibration")]
    held = treated[treated.role.eq("held_out")]
    assert len(cal) == 18 and len(held) == 22
    assert cal.prepared_index.tolist() == model["calibration_indices"]
    assert held.prepared_index.tolist() == model["heldout_indices"]
    expected_current = kscn_model.state(cal.eta_mV.to_numpy(), parameters)["current"]
    factor = float(expected_current @ cal.j_mA_cm2.to_numpy() / (expected_current @ expected_current))
    np.testing.assert_allclose(factor, model["factor"], atol=1e-12)
    np.testing.assert_allclose(kscn_model.scaled_parameters(parameters, factor, "finite_volmer"),
                               model["scaled_parameters"], atol=1e-12)
    assert np.all(np.diff(control.eta_mV) > 0)
    ratio = cal.j_mA_cm2.to_numpy() / np.interp(cal.eta_mV, control.eta_mV, control.j_mA_cm2)
    pd.DataFrame(dict(eta_mV=cal.eta_mV, ratio=ratio)).to_csv(out / "KSCN_RATIO.csv", index=False)
    treated_prediction = kscn_model.state(treated.eta_mV.to_numpy(), np.array(model["scaled_parameters"]))["current"]
    treated.assign(predicted_j_mA_cm2=treated_prediction).to_csv(out / "KSCN_PREDICTIONS.csv", index=False)
    held_prediction = kscn_model.state(held.eta_mV.to_numpy(), np.array(model["scaled_parameters"]))["current"]
    voltage_checks = {}
    for label, points, pars in [("KSCN_control_kinetics", control, parameters),
                                ("KSCN_held_out", held, np.array(model["scaled_parameters"]))]:
        eta_prediction = kscn_model.inverse(points.j_mA_cm2.to_numpy(), pars)
        rmse = float(np.sqrt(np.mean((eta_prediction - points.eta_mV.to_numpy()) ** 2)))
        saved = next(r for r in reference("D_PROVENANCE.json")["checks"] if r["label"] == label)
        assert len(points) == saved["n"]
        np.testing.assert_allclose(rmse, saved["rmse_mV"], atol=1e-9)
        voltage_checks[label + "_RMSE_mV"] = rmse
    return dict(NiFeP_points=61, NiFeP_shared_R_layer=shared["r_ohm_cm2"], NiFeP_inverse_layer_slope=slope,
                KSCN_scale=factor, KSCN_calibration_points=18, KSCN_heldout_points=22,
                KSCN_heldout_RMSE_mA_cm2=float(np.sqrt(np.mean((held_prediction - held.j_mA_cm2.to_numpy()) ** 2))),
                KSCN_kinetics_refitted=refit_kscn, **voltage_checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO / "build/figure5")
    parser.add_argument("--refit-kscn", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output == HERE or HERE in output.parents:
        raise ValueError("Generated outputs must be outside the analysis source directory")
    output.mkdir(parents=True, exist_ok=True)
    report = {}
    for panel, function in [("A", panel_a), ("B", panel_b), ("C", panel_c)]:
        report[panel] = function(output)
        print(f"Figure 5{panel}: reproduced and checked", flush=True)
    report["D"] = panel_d(output, args.refit_kscn)
    write_json(output / "RESULTS.json", report)
    print("Figure 5D: reproduced and checked", flush=True)


if __name__ == "__main__":
    main()
