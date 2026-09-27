"""Refit every retained HER curve using the same effective-BV implementation."""
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import sys
import time
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ[key] = "1"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "analysis/common"))
import numpy as np
import pandas as pd
import effective_bv as bv


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return pd.read_csv(path, float_precision="round_trip", low_memory=False)


def check_reference():
    manifest = json.loads((HERE / "reference/MANIFEST.json").read_text())
    for name, digest in manifest["inputs"].items():
        assert sha(ROOT / name) == digest, name
    for name, digest in manifest["seeds"].items():
        assert sha(HERE / "reference" / name) == digest, name


def worker(job):
    uid, paper, j, y, seeds = job
    return [dict(curve_uid=uid, paper_key=paper, model=name, **fit)
            for name, fit in bv.fit_pair(j, y, seeds).items()]


def run(output, workers=6):
    check_reference()
    output.mkdir(parents=True, exist_ok=True)
    points = read(ROOT / "analysis/figure4/inputs/POINTS.csv")
    refs = read(HERE / "reference/POPULATION_SEEDS.csv")
    groups = dict(tuple(points.groupby("curve_uid", sort=True)))
    protocol = dict(model=bv.PROTOCOL, input_sha256=sha(ROOT / "analysis/figure4/inputs/POINTS.csv"),
        model_sha256=sha(ROOT / "analysis/common/effective_bv.py"), script_sha256=sha(__file__),
        seeds_sha256=sha(HERE / "reference/POPULATION_SEEDS.csv"))
    p = output / "PROTOCOL.json"
    if p.exists():
        assert json.loads(p.read_text()) == protocol, "Inputs/code changed: use a new output directory"
    p.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    path = output / "FITS.csv"
    rows = read(path).to_dict("records") if path.exists() else []
    done = {r["curve_uid"] for r in rows}
    seedgroups = {uid: g.set_index("model").to_dict("index") for uid, g in refs.groupby("curve_uid")}
    jobs = [(uid, g.paper_key.iloc[0], g.j.to_numpy(), g.eta_mV.to_numpy(), seedgroups[uid])
            for uid, g in groups.items() if uid not in done]
    began = time.monotonic()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(worker, job) for job in jobs]):
            rows.extend(future.result())
            if len(rows) % 100 == 0 or len(rows) == 2 * len(groups):
                pd.DataFrame(rows).sort_values(["curve_uid", "model"]).to_csv(path, index=False)
                print(f"Population refit: {len(rows)//2}/{len(groups)} curves, {time.monotonic()-began:.0f}s", flush=True)
    frame = pd.DataFrame(rows)
    assert len(frame) == 6066 and frame.curve_uid.nunique() == 3033
    assert not frame.duplicated(["curve_uid", "model"]).any()
    assert frame.equivalent_converged.all(), "Inspect optimizer failures before using the fits"
    for row in frame.to_dict("records"):
        g = groups[row["curve_uid"]]
        e = bv.predict(g.j.to_numpy(), row) - g.eta_mV.to_numpy()
        np.testing.assert_allclose(e @ e, row["sse"], rtol=1e-9, atol=1e-7)
    wide = frame.pivot(index="curve_uid", columns="model", values="sse")
    assert (wide["BV+jR"] <= wide.BV * (1 + 1e-8) + 1e-7).all()
    summary = [dict(model=name, curves=len(g), papers=g.paper_key.nunique(),
        passes=int(g.r2.ge(.99).sum()), percent=100 * g.r2.ge(.99).mean(),
        median_rmse_mV=g.rmse.median(), median_r2=g.r2.median()) for name, g in frame.groupby("model")]
    pd.DataFrame(summary).to_csv(output / "MODEL_SUMMARY.csv", index=False)
    print(pd.DataFrame(summary).to_string(index=False), flush=True)
    return frame


def downstream(frame, output):
    sys.path.insert(0, str(ROOT / "analysis/figure4"))
    from local_slopes import curve_derivatives, polynomial_operator
    from run import EXAMPLES
    points = read(ROOT / "analysis/figure4/inputs/POINTS.csv")
    fits = frame.set_index(["curve_uid", "model"])
    local, examples, summaries, histograms = [], [], [], []
    for uid, g in points.groupby("curve_uid", sort=True):
        g = g.sort_values("native_index")
        j, y = g.j.to_numpy(), g.eta_mV.to_numpy()
        models = {m: bv.predict(j, fits.loc[(uid, m)]) for m in ("BV", "BV+jR")}
        models["jR"] = fits.loc[(uid, "BV+jR"), "R"] * j
        models["base"] = models["BV+jR"] - models["jR"]
        for item in curve_derivatives(j, y, 9, 2):
            if item["status"] != "eligible":
                continue
            indices = np.arange(item["left_index"], item["right_index"] + 1)
            op, *_ = polynomial_operator(np.log10(j[indices]), np.log10(j[item["native_index"]]), 2)
            item.update(curve_uid=uid, paper_key=g.paper_key.iloc[0],
                        **{m: float(op @ pred[indices]) for m, pred in models.items()})
            np.testing.assert_allclose(item["BV+jR"], item["base"] + item["jR"], atol=1e-8)
            local.append(item)
        if uid in EXAMPLES:
            examples.append(g.assign(display_label=EXAMPLES[uid], **models))
    pd.DataFrame(local).to_csv(output / "LOCAL_SLOPES.csv", index=False)
    pd.concat(examples).to_csv(output / "EXAMPLE_CURVES.csv", index=False)
    frame[frame.curve_uid.isin(EXAMPLES)].to_csv(output / "EXAMPLE_METRICS.csv", index=False)
    accepted = frame[frame.model.eq("BV+jR") & frame.r2.ge(.99)]
    for field, edges in [("b_mV_dec", np.arange(20, 225, 5)), ("R", np.linspace(0, 5, 51)),
                         ("j0", np.logspace(-8, 3, 45)), ("coefficient_sum", np.linspace(0, 2, 41))]:
        v = accepted[field].to_numpy()
        counts, _ = np.histogram(v, edges)
        summaries.append(dict(parameter=field, curves=len(v), papers=accepted.paper_key.nunique(),
            median=float(np.median(v)), q25=float(np.quantile(v, .25)), q75=float(np.quantile(v, .75)),
            below_display=int((v < edges[0]).sum()), above_display=int((v > edges[-1]).sum())))
        histograms.extend(dict(parameter=field, left=a, right=b, count=int(n), percent=100*n/len(v))
                          for a, b, n in zip(edges[:-1], edges[1:], counts))
    pd.DataFrame(summaries).to_csv(output / "PARAMETER_SUMMARY.csv", index=False)
    pd.DataFrame(histograms).to_csv(output / "PARAMETER_HISTOGRAMS.csv", index=False)
