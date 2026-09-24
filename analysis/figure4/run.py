"""Recompute Figure 4 statistics and local derivatives from digitized curves.

The default verifies the supplied fit parameters on every original point.
The refit stage optimizes BV and BV+jR again and writes separate fit results.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import os
from pathlib import Path
import sys
import time

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(key, "1")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "common"))
import numpy as np
import pandas as pd
import strict_bv as bv
from local_slopes import curve_derivatives, polynomial_operator
from weights import pw, quant
from prepare import prepare

WINDOWS = [(0, 25), (25, 50), (50, 100), (100, 150), (150, 200), (200, 300), (300, 400), (400, 500)]
EXAMPLES = {
    "batch8/case1831/figure_5__panel_a/curve_2": "20 wt% Pt/C",
    "batch8/case1792/figure_6__panel_a/curve_2": "N-Ni",
    "batch0/case44/figure_4__panel_a/curve_2": "WO3",
}


def read(path):
    return pd.read_csv(path, float_precision="round_trip", low_memory=False)


def check_table(actual, filename):
    expected = read(HERE / "reference" / filename)
    pd.testing.assert_frame_equal(actual[expected.columns].reset_index(drop=True), expected,
        check_dtype=False, check_exact=False, rtol=1e-9, atol=1e-8)


def prediction(j, row, prefix):
    return bv.A_STAR_MV * bv.strict_bv_x(j / np.exp(row[prefix + "_log_j0"]), row[prefix + "_alpha"]) + row[prefix + "_r_mV_per_mA"] * j


def distributions(fits, output):
    accepted = fits[fits.bvir_fit_ok & fits.bvir_r2.ge(.99)]
    assert len(accepted) == 2351 and accepted.paper_key.nunique() == 460
    fields = ["bvir_b_tafel_mV_dec", "bvir_r_mV_per_mA", "bvir_j0_mA"]
    bins = [np.arange(20, 225, 5), np.linspace(0, 5, 51), np.logspace(-8, 3, 45)]
    summaries, histograms = [], []
    for field, edges in zip(fields, bins):
        values = accepted[field].to_numpy()
        q = np.quantile(values, [0, .05, .25, .5, .75, .95, 1])
        summaries.append(dict(parameter=field, n=len(values), **dict(zip(["min", "p05", "q25", "median", "q75", "p95", "max"], q))))
        counts, _ = np.histogram(values, edges)
        assert counts.sum() + (values < edges[0]).sum() + (values > edges[-1]).sum() == len(values)
        histograms.extend(dict(parameter=field, left=a, right=b, count=int(n), percent=100*n/len(values))
                          for a, b, n in zip(edges[:-1], edges[1:], counts))
    for records, filename in [(summaries, "PARAMETER_SUMMARY.csv"), (histograms, "PARAMETER_HISTOGRAM_BINS.csv")]:
        frame = pd.DataFrame(records)
        check_table(frame, filename)
        frame.to_csv(output / filename, index=False)
    return dict(curves=len(accepted), papers=int(accepted.paper_key.nunique()),
                medians={r["parameter"]: float(r["median"]) for r in summaries})


def analyse(metadata, points, fits, output):
    groups = {uid: g.sort_values("native_index") for uid, g in points.groupby("curve_uid")}
    assert set(groups) == set(metadata.curve_uid) == set(fits.index)
    assert len(fits) == 3033 and metadata.paper_key.nunique() == 473
    assert metadata.canonical_fit_eligible.all() and metadata.j_max_mA.ge(20).all()
    rows, metric_rows, curve_points = [], [], []
    for number, (uid, row) in enumerate(fits.iterrows(), 1):
        group = groups[uid]
        j, eta = group.j.to_numpy(), group.eta_mV.to_numpy()
        assert len(j) == row.fit_point_count and group.paper_key.eq(row.paper_key).all()
        assert (j >= .2).all() and (j <= 500).all() and (eta >= 0).all() and (eta <= 2000).all()
        np.testing.assert_allclose([j.min(), j.max(), eta.min(), eta.max()],
            row[["j_min_mA", "j_max_mA", "y_min_mV", "y_max_mV"]].to_numpy(float), atol=1e-8)
        model = {"BV": prediction(j, row, "bv"), "BVjR": prediction(j, row, "bvir")}
        model["jR"] = row.bvir_r_mV_per_mA * j
        model["base"] = model["BVjR"] - model["jR"]
        metrics = dict(curve_uid=uid, paper_key=row.paper_key)
        for label, prefix in [("BV", "bv"), ("BVjR", "bvir")]:
            assert row[prefix + "_fit_ok"] and row[prefix + "_e_offset_mV"] == 0
            sse = float(np.sum((eta - model[label]) ** 2))
            rmse, r2 = np.sqrt(sse / len(j)), bv.r2_from_sse(eta, sse)
            np.testing.assert_allclose([sse, rmse, r2], row[[prefix + "_sse_mV2", prefix + "_rmse_mV", prefix + "_r2"]].to_numpy(float), rtol=1e-9, atol=1e-7)
            metrics.update({label + "_R2": r2, label + "_rmse": rmse})
        metric_rows.append(metrics)
        for item in curve_derivatives(j, eta, 9, 2):
            item.update(curve_uid=uid, paper_key=row.paper_key)
            if item["status"] == "eligible":
                indices = np.arange(item["left_index"], item["right_index"] + 1)
                operator, *_ = polynomial_operator(np.log10(j[indices]), np.log10(j[item["native_index"]]), 2)
                item.update({key: float(operator @ value[indices]) for key, value in model.items()})
                item["observed"] = item["slope_mV_dec"]
                np.testing.assert_allclose(item["BVjR"], item["base"] + item["jR"], atol=1e-8)
            rows.append(item)
        if uid in EXAMPLES:
            curve_points.append(group.assign(display_label=EXAMPLES[uid], **model))
        if number % 1000 == 0:
            print(f"Verified fits and recomputed local slopes: {number}/3033", flush=True)
    metrics = pd.DataFrame(metric_rows)
    summaries = []
    for label, count in [("BV", 806), ("BVjR", 2351)]:
        passes = metrics[label + "_R2"].ge(.99)
        assert int(passes.sum()) == count
        item = dict(model=label, curves=3033, papers=473, R2_ge_099_count=count, R2_ge_099_percent=100*passes.mean())
        for key in ("R2", "rmse"):
            item.update({key + "_" + name: metrics[label + "_" + key].quantile(q)
                for q, name in [(.05, "p05"), (.25, "p25"), (.5, "median"), (.75, "p75"), (.95, "p95")]})
        summaries.append(item)
    check_table(pd.DataFrame(summaries), "CORPUS_FIT_METRIC_SUMMARY.csv")
    metrics.to_csv(output / "FIT_METRICS.csv", index=False)
    pd.DataFrame(summaries).to_csv(output / "CORPUS_FIT_METRIC_SUMMARY.csv", index=False)
    support = pd.DataFrame(rows)
    flow = support.groupby("status").agg(points=("native_index", "size"), curves=("curve_uid", "nunique")).reset_index()
    check_table(flow, "DERIVATIVE_SUPPORT_FLOW.csv")
    flow.to_csv(output / "DERIVATIVE_SUPPORT_FLOW.csv", index=False)
    local = support[support.status.eq("eligible") & support.eta_mV.ge(0) & support.eta_mV.lt(500)]
    local.to_csv(output / "LOCAL_SLOPES.csv", index=False)
    windows, histograms, window_summaries = [], [], []
    edges = np.arange(-50, 2005, 5)
    for lo, hi in WINDOWS:
        group = local[local.eta_mV.ge(lo) & local.eta_mV.lt(hi)]
        cw = group.groupby(["curve_uid", "paper_key"]).agg(slope=("observed", "median"), derivative_centers=("native_index", "size")).reset_index()
        cw["window"], cw["eta_lo"], cw["eta_hi"] = f"{lo}-{hi}", lo, hi
        windows.append(cw)
        weights = pw(cw)
        counts = np.histogram(cw.slope, bins=edges, weights=weights)[0]
        histograms.extend(dict(window=f"{lo}-{hi}", origin=0, left=a, right=b, mass=v) for a, b, v in zip(edges[:-1], edges[1:], counts))
        window_summaries.append(dict(window=f"{lo}-{hi}", parent_curves=3033, parent_papers=473,
            curves=len(cw), papers=cw.paper_key.nunique(), derivatives=int(cw.derivative_centers.sum()),
            **dict(zip(["p05", "p25", "median", "p75", "p95"], quant(cw.slope, weights, (.05, .25, .5, .75, .95)))),
            fraction_below_display=float(weights @ cw.slope.lt(-10)), fraction_above_display=float(weights @ cw.slope.gt(400)),
            fraction_outside_histogram=float(weights @ (cw.slope.lt(edges[0]) | cw.slope.gt(edges[-1])))))
    for data, name in [(histograms, "HISTOGRAMS.csv"), (window_summaries, "WINDOW_SUMMARY.csv")]:
        frame = pd.DataFrame(data)
        check_table(frame, name)
        frame.to_csv(output / name, index=False)
    pd.concat(windows).to_csv(output / "CURVE_WINDOW_SLOPES.csv", index=False)
    pd.concat(curve_points).to_csv(output / "EXAMPLE_CURVES.csv", index=False)
    local[local.curve_uid.isin(EXAMPLES)].to_csv(output / "EXAMPLE_SLOPES.csv", index=False)
    return dict(curves=3033, papers=473, original_points=len(points), BV_passes=806, BVjR_passes=2351,
                local_derivative_centers=len(local), reference_fits_verified=True, fit_parameters_reoptimized=False,
                local_derivatives_recomputed=True, parameters=distributions(fits, output))


def fit_curve(job):
    uid, j, eta = job
    result = {"curve_uid": uid}
    for prefix, include_r in [("bv", False), ("bvir", True)]:
        fit = bv.fit_variant(j, eta, include_ir=include_r, include_offset=False, current={})
        result.update({prefix + "_" + key: value for key, value in fit.items()})
    return result


def check_refit(results, reference, points, output):
    if not results.curve_uid.is_unique:
        raise ValueError("Duplicate refitted curve IDs")
    results = results.set_index("curve_uid").sort_index()
    assert set(results.index) == set(points.curve_uid)
    reference = reference.loc[results.index]
    report = dict(curves=len(results), model_fits=2*len(results), models={})
    groups = {uid: group for uid, group in points.groupby("curve_uid")}
    for prefix in ("bv", "bvir"):
        assert results[prefix + "_ok"].all()
        assert results[prefix + "_error"].fillna("").eq("").all()
        assert results[prefix + "_e_offset_mV"].eq(0).all()
        # Compare both recalculated objectives and pass assignments, not just
        # coefficients: weakly identified parameters can differ between fits.
        for uid, row in results.iterrows():
            group = groups[uid]
            sse = float(np.sum((group.eta_mV.to_numpy() - prediction(group.j.to_numpy(), row, prefix)) ** 2))
            np.testing.assert_allclose([sse, np.sqrt(sse / len(group)), bv.r2_from_sse(group.eta_mV.to_numpy(), sse)],
                row[[prefix + "_sse_mV2", prefix + "_rmse_mV", prefix + "_r2"]].to_numpy(float), rtol=1e-8, atol=1e-7)
        new_rmse = results[prefix + "_rmse_mV"].to_numpy(float)
        old_rmse = reference[prefix + "_rmse_mV"].to_numpy(float)
        np.testing.assert_allclose(new_rmse, old_rmse, rtol=1e-6, atol=1e-6)
        np.testing.assert_allclose(results[prefix + "_r2"], reference[prefix + "_r2"], rtol=1e-6, atol=1e-8)
        new_pass = results[prefix + "_r2"].ge(.99)
        old_pass = reference[prefix + "_r2"].ge(.99)
        assert new_pass.equals(old_pass)
        report["models"][prefix] = dict(successful_fits=len(results), R2_ge_099=int(new_pass.sum()),
            pass_assignment_changes=int((new_pass != old_pass).sum()),
            max_abs_rmse_difference_mV=float(np.max(np.abs(new_rmse - old_rmse))))
    report["reference_objectives_reproduced"] = True
    (output / "REFIT_CHECKS.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", choices=("prepare", "analyse", "refit"), default="analyse")
    parser.add_argument("--output", type=Path, default=ROOT / "build/figure4")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--curve", help="Refit only this curve UID; omit to refit the complete cohort")
    args = parser.parse_args()
    output = args.output.resolve()
    if output == HERE or HERE in output.parents:
        raise ValueError("Write results outside the analysis source directory")
    if args.curve and args.stage != "refit":
        parser.error("--curve applies only to refit")
    output.mkdir(parents=True, exist_ok=True)
    preparation = prepare(output)
    if args.stage == "prepare":
        print(json.dumps(preparation, indent=2))
        return
    metadata, points = read(output / "PREPARED_CURVES.csv"), read(output / "PREPARED_POINTS.csv")
    fits = metadata.merge(read(HERE / "reference/FIT_PARAMETERS.csv"), on="curve_uid", validate="one_to_one").set_index("curve_uid")
    if args.stage == "refit":
        if args.curve:
            if args.curve not in set(points.curve_uid):
                parser.error("Unknown curve UID")
            points = points[points.curve_uid.eq(args.curve)]
        jobs = [(uid, g.j.to_numpy(), g.eta_mV.to_numpy()) for uid, g in points.groupby("curve_uid", sort=False)]
        start, rows = time.monotonic(), []
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(fit_curve, job): job[0] for job in jobs}
            for future in as_completed(futures):
                rows.append(future.result())
                if len(rows) % 100 == 0 or len(rows) == len(jobs):
                    pd.DataFrame(rows).sort_values("curve_uid").to_csv(output / "REFITTED_PARAMETERS.csv", index=False)
                    print(f"Refitted {len(rows)}/{len(jobs)} curves in {time.monotonic()-start:.1f} s", flush=True)
        failed = [r["curve_uid"] for r in rows if any(not r.get(p + "_ok") or r.get(p + "_error") for p in ("bv", "bvir"))]
        (output / "REFIT_RUN.json").write_text(json.dumps(dict(curves=len(rows), model_fits=2*len(rows),
            failed_curve_ids=failed, elapsed_seconds=time.monotonic()-start, workers=args.workers), indent=2) + "\n", encoding="utf-8")
        if failed:
            raise RuntimeError(f"{len(failed)} curves contain unsuccessful fits; all results are retained for inspection")
        report = check_refit(pd.DataFrame(rows), fits, points, output)
        print(json.dumps(report, indent=2))
        print(f"Refitted {len(rows)} curves; results kept separate from figure reference parameters")
    else:
        report = analyse(metadata, points, fits, output)
        (output / "CHECKS.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
