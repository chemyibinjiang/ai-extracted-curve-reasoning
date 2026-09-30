"""Re-profile Pt/C memberships and refit the VHT reconstructions and controls."""
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ[key] = "1"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ["FIGURE6_OUTPUT"] = str(ROOT / "build/effective-bv-kinetic-cache")
sys.path.insert(0, str(ROOT / "analysis/common"))
sys.path.insert(0, str(ROOT / "analysis/figure6"))
sys.path.insert(0, str(ROOT / "analysis/figure6/vendor/vht"))
import numpy as np
import pandas as pd
from scipy.optimize import least_squares, minimize_scalar
import effective_bv as bv
import independent_model as engine
from sharing import layout, prediction_jacobian
from numerics import optimize_scale
from control_core import rate_control, state, independent_state

MODELS = ("DeltaG_only", "DeltaG_T", "DeltaG_H", "independent_H_T_G")
UNIT = engine.KBT_MEV*np.log(10.)
BOUNDS = ([-10.,-16.,-800/UNIT,-24.], [10.,16.,800/UNIT,24.])
FIT_POINTS, POLISH_POINTS, VERIFY_POINTS = 200, 1000, 5000


def selection_key(result):
    return result["pooled_rmse"], result["worst_rmse"]


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read(path):
    return pd.read_csv(path, float_precision="round_trip")


def profile(j, y, template, start=None):
    q = template.Q_mV
    lo = max(np.log(1e-12), np.log(q/100)) if q > 0 else np.log(1e-12)
    hi = np.log(1e8)
    def objective(z):
        r = dict(log_j0=z, fraction=template.fraction, coefficient_sum=template.coefficient_sum, R=q*np.exp(-z))
        pred = bv.predict(j, r)
        return float(np.sum((pred-y)**2))
    grid = np.linspace(lo, hi, 45)
    losses = [objective(z) for z in grid]
    choices = [(loss, z) for loss, z in zip(losses, grid)]
    if start is not None:
        choices.append((objective(start), start))
    for i in range(len(grid)):
        if (i and losses[i] > losses[i-1]) or (i+1 < len(grid) and losses[i] > losses[i+1]):
            continue
        result = minimize_scalar(objective, bounds=(grid[max(0, i-1)], grid[min(len(grid)-1, i+1)]),
                                 method="bounded", options={"xatol": 1e-11})
        choices.append((float(result.fun), float(result.x)))
    return min(choices)


def empirical(output):
    summaries = []
    for condition, folder, upper in [("acid", "acidic", 200), ("KOH", "alkaline", 300)]:
        out = output / condition
        out.mkdir(parents=True, exist_ok=True)
        templates = read(HERE / "reference" / condition / "TEMPLATES.csv")
        previous = read(HERE / "reference" / condition / "ASSIGNMENTS.csv").set_index("curve_uid")
        full = read(ROOT / f"analysis/figure6/inputs/{folder}/cohort_all_points.csv")
        flow, assignments, points = [], [], []
        for uid, g in full.groupby("curve_uid", sort=True):
            g = g[g.eta_mV.between(0, upper)].sort_values(["j_mA_cm2", "fit_point_index"])
            status = "insufficient"
            if len(g) >= 5 and g.eta_mV.var(ddof=0) > 1e-20:
                j, y = g.j_mA_cm2.to_numpy(), g.eta_mV.to_numpy()
                r = np.clip(j@y/(j@j), 0, 100)
                total = np.sum((y-y.mean())**2)
                status = "linear" if np.sum((r*j-y)**2) <= .01*total else "nonlinear"
                if status == "nonlinear":
                    choices = []
                    for t in templates.itertuples():
                        start = np.log(previous.loc[uid, "beta"]) if previous.loc[uid, "family"] == t.family else None
                        loss, z = profile(j, y, t, start)
                        choices.append((loss, t.candidate_index, z, t))
                    loss, _, z, t = min(choices, key=lambda x: x[:2])
                    row = dict(curve_uid=uid, family=t.family, beta=float(np.exp(z)), r2=float(1-loss/total),
                               rmse=float(np.sqrt(loss/len(j))), adequate=bool(loss <= .01*total))
                    assert row["adequate"] == bool(previous.loc[uid, "adequate"])
                    assert row["family"] == previous.loc[uid, "family"]
                    assignments.append(row)
                    fit = dict(log_j0=z, fraction=t.fraction, coefficient_sum=t.coefficient_sum, R=t.Q_mV*np.exp(-z))
                    points.append(g.assign(family=t.family, beta=np.exp(z), adequate=row["adequate"],
                        x=j/np.exp(z), prediction_mV=bv.predict(j, fit)))
            flow.append(dict(curve_uid=uid, status=status, retained_points=len(g)))
        pp = pd.concat(points, ignore_index=True)
        for index, t in templates.iterrows():
            g = pp[pp.family.eq(t.family) & pp.adequate]
            templates.loc[index, ["n_curves", "x_min", "x_max"]] = [g.curve_uid.nunique(), g.x.min(), g.x.max()]
        templates.drop(columns=["origin"], errors="ignore").to_csv(out / "TEMPLATES.csv", index=False)
        pd.DataFrame(assignments).to_csv(out / "ASSIGNMENTS.csv", index=False)
        pp.to_csv(out / "POINT_PREDICTIONS.csv", index=False)
        pd.DataFrame(flow).to_csv(out / "COHORT_FLOW.csv", index=False)
        for name in ("COVERAGE_SCAN.csv", "PAPER_CV.csv"):
            (out / name).write_bytes((HERE / "reference" / condition / name).read_bytes())
        summary = dict(condition=condition, total=len(flow),
            insufficient=sum(r["status"] == "insufficient" for r in flow),
            linear=sum(r["status"] == "linear" for r in flow), nonlinear=len(assignments),
            families=len(templates), covered=sum(r["adequate"] for r in assignments),
            template_search="Verified selected library from the completed variable-coefficient search",
            amplitude_fit="Reoptimized for every eligible nonlinear curve against all selected templates")
        summaries.append(summary)
        print(summary, flush=True)
    dump(output / "EMPIRICAL_SUMMARY.json", summaries)


def data(source, condition, count=FIT_POINTS):
    meta = read(Path(source) / condition / "TEMPLATES.csv")
    points = read(Path(source) / condition / "POINT_PREDICTIONS.csv")
    points = points[points.adequate].copy()
    xx = np.array([np.geomspace(r.x_min, r.x_max, count) for r in meta.itertuples()])
    yy = np.array([bv.predict(x, dict(log_j0=0., fraction=r.fraction, coefficient_sum=r.coefficient_sum, R=r.Q_mV))
                   for x, r in zip(xx, meta.itertuples())])
    return meta, points, xx, yy


def records(p, ix):
    return np.column_stack([p[ix], np.full((len(ix), 2), .5), np.zeros(len(ix))])


def packed(rec, ix):
    p, count = np.zeros(ix.max()+1), np.zeros(ix.max()+1)
    for i in range(len(rec)):
        for k in range(4):
            p[ix[i,k]] += rec[i,k]
            count[ix[i,k]] += 1
    return p/count


def worker(job):
    source, condition, name, start = job
    meta, _, xx, yy = data(source, condition)
    cap = 2. if condition == "acid" else 3.
    ix, names, lo, hi = layout(name, len(meta), bounds=BOUNDS)
    seeds = json.loads((HERE / "reference/VHT_SEEDS.json").read_text())
    rec = np.array(seeds[condition + "_" + name]["records"])
    rng = np.random.default_rng(20260928 + start + sum(map(ord, condition+name)))
    if start > 0:
        rec[:,:3] += rng.normal(0, .35 if start < 5 else 1.5, (len(meta),3))
    p0 = packed(rec, ix)
    for i, r in enumerate(records(p0, ix)):
        mid = len(xx[i])//2
        current = engine.state(yy[i,mid]/engine.THERMAL, *r[:3], .5, .5)[0]
        p0[ix[i,3]] = np.log10(xx[i,mid]/max(current, 1e-30))
    p0 = np.clip(p0, lo+1e-9, hi-1e-9)
    def errors(p):
        pred, jac = prediction_jacobian(p, xx, ix)
        return (pred-yy)/cap, jac/cap
    opt = least_squares(lambda p: errors(p)[0].ravel(), p0,
        jac=lambda p: errors(p)[1].reshape(-1, len(p)), bounds=(lo,hi),
        x_scale="jac", max_nfev=800, ftol=1e-10, xtol=1e-10, gtol=1e-7)
    alternatives = [("pooled_reference", packed(np.array(seeds[condition+"_"+name]["records"]), ix), False),
                    ("pooled_200", opt.x, bool(opt.success))]
    _, _, xx, yy = data(source, condition, POLISH_POINTS)
    polished = least_squares(lambda p: errors(p)[0].ravel(), opt.x,
        jac=lambda p: errors(p)[1].reshape(-1, len(p)), bounds=(lo,hi),
        x_scale="jac", max_nfev=1000, ftol=1e-11, xtol=1e-11, gtol=1e-8)
    alternatives.append(("pooled_1000", polished.x, bool(polished.success)))
    _, _, xd, yd = data(source, condition, VERIFY_POINTS)
    snapshots = []
    for stage, p, success in alternatives:
        rec = records(p, ix)
        prediction = np.array([engine.response(x, *r) for x,r in zip(xd,rec)])
        rms = np.sqrt(np.mean((prediction-yd)**2, axis=1))
        r2 = 1-np.sum((prediction-yd)**2,axis=1)/np.sum((yd-yd.mean(axis=1,keepdims=True))**2,axis=1)
        snapshots.append(dict(condition=condition, model=name, seed=start, stage=stage,
            optimizer_converged=success, records=rec.tolist(), params=p.tolist(), family_rmse=rms.tolist(),
            worst_rmse=float(rms.max()), pooled_rmse=float(np.sqrt(np.mean(rms**2))), cap=cap,
            family_R2=r2.tolist(), feasible=bool(rms.max() <= cap and r2.min() >= .99), n_parameters=len(p)))
    return dict(condition=condition, model=name, seed=start, snapshots=snapshots)


def evaluate(selected, output):
    summary, parameters, replay, predictions, control = [], [], [], [], []
    for key, result in selected.items():
        condition, name = result["condition"], result["model"]
        meta, points, xx, yy = data(output, condition, VERIFY_POINTS)
        own = []
        for i, (t, rec) in enumerate(zip(meta.itertuples(), result["records"])):
            predictor = lambda x: engine.response(np.asarray(x), *rec)
            row = dict(condition=condition, model=name, family=t.family,
                log10_kH_over_kV=rec[0], log10_kT_over_kV=rec[1],
                DeltaG_eff_meV=-rec[2]*engine.KBT_MEV*np.log(10), alphaV=.5, alphaH=.5,
                kH_over_kV=10**rec[0], kT_over_kV=10**rec[1], current_scale=10**rec[3],
                template_rmse=result["family_rmse"][i])
            parameters.append(row)
            predictions.extend(dict(condition=condition, model=name, family=t.family, x=x,
                empirical_eta_mV=y, vht_eta_mV=v) for x,y,v in zip(xx[i], yy[i], predictor(xx[i])))
            for uid, g in points[points.family.eq(t.family)].groupby("curve_uid"):
                x, y = g.x.to_numpy(), g.eta_mV.to_numpy()
                scale, _, _, bound = optimize_scale(x, y, predictor, t.x_min, t.x_max)
                entry = dict(condition=condition, model=name, family=t.family, curve_uid=uid,
                             amplitude_multiplier=scale, at_bound=bound, **engine.metrics(y, predictor(x/scale)))
                own.append(entry)
                replay.append(entry)
            if (condition, name) in (("acid", "DeltaG_only"), ("KOH", "DeltaG_T")):
                record = SimpleNamespace(**row)
                vlo, vhi = predictor(xx[i])[[0,-1]]
                for eta in (50., 100., 150.):
                    np.testing.assert_allclose(state(record, eta), independent_state(record, eta, np.zeros(3)),
                                               rtol=1e-8, atol=1e-10)
                for eta in np.arange(1., (200 if condition == "acid" else 300) + .25, .5):
                    values = rate_control(record, eta)
                    np.testing.assert_allclose(values.sum(), 1., atol=2e-5)
                    control.append(dict(condition=condition, family=t.family, eta_mV=eta,
                        X_V=values[0], X_H=values[1], X_T=values[2], theta_H=state(record, eta)[1],
                        inside_fitted_support=bool(vlo <= eta <= vhi),
                        fitted_support_min_mV=float(vlo), fitted_support_max_mV=float(vhi)))
        summary.append(dict(condition=condition, model=name, families=len(meta), cap=result["cap"],
            pooled_rmse_mV=result["pooled_rmse"], worst_rmse_mV=result["worst_rmse"], feasible=result["feasible"],
            selected_stage=result["stage"], optimizer_converged=result["optimizer_converged"],
            raw_members=len(own), raw_pass=sum(r["R2"] >= .99 for r in own)))
    for rows, name in [(summary,"KINETIC_SUMMARY"), (parameters,"KINETIC_PARAMETERS"),
                       (replay,"RAW_VHT_REPLAY"), (predictions,"TEMPLATE_RECONSTRUCTION"), (control,"RATE_CONTROL")]:
        pd.DataFrame(rows).to_csv(output / f"{name}.csv", index=False)
    means = []
    for (condition, eta), g in pd.DataFrame(control).groupby(["condition", "eta_mV"], sort=True):
        row = dict(condition=condition, eta_mV=eta, all_families_supported=bool(g.inside_fitted_support.all()))
        for step in "VHT":
            row[f"X_{step}_mean"] = g[f"X_{step}"].mean()
            row[f"X_{step}_sd"] = g[f"X_{step}"].std(ddof=1)
        means.append(row)
    pd.DataFrame(means).to_csv(output / "RATE_CONTROL_MEAN_SD.csv", index=False)
    print(pd.DataFrame(summary).to_string(index=False), flush=True)


def run(output, workers=6, starts=12):
    output.mkdir(parents=True, exist_ok=True)
    empirical(output)
    fingerprint = hashlib.sha256(Path(__file__).read_bytes() + (ROOT / "analysis/common/effective_bv.py").read_bytes()
        + (HERE / "reference/VHT_SEEDS.json").read_bytes()
        + (ROOT / "analysis/figure6/sharing.py").read_bytes()
        + b"".join((output / c / "TEMPLATES.csv").read_bytes() for c in ("acid", "KOH"))).hexdigest()
    protocol = output / "KINETIC_PROTOCOL.json"
    if protocol.exists():
        assert json.loads(protocol.read_text())["fingerprint"] == fingerprint, "Code/input changed: use a new output"
    dump(protocol, dict(fingerprint=fingerprint, starts=starts, VHT_added_R=0,
        models=list(MODELS), alpha_V=.5, alpha_H=.5, reference_points=VERIFY_POINTS,
        optimization_points=FIT_POINTS, polish_points=POLISH_POINTS,
        objective="Mean squared voltage residual, with equal weight per template",
        selection="Lowest pooled RMSE; worst-family RMSE is only a tie breaker",
        bounds_log10_h=[-10,10], bounds_log10_t=[-16,16], bounds_G_meV=[-800,800],
        bounds_log10_c=[-24,24], acceptance="Each family: R2 >= 0.99 and RMSE <= 2 mV (acid) or 3 mV (KOH)"))
    target = output / "VHT_RUNS.json"
    runs = json.loads(target.read_text()) if target.exists() else []
    done = {(r["condition"], r["model"], r["seed"]) for r in runs}
    jobs = [(str(output), c, m, i) for c in ("acid", "KOH") for m in MODELS for i in range(starts)
            if (c,m,i) not in done]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(worker, job) for job in jobs]):
            result = future.result()
            runs.append(result)
            dump(target, runs)
            best = min(result["snapshots"], key=selection_key)
            print(f"VHT {len(runs)}/{2*len(MODELS)*starts}: {result['condition']} {result['model']} pooled RMSE {best['pooled_rmse']:.4f}", flush=True)
    selected = {}
    for c in ("acid", "KOH"):
        for m in MODELS:
            candidates = [s for r in runs if r["condition"] == c and r["model"] == m for s in r["snapshots"]]
            selected[c+"_"+m] = min(candidates, key=selection_key)
    dump(output / "VHT_SELECTED.json", selected)
    evaluate(selected, output)
