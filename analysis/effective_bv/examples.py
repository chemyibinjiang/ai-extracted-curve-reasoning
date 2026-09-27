"""Compensation, cycle resistance, NiMo kinetics and current rescaling examples."""
import json
import os
from pathlib import Path
import sys
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ[key] = "1"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGE = ROOT / "analysis/figure5"
sys.path.insert(0, str(ROOT / "analysis/common"))
sys.path.insert(0, str(PACKAGE))
import numpy as np
import pandas as pd
import effective_bv as bv
import refit_nimo
import kscn_model
from compensation import panel_a


def read(name):
    return pd.read_csv(PACKAGE / "inputs" / name, float_precision="round_trip")


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def bubbles(out):
    native, eis = read("B_POLARIZATION.csv"), read("B_EIS_NATIVE_DATA.csv")
    prior = json.loads((PACKAGE / "reference/B_SEEDS.json").read_text())
    rows, lines, fits = [], [], []
    for cycle, g in native.groupby("cycle", sort=True):
        original = next(r for r in prior if r["cycle"] == cycle)
        start = bv.seed(original)
        pair = bv.fit_pair(g.j_mA_cm2.to_numpy(), g.eta_mV.to_numpy())
        fit = bv.fit(g.j_mA_cm2.to_numpy(), g.eta_mV.to_numpy(), True,
                     [start, bv.seed(pair["BV+jR"])])
        pair["BV+jR"] = fit
        assert fit["equivalent_converged"]
        arc = eis[eis.cycle.eq(cycle) & eis.minus_Zimag_ohm.between(1.4, 6)]
        co = np.polynomial.polynomial.polyfit(arc.minus_Zimag_ohm, arc.Zreal_ohm, 2)
        rows.append(dict(cycle=int(cycle), R_BVjR_ohm_cm2=fit["R"], Rs_EIS_ohm=float(co[0]),
                         alpha_c=fit["alpha_c"], alpha_a=fit["alpha_a"], rmse_mV=fit["rmse"]))
        for name, item in pair.items():
            fits.append(dict(cycle=int(cycle), model=name, **item))
            lines.append(g.assign(model=name, predicted_eta_mV=bv.predict(g.j_mA_cm2.to_numpy(), item)))
    table = pd.DataFrame(rows)
    slope, intercept = np.polyfit(table.Rs_EIS_ohm, table.R_BVjR_ohm_cm2, 1)
    pred = slope * table.Rs_EIS_ohm + intercept
    r2 = 1 - np.sum((pred - table.R_BVjR_ohm_cm2)**2) / np.sum((table.R_BVjR_ohm_cm2-table.R_BVjR_ohm_cm2.mean())**2)
    table.to_csv(out / "B_CYCLE_R.csv", index=False)
    pd.DataFrame(fits).to_csv(out / "B_FITS.csv", index=False)
    pd.concat(lines).to_csv(out / "B_PREDICTIONS.csv", index=False)
    return dict(cycles=rows, trend_slope=float(slope), trend_intercept=float(intercept), trend_r2=float(r2))


def layers(out):
    data = read("NiFeP_ORIGINAL_DATA.csv")
    excluded = read("NiFeP_EXCLUDED_DATA.csv")
    keys = ["curve_uid", "native_index"]
    bad = set(map(tuple, excluded[keys].to_numpy()))
    data = data.loc[[tuple(v) not in bad for v in data[keys].to_numpy()]].copy()
    assert len(data) == 61
    q, y = data.j_mA_cm2.to_numpy()/data.layers.to_numpy(), data.eta_mV.to_numpy()
    shared = bv.fit_pair(q, y)["BV+jR"]
    fits, predictions = [], []
    for n, g in data.groupby("layers", sort=True):
        q = g.j_mA_cm2.to_numpy()/n
        fit = bv.fit(q, g.eta_mV.to_numpy(), True, [bv.seed(shared)])
        assert fit["equivalent_converged"]
        fits.append(dict(layers=int(n), independent_R=fit["R"]/n, predicted_R=shared["R"]/n, **fit))
        predictions.append(g.assign(shared_eta_mV=bv.predict(q, shared), independent_eta_mV=bv.predict(q, fit)))
    table = pd.DataFrame(fits)
    x, y = 1/table.layers.to_numpy(), table.independent_R.to_numpy()
    slope = float(x@y/(x@x))
    table.to_csv(out / "D_NIFEP_FITS.csv", index=False)
    pd.concat(predictions).to_csv(out / "D_NIFEP_PREDICTIONS.csv", index=False)
    return dict(shared=shared, independent_fits=fits, inverse_layer_slope=slope,
                inverse_layer_rmse=float(np.sqrt(np.mean((y-slope*x)**2))), retained_points=61)


def kscn(out):
    data = read("KSCN_DATA.csv")
    model = json.loads((PACKAGE / "reference/KSCN_MODEL.json").read_text())
    p = np.array(model["parameters"])
    treated = data[data.curve.eq("kscn")].sort_values("prepared_index")
    cal, test = treated[treated.role.eq("scale_calibration")], treated[treated.role.eq("held_out")]
    j = kscn_model.state(cal.eta_mV.to_numpy(), p)["current"]
    factor = float(j@cal.j_mA_cm2.to_numpy()/(j@j))
    q = kscn_model.scaled_parameters(p, factor, "finite_volmer")
    np.testing.assert_allclose(factor, model["factor"], atol=1e-12)
    pred = kscn_model.inverse(test.j_mA_cm2.to_numpy(), q)
    test.assign(predicted_eta_mV=pred).to_csv(out / "D_KSCN_HELDOUT.csv", index=False)
    return dict(factor=factor, calibration_points=len(cal), heldout_points=len(test),
                heldout_rmse_mV=float(np.sqrt(np.mean((pred-test.eta_mV.to_numpy())**2))),
                action="Kinetic model unchanged; amplitude calibration and held-out predictions recomputed")


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    results = {"A": panel_a(output)}
    results["B"] = bubbles(output)
    dump(output / "RESULTS.json", results)
    print("Figure 5A accounting and 5B effective-BV cycle refits complete", flush=True)
    results["D_NiFeP"] = layers(output)
    results["D_KSCN"] = kscn(output)
    dump(output / "RESULTS.json", results)
    print("Figure 5D shared/independent layer refits and KSCN replay complete", flush=True)
    results["C"] = refit_nimo.run(output / "nimo", starts=64, checks=True, plot=True, empirical_backend=bv)
    dump(output / "RESULTS.json", results)
    print("Figure 5C: both empirical fits, VHT, coverage, CV and window checks complete", flush=True)
