"""Portable entry points for current Figure 6, keeping outputs outside sources.

replay: re-profile scales against the published templates, replay the selected
VHT solutions, recalibrate current amplitudes, and recompute rate controls.
discover/refit: rerun the original searches, not merely the frozen summaries.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def prepare_published_library():
    import numpy as np
    import pandas as pd
    import empirical
    from paths import EMPIRICAL_OUT, INPUTS, REFERENCE

    results = []
    for condition, (folder, upper) in empirical.CONDITIONS.items():
        target = EMPIRICAL_OUT / condition
        target.mkdir(parents=True, exist_ok=True)
        full = pd.read_csv(INPUTS / folder / "cohort_all_points.csv")
        templates = pd.read_csv(REFERENCE / condition / "TEMPLATES.csv")
        expected = pd.read_csv(REFERENCE / condition / "ASSIGNMENTS.csv", float_precision="round_trip").set_index("curve_uid")
        summary = json.loads((REFERENCE / condition / "RESULT.json").read_text())
        cuts = {uid: g[g.eta_mV.between(0, upper)].sort_values(["j_mA_cm2", "fit_point_index"])
                for uid, g in full.groupby("curve_uid")}
        eligible = {uid: g for uid, g in cuts.items() if len(g) >= 5 and g.eta_mV.var(ddof=0) > 1e-20}
        assert len(cuts) == summary["n_cohort"] and len(eligible) == summary["n_eligible"]
        assert set(eligible) == set(expected.index)
        tables = {r.family: empirical.model.table(r.alpha) for r in templates.itertuples()}
        rows, points = [], []
        for uid in sorted(eligible):
            group = eligible[uid]
            j, eta = group.j_mA_cm2.to_numpy(), group.eta_mV.to_numpy()
            resistance = float(np.clip(j @ eta / (j @ j), 0, 100))
            linear = empirical.metrics(eta, resistance * j)
            saved = expected.loc[uid]
            if empirical.passes(linear):
                row = dict(saved)
                row.update(beta=1 / resistance, R_ohm_cm2=resistance, **linear)
                prediction = resistance * j
                assert saved.kind == "linear"
            else:
                alternatives = []
                for template in templates.itertuples():
                    values, derivatives = tables[template.family]
                    z, _ = empirical.model.profile(j, np.log(j), eta, template.alpha, template.Q_mV, values, derivatives)
                    beta = float(10 ** (z / empirical.model.LN10))
                    prediction = empirical.model.predict(j, template.alpha, template.Q_mV, z / np.log(10))
                    score = empirical.metrics(eta, prediction)
                    alternatives.append((score["RMSE_mV"], template.candidate_index, template.family, beta, prediction, score))
                _, _, family, beta, prediction, score = min(alternatives, key=lambda item: item[:2])
                assert family == saved.family and empirical.passes(score) == bool(saved.adequate)
                row = dict(saved)
                row.update(beta=beta, **score)
            np.testing.assert_allclose(row["beta"], saved.beta, rtol=1e-9, atol=1e-10)
            np.testing.assert_allclose(row["R2"], saved.R2, atol=1e-10)
            row["curve_uid"] = uid
            rows.append(row)
            pp = group.copy()
            for key in ("condition", "kind", "family", "adequate", "beta"):
                pp[key] = row[key]
            pp["x"], pp["empirical_prediction_mV"] = j / row["beta"], prediction
            points.append(pp)
        assignments, predictions = pd.DataFrame(rows), pd.concat(points, ignore_index=True)
        nonlinear = assignments[assignments.adequate & assignments.kind.eq("BV+jR")]
        assert len(nonlinear) == summary["nonlinear_covered"]
        for row in templates.itertuples():
            group = predictions[predictions.family.eq(row.family) & predictions.adequate]
            assert group.curve_uid.nunique() == row.n_curves
            np.testing.assert_allclose([group.x.min(), group.x.max()], [row.x_min, row.x_max], rtol=1e-9)
        templates.to_csv(target / "TEMPLATES.csv", index=False)
        assignments.to_csv(target / "ASSIGNMENTS.csv", index=False)
        predictions.to_csv(target / "POINT_PREDICTIONS.csv", index=False)
        summary["coverage_search_rerun"] = False
        summary["mode"] = "All original in-window observations replayed against the published library; scales re-profiled"
        empirical.dump(target / "RESULT.json", summary)
        results.append(summary)
        print(f"{condition}: {len(nonlinear)} nonlinear passes; original point support and family assignment verified", flush=True)
    (EMPIRICAL_OUT / "VHT_SELECTED.json").write_bytes((REFERENCE / "VHT_SELECTED.json").read_bytes())
    return results


def replay_kinetics():
    import pandas as pd
    import kinetic
    import koh_kinetic
    from paths import REFERENCE, EMPIRICAL_OUT, KOH_OUT
    acid = json.loads((REFERENCE / "VHT_SELECTED.json").read_text())["acid_kinetics_only"]
    kinetic.replay({"acid_kinetics_only": acid})
    koh_kinetic.evaluate(json.loads((REFERENCE / "KOH_SELECTED.json").read_text()))
    ac = pd.read_csv(EMPIRICAL_OUT / "VHT_RAW_CURVE_REPLAY.csv")
    base = pd.read_csv(KOH_OUT / "RAW_CURVE_REPLAY.csv")
    assert len(ac) == 59 and int(ac.pass_R2.sum()) == 48
    assert len(base) == 195 and int(base.pass_R2.sum()) == 174
    return dict(acid_empirical_passes=59, acid_VHT_passes=48,
                KOH_empirical_passes=195, KOH_VHT_passes=174)


def controls():
    import numpy as np
    import pandas as pd
    from paths import PACKAGE, OUTPUT, EMPIRICAL_OUT, KOH_OUT, REPO
    sys.path.insert(0, str(PACKAGE / "vendor/vht"))
    import control_core as core
    rows = []
    for condition, parameter_path, grid_path, upper in [
        ("acid", EMPIRICAL_OUT / "VHT_FAMILY_PARAMETERS.csv", EMPIRICAL_OUT / "VHT_TEMPLATE_RECONSTRUCTION.csv", 200),
        ("KOH", KOH_OUT / "FAMILY_PARAMETERS.csv", KOH_OUT / "TEMPLATE_RECONSTRUCTION.csv", 300),
    ]:
        parameters = pd.read_csv(parameter_path, float_precision="round_trip")
        grid = pd.read_csv(grid_path, float_precision="round_trip")
        for row in parameters.itertuples():
            support = grid[grid.family.eq(row.family)].vht_eta_mV
            lo, hi = support.min(), support.max()
            for voltage in (50, 100, 150):
                np.testing.assert_allclose(core.state(row, voltage), core.independent_state(row, voltage, np.zeros(3)), rtol=1e-8, atol=1e-10)
            for voltage in np.arange(1, upper + 0.25, 0.5):
                result = core.rate_control(row, voltage)
                np.testing.assert_allclose(result.sum(), 1, atol=1e-6)
                rows.append(dict(condition=condition, family=row.family, eta_mV=voltage,
                    inside_fitted_support=bool(lo <= voltage <= hi), fitted_support_min_mV=lo,
                    fitted_support_max_mV=hi, theta_H=core.state(row, voltage)[1],
                    X_V=result[0], X_H=result[1], X_T=result[2]))
    family = pd.DataFrame(rows)
    family.to_csv(OUTPUT / "RATE_CONTROL_FAMILY_GRID.csv", index=False)
    frozen = pd.read_csv(REPO / "analysis/figure6/expected/RATE_CONTROL_FAMILY_GRID.csv", float_precision="round_trip")
    keys = ["condition", "family", "eta_mV"]
    actual = family.set_index(keys).sort_index()
    frozen = frozen.set_index(keys).sort_index()
    pd.testing.assert_index_equal(actual.index, frozen.index)
    for column in ["theta_H", "X_V", "X_H", "X_T", "fitted_support_min_mV", "fitted_support_max_mV"]:
        np.testing.assert_allclose(actual[column], frozen[column], atol=1e-9, rtol=1e-9)
    np.testing.assert_array_equal(actual.inside_fitted_support, frozen.inside_fitted_support)
    means = []
    for (condition, eta), group in family.groupby(["condition", "eta_mV"], sort=True):
        item = dict(condition=condition, eta_mV=eta, n_families=len(group),
                    all_families_supported=bool(group.inside_fitted_support.all()),
                    n_families_supported=int(group.inside_fitted_support.sum()),
                    common_support_min_mV=float(group.fitted_support_min_mV.max()),
                    common_support_max_mV=float(group.fitted_support_max_mV.min()))
        for step in ("V", "H", "T"):
            item[f"X_{step}_mean"] = group[f"X_{step}"].mean()
            item[f"X_{step}_sd"] = group[f"X_{step}"].std(ddof=1)
        means.append(item)
    pd.DataFrame(means).to_csv(OUTPUT / "RATE_CONTROL_MEAN_SD.csv", index=False)
    sys.path.insert(0, str(REPO / "scripts"))
    from validate_figures import load_tables, validate_science
    import csv
    tables = load_tables(REPO)
    for name in ("RATE_CONTROL_FAMILY_GRID", "RATE_CONTROL_MEAN_SD"):
        with (OUTPUT / f"{name}.csv").open(newline="") as stream:
            tables[name] = list(csv.DictReader(stream))
    report = validate_science(tables)
    print("Rate controls regenerated from kinetic parameters and checked against all published family/mean crossings", flush=True)
    return report


def check_refit():
    import numpy as np
    import pandas as pd
    from paths import OUTPUT, REFERENCE, EMPIRICAL_OUT, KOH_OUT
    report = {}
    for condition, generated, reference, key, summary, summary_key in [
        ("acid", EMPIRICAL_OUT / "VHT_SELECTED.json", REFERENCE / "VHT_SELECTED.json", "acid_kinetics_only",
         EMPIRICAL_OUT / "VHT_SUMMARY.csv", "acid_kinetics_only"),
        ("KOH", KOH_OUT / "SELECTED_MODELS.json", REFERENCE / "KOH_SELECTED.json", "DeltaG_T",
         KOH_OUT / "SUMMARY.csv", "DeltaG_T"),
    ]:
        actual = json.loads(generated.read_text())[key]
        expected = json.loads(reference.read_text())[key]
        params = np.asarray(actual["params"])
        errors = np.asarray(actual["family_RMSE_mV"])
        assert np.isfinite(params).all() and np.isfinite(errors).all()
        metrics = pd.read_csv(summary).set_index("model").loc[summary_key]
        report[condition] = dict(parameters_match_reference=bool(np.allclose(params, expected["params"], rtol=1e-7, atol=1e-7)),
            family_errors_match_reference=bool(np.allclose(errors, expected["family_RMSE_mV"], rtol=1e-7, atol=1e-7)),
            pooled_template_RMSE_mV=float(np.sqrt(np.mean(errors**2))),
            raw_curve_R2_passes=int(metrics.refit_beta_pass))
    (OUTPUT / "REFIT_CHECKS.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("replay", "discover", "refit", "controls"), nargs="?", default="replay")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.output:
        os.environ["FIGURE6_OUTPUT"] = str(args.output.resolve())
    from paths import PACKAGE, OUTPUT
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[key] = "1"
    if args.stage == "discover":
        subprocess.run([sys.executable, str(PACKAGE / "empirical.py")], check=True)
        import pandas as pd
        from paths import EMPIRICAL_OUT, REFERENCE
        checks = {}
        for condition in ("acid", "KOH"):
            actual = pd.read_csv(EMPIRICAL_OUT / condition / "COVERAGE_SCAN.csv")
            frozen = pd.read_csv(REFERENCE / condition / "COVERAGE_SCAN.csv")
            columns = ["K_BV", "nonlinear_denominator", "covered", "certified_count"]
            pd.testing.assert_frame_equal(actual[columns], frozen[columns])
            actual_templates = pd.read_csv(EMPIRICAL_OUT / condition / "TEMPLATES.csv")
            frozen_templates = pd.read_csv(REFERENCE / condition / "TEMPLATES.csv")
            columns = ["family", "candidate_index", "n_curves"]
            checks[condition] = dict(coverage_scan_matches=True,
                selected_representatives_match=actual_templates[columns].equals(frozen_templates[columns]))
        (OUTPUT / "DISCOVERY_CHECKS.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(checks, indent=2), flush=True)
    elif args.stage == "refit":
        prepare_published_library()
        subprocess.run([sys.executable, str(PACKAGE / "kinetic.py"), "--workers", str(args.workers)], check=True)
        subprocess.run([sys.executable, str(PACKAGE / "koh_kinetic.py"), "--workers", str(args.workers)], check=True)
        check_refit()
    elif args.stage == "controls":
        controls()
    else:
        prepare_published_library()
        kinetic = replay_kinetics()
        report = controls()
        report.update(kinetic, empirical_search_rerun=False, kinetic_parameters_refitted=False,
                      current_scales_reoptimized=True, controls_recomputed_from_parameters=True)
        (OUTPUT / "REPLAY_CHECKS.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
