"""Compare BV, BV+jR and resistance-free VHT against identical NiMo data.

Run from any directory. Outputs reproduce the Figure 5C analysis, not an
overwrite of the manually finalized manuscript artwork or source-paper fits.
"""
import argparse
import hashlib
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
import scipy
import strict_bv as bv
import nimo_vht as vht


def empirical(current, voltage):
    fits = {}
    for name, include_ir in [("BV", False), ("BV+jR", True)]:
        fit = bv.fit_variant(current, voltage, include_ir=include_ir, include_offset=False, current={})
        if not fit["ok"] or fit["error"]:
            raise RuntimeError(f"{name}: {fit}")
        fits[name] = fit
    return fits


def predict(current, fit):
    return bv.predict_variant(np.asarray(current),
        np.array([fit["log_j0"], fit["alpha"], fit["r_mV_per_mA"]]),
        include_ir=True, include_offset=False)


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run(output, starts=64, checks=True, plot=True):
    output = Path(output).resolve()
    protected = [HERE.parent.resolve(), (REPO / "figures").resolve()]
    if any(output == p or p in output.parents for p in protected):
        raise ValueError("Use an output directory outside analysis/ and figures/")
    output.mkdir(parents=True, exist_ok=True)
    source = HERE / "inputs/C_PRIMARY_DATA.csv"
    data = pd.read_csv(source, float_precision="round_trip")
    data = data[data.source.eq("figure4_experiment")].sort_values("J_mA_cm2").reset_index(drop=True)
    assert len(data) == 40 and data.J_mA_cm2.between(2, 24).all()
    current, voltage = data.J_mA_cm2.to_numpy(), data.U_mV.to_numpy()
    empirical_fits = empirical(current, voltage)
    kinetic = vht.fit(current, voltage, starts=starts)
    best = kinetic["best"]
    p = vht.increasing_branch(best["parameters"], voltage)
    symmetry_p = vht.mirror(p)
    eta = np.linspace(voltage.min(), voltage.max(), 241)
    states = vht.forward(eta, p)
    symmetric = vht.forward(eta, symmetry_p)
    np.testing.assert_allclose(states["current"], symmetric["current"], rtol=1e-8, atol=1e-9)
    np.testing.assert_allclose(states["theta"] + symmetric["theta"], 1., atol=1e-10)
    balance = states["V"] - states["H"] - 2 * states["T"]
    assert np.max(abs(balance) / states["current"]) < 1e-7
    np.testing.assert_allclose(vht.inverse(states["current"], p), eta, atol=1e-7)
    coverage = pd.DataFrame(dict(eta_mV=eta, theta=states["theta"], theta_mirror=symmetric["theta"],
        j_mA_cm2=states["current"], V_current_equivalent=states["V"],
        H_current_equivalent=states["H"], T_current_equivalent=states["T"]))
    # These optimizer solutions are a sensitivity set, not posterior samples or a CI.
    accepted = [r for r in kinetic["starts"] if r["success"] and
                r["SSE_mV2"] <= best["SSE_mV2"] * 1.01 + 1e-8]
    alternative_theta = np.array([vht.forward(eta,
        vht.increasing_branch(r["parameters"], voltage))["theta"] for r in accepted])
    coverage["near_optimum_min"] = alternative_theta.min(axis=0)
    coverage["near_optimum_max"] = alternative_theta.max(axis=0)
    coverage.to_csv(output / "C_NIMO_PREDICTED_COVERAGE.csv", index=False)

    predictions, metrics = {}, []
    for name, count in [("BV", 2), ("BV+jR", 3), ("VHT", 4)]:
        predictions[name] = (vht.inverse(current, p) if name == "VHT"
                             else predict(current, empirical_fits[name]))
        metrics.append(dict(model=name, n=len(current), free_parameters=count,
                            **vht.metrics(voltage, predictions[name])))
        data[name + "_eta_mV"] = predictions[name]
    data.to_csv(output / "C_NIMO_FIT_POINTS.csv", index=False)
    pd.DataFrame(metrics).to_csv(output / "C_NIMO_METRICS.csv", index=False)
    grid = np.geomspace(current.min(), current.max(), 301)
    lines = pd.DataFrame(dict(j_mA_cm2=grid))
    for name in predictions:
        lines[name + "_eta_mV"] = vht.inverse(grid, p) if name == "VHT" else predict(grid, empirical_fits[name])
    lines.to_csv(output / "C_NIMO_FIT_LINES.csv", index=False)
    dump(output / "C_NIMO_MULTISTART.json", kinetic)
    print("Full-data RMSE (mV): " + ", ".join(f"{r['model']}={r['RMSE_mV']:.6f}" for r in metrics), flush=True)

    diagnostics = {}
    if checks:
        substarts = max(8, starts // 4)
        vh = vht.fit(current, voltage, starts=substarts, initial=best["parameters"], tafel=False)
        wider = vht.fit(current, voltage, starts=substarts, initial=best["parameters"],
            bounds=(np.array([-7., -7., -4., -8.]), np.array([7., 7., 4., 8.])))
        diagnostics["VH_limit"] = vh["best"]
        diagnostics["wider_bounds"] = dict(best=wider["best"], bounds=wider["bounds"],
            max_prediction_change_mV=float(np.max(abs(vht.inverse(current, wider["best"]["parameters"])
                                                      - predictions["VHT"]))))
        dump(output / "C_NIMO_LIMIT_CHECKS.json", dict(VH=vh, wider_bounds=wider))
        cv_rows, window_rows = [], []
        for fold in range(5):
            test = np.arange(len(current)) % 5 == fold
            ef = empirical(current[~test], voltage[~test])
            # No full-data fitted parameters enter a held-out fit.
            vf = vht.fit(current[~test], voltage[~test], starts=substarts, seed=20260924 + fold)
            for name in predictions:
                pred = (vht.inverse(current[test], vf["best"]["parameters"]) if name == "VHT"
                        else predict(current[test], ef[name]))
                for idx, value in zip(np.flatnonzero(test), pred):
                    cv_rows.append(dict(fold=fold, index=int(idx), model=name,
                        observed_eta_mV=float(voltage[idx]), predicted_eta_mV=float(value)))
        cv = pd.DataFrame(cv_rows)
        cv.to_csv(output / "C_NIMO_CROSS_VALIDATION.csv", index=False)
        diagnostics["interleaved_5fold_RMSE_mV"] = {name: float(np.sqrt(np.mean(
            (group.predicted_eta_mV - group.observed_eta_mV)**2))) for name, group in cv.groupby("model")}
        for lower, upper in [(3., 24.), (5., 24.), (2., 15.)]:
            use = (current >= lower) & (current <= upper)
            ef = empirical(current[use], voltage[use])
            vf = vht.fit(current[use], voltage[use], starts=substarts, seed=20260930)
            for name in predictions:
                pred = (vht.inverse(current[use], vf["best"]["parameters"]) if name == "VHT"
                        else predict(current[use], ef[name]))
                window_rows.append(dict(requested_j_min=lower, requested_j_max=upper,
                    actual_j_min=float(current[use].min()), actual_j_max=float(current[use].max()),
                    model=name, n=int(use.sum()), **vht.metrics(voltage[use], pred)))
        pd.DataFrame(window_rows).to_csv(output / "C_NIMO_WINDOW_CHECKS.csv", index=False)
        print("Held-out RMSE (mV): " + str(diagnostics["interleaved_5fold_RMSE_mV"]), flush=True)

    report = dict(source_doi="10.1002/celc.202001436", source_file="analysis/figure5/inputs/C_PRIMARY_DATA.csv",
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), selected_source="figure4_experiment",
        sample="223 nm electrodeposited NiMo; 0.5 M H2SO4; source-paper iR-corrected LSV",
        n=40, current_range_mA_cm2=[float(current.min()), float(current.max())],
        voltage_range_mV=[float(voltage.min()), float(voltage.max())],
        objective="Unweighted voltage-space least squares on identical digitized experimental points",
        BV_convention="n_eff=2; effective alpha fitted; not an elementary-step transfer coefficient",
        VHT_convention="One-electron V/H steps; alphaV=alphaH=0.5; detailed balance; no resistance or offset",
        empirical_fits=empirical_fits, metrics=metrics, VHT_best=best,
        representative_parameters=p.tolist(), mirrored_parameters=symmetry_p.tolist(),
        parameter_order=list(vht.PARAMETERS), theta_source="Calculated from independently fitted VHT parameters",
        near_optimum_rule="Converged starts within 1% of best SSE; increasing branch; not a confidence interval",
        near_optimum_starts=len(accepted),
        maximum_near_optimum_theta_spread=float(np.max(alternative_theta.max(axis=0)-alternative_theta.min(axis=0))),
        maximum_relative_balance_error=float(np.max(abs(balance) / states["current"])),
        diagnostics=diagnostics, versions=dict(python=sys.version.split()[0], numpy=np.__version__,
                                             scipy=scipy.__version__, pandas=pd.__version__),
        limitations=["These are digitized points from one published curve, not independent replicate measurements.",
            "Cross-validation tests interpolation within this curve, not external validation or unique mechanism identification.",
            "A good kinetics-only fit demonstrates compatibility; it does not exclude residual physical resistance.",
            "The exact V/H parameter symmetry produces the same polarization with complementary coverage.",
            "A rate ratio at its bound indicates a kinetic limit, not a measured microscopic rate constant.",
            "Fit and coverage are new calculations, not reproduction of the source authors' fitted parameters."])
    dump(output / "C_NIMO_REPORT.json", report)
    if plot:
        draw(output, data, lines, coverage, report)
    return report


def draw(output, data, lines, coverage, report):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "Arial", "font.size": 10, "axes.labelweight": "bold",
        "axes.titleweight": "bold", "axes.spines.top": False, "axes.spines.right": False,
        "svg.fonttype": "none", "pdf.fonttype": 42})
    colors = {"BV": "#1675cb", "BV+jR": "#e63957", "VHT": "#008c79"}
    errors = {r["model"]: r["RMSE_mV"] for r in report["metrics"]}
    fig, axes = plt.subplots(1, 3, figsize=(11.8, 3.5), layout="constrained")
    for ax, names in zip(axes[:2], [("BV", "BV+jR"), ("VHT",)]):
        ax.plot(data.U_mV, data.J_mA_cm2, "o", ms=3.8, mfc="white", mec="black", mew=.8,
                label="NiMo data", zorder=4)
        for name in names:
            ax.plot(lines[name + "_eta_mV"], lines.j_mA_cm2,
                "--" if name == "BV" else "-", lw=2, color=colors[name], label=name)
        ax.set(xlabel=r"$|\eta|$ (mV)", ylabel=r"$|j|$ (mA cm$^{-2}$)",
               xlim=(65, 152), ylim=(0, 26), yticks=[0, 5, 10, 15, 20, 25])
        ax.legend(loc="upper left", frameon=False, handlelength=2.2, labelspacing=.35)
        ax.text(.04, .50, "Voltage RMSE\n" + "\n".join(f"{n}: {errors[n]:.2f} mV" for n in names),
                transform=ax.transAxes, va="top", fontsize=9)
    axes[0].set_title("Empirical fits", pad=9)
    axes[1].set_title("Kinetics-only VHT fit", pad=9)
    axes[1].text(.97, .05, r"$R=0$; no offset", ha="right", transform=axes[1].transAxes, fontsize=9)
    axes[2].plot(coverage.eta_mV, coverage.theta, color=colors["VHT"], lw=2, label="Representative fit")
    axes[2].plot(coverage.eta_mV, coverage.theta_mirror, color="0.40", lw=1.5, ls="--", label="Equivalent solution")
    axes[2].set(title="Model-predicted coverage", xlabel=r"$|\eta|$ (mV)",
        ylabel=r"Hydrogen coverage, $\theta_{\mathrm{H}}$", xlim=(65, 152), ylim=(0, 1), yticks=[0, .25, .5, .75, 1])
    axes[2].legend(loc="upper left", frameon=False, fontsize=9, handlelength=2.1)
    axes[2].text(.5, .05, "Identical polarization", ha="center", transform=axes[2].transAxes, fontsize=9)
    for extension in ("svg", "png", "pdf"):
        fig.savefig(output / f"Figure5C_NiMo_comparison.{extension}", dpi=220)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3), layout="constrained")
    for name in colors:
        axes[0].plot(data.J_mA_cm2, data[name + "_eta_mV"] - data.U_mV,
            "o-", ms=2.5, lw=1.1, color=colors[name], label=name)
    axes[0].axhline(0, color="black", lw=.7)
    axes[0].set(title="Voltage residuals", xlabel=r"$|j|$ (mA cm$^{-2}$)", ylabel="Predicted - observed (mV)")
    axes[0].legend(frameon=False)
    axes[1].fill_between(coverage.eta_mV, coverage.near_optimum_min, coverage.near_optimum_max,
                        color=colors["VHT"], alpha=.2)
    axes[1].plot(coverage.eta_mV, coverage.theta, color=colors["VHT"], lw=1.5)
    axes[1].set(title="Near-optimal increasing branches", xlabel=r"$|\eta|$ (mV)",
                ylabel=r"$\theta_{\mathrm{H}}$", ylim=(0, 1))
    axes[1].text(.03, .96, "Within 1% of best SSE\nSensitivity range, not a CI", va="top",
                 transform=axes[1].transAxes, fontsize=9)
    fig.savefig(output / "NiMo_diagnostics.png", dpi=200)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO / "build/figure5-nimo")
    parser.add_argument("--starts", type=int, default=64)
    parser.add_argument("--skip-checks", action="store_true", help="Skip CV, window and limiting-model checks")
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()
    run(args.output, args.starts, not args.skip_checks, not args.no_plot)


if __name__ == "__main__":
    main()
