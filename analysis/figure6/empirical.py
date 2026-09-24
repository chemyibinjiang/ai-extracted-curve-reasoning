"""Discover linear-first BV libraries on original points in fixed eta windows."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import time

from paths import PACKAGE, EMPIRICAL_OUT, INPUTS
HERE = EMPIRICAL_OUT
VENDOR = PACKAGE / "vendor/empirical"
os.environ["NUMBA_CACHE_DIR"] = str(HERE / "numba_cache")
os.environ["NUMBA_NUM_THREADS"] = "8"
for key in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"]:
    os.environ[key] = "1"
sys.dont_write_bytecode = True
sys.path.insert(0, str(VENDOR))
import model
import coverage_solver
import numpy as np
import pandas as pd
from numba import njit, prange

CONDITIONS = {"acid": ("acidic", 200), "KOH": ("alkaline", 300)}
MIN_POINTS = 5
R2_MIN = .99
MAX_K = 10


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(obj):
    if isinstance(obj, dict): return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)): return [clean(v) for v in obj]
    if isinstance(obj, np.ndarray): return clean(obj.tolist())
    if isinstance(obj, np.generic): return clean(obj.item())
    if isinstance(obj, float) and not np.isfinite(obj): return None
    return obj


def dump(path, data):
    Path(path).write_text(json.dumps(clean(data), indent=2), encoding="utf-8")


def metrics(y, pred):
    e = np.asarray(pred)-np.asarray(y)
    mse = float(np.mean(e*e))
    variance = float(np.var(y))
    return dict(RMSE_mV=np.sqrt(mse), R2=1-mse/variance if variance>1e-20 else np.nan,
                bias_mV=float(e.mean()), max_abs_mV=float(np.max(abs(e))))


def passes(m):
    return bool(m["R2"] >= R2_MIN)


def candidate_grid():
    alphas = np.arange(1,100)/100
    qs = np.unique(np.r_[0., 1e-12, 1e-10, 1e-8, 1e-6, 1e-5,
                        np.logspace(-4,3,141), 10.**np.array([4,5,6,7,8,9,9.5,9.9,10])])
    return pd.DataFrame([(a,q) for a in alphas for q in qs], columns=["alpha","Q_mV"])


@njit(parallel=True, cache=True)
def profile_grid(J, Y, N, alphas, qs):
    S, Z = np.empty((len(alphas)*len(qs),len(N))), np.empty((len(alphas)*len(qs),len(N)))
    LJ = np.log(np.maximum(J,1e-300))
    for ai in prange(len(alphas)):
        a = alphas[ai]
        vals, ders = model.table(a)
        for qi in range(len(qs)):
            k = ai*len(qs)+qi
            for i in range(len(N)):
                n = N[i]
                z,s = model.profile(J[i,:n],LJ[i,:n],Y[i,:n],a,qs[qi],vals,ders)
                S[k,i],Z[k,i] = s,z/model.LN10
    return S,Z


def run(condition, grid, force=False):
    began = time.monotonic()
    folder, upper = CONDITIONS[condition]
    dest = HERE/condition
    dest.mkdir(exist_ok=True,parents=True)
    source = INPUTS/folder/"cohort_all_points.csv"
    full = pd.read_csv(source)
    assert full.j_mA_cm2.gt(0).all()
    full.to_csv(dest/"INPUT_RETAINED_POINTS.csv",index=False)
    cuts = {u:g[g.eta_mV.between(0,upper)].sort_values(["j_mA_cm2","fit_point_index"])
            for u,g in full.groupby("curve_uid")}
    membership = []
    for u,g in full.groupby("curve_uid"):
        cut = cuts[u]
        eligible = len(cut)>=MIN_POINTS and cut.eta_mV.var(ddof=0)>1e-20
        membership.append(dict(condition=condition,curve_uid=u,n_source=len(g),n_in_window=len(cut),
            eligible=eligible,status="eligible" if eligible else "insufficient_information",
            eta_min=cut.eta_mV.min(),eta_max=cut.eta_mV.max(),j_min=cut.j_mA_cm2.min(),j_max=cut.j_mA_cm2.max()))
    membership = pd.DataFrame(membership)
    membership.to_csv(dest/"MEMBERSHIP.csv",index=False)
    points = pd.concat([g for g in cuts.values() if len(g)],ignore_index=True)
    points.to_csv(dest/"WINDOW_POINTS.csv",index=False)
    ids = sorted(membership.loc[membership.eligible,"curve_uid"])
    linear = []
    for u in ids:
        j,y = cuts[u].j_mA_cm2.to_numpy(),cuts[u].eta_mV.to_numpy()
        R = float(np.clip(j@y/(j@j),0,100))
        m = metrics(y,R*j)
        slope,offset = np.linalg.lstsq(np.column_stack([j,np.ones(len(j))]),y,rcond=None)[0]
        affine = metrics(y,slope*j+offset)
        linear.append(dict(curve_uid=u,R_ohm_cm2=R,adequate=passes(m),**m,
                           affine_R_ohm_cm2=slope,affine_intercept_mV=offset,
                           affine_R2=affine["R2"],affine_RMSE_mV=affine["RMSE_mV"]))
    linear = pd.DataFrame(linear).set_index("curve_uid")
    linear.to_csv(dest/"LINEAR_FITS.csv")
    nonlinear = sorted(linear.index[~linear.adequate])
    n = len(nonlinear)
    assert n>0
    N = np.array([len(cuts[u]) for u in nonlinear],dtype=np.int64)
    J,Y = np.ones((n,N.max())),np.zeros((n,N.max()))
    for i,u in enumerate(nonlinear):
        J[i,:N[i]],Y[i,:N[i]] = cuts[u].j_mA_cm2,cuts[u].eta_mV
    limits = np.array([.01*np.sum((Y[i,:N[i]]-Y[i,:N[i]].mean())**2) for i in range(n)])
    fingerprint = hashlib.sha256((sha(source)+sha(__file__)+grid.to_csv(index=False)+str(upper)).encode()).hexdigest()
    cache = dest/"CANDIDATE_PROFILES.npz"
    if cache.exists() and not force:
        with np.load(cache) as z:
            assert str(z["fingerprint"])==fingerprint,"Profile cache input mismatch"
            S,Z = z["S"],z["Z"]
    else:
        S,Z = profile_grid(J,Y,N,np.sort(grid.alpha.unique()),np.sort(grid.Q_mV.unique()))
        for k,i in np.argwhere(abs(S/limits[None,:]-1)<1e-5):
            r = grid.iloc[k]
            S[k,i] = np.sum((model.predict(J[i,:N[i]],r.alpha,r.Q_mV,Z[k,i])-Y[i,:N[i]])**2)
        np.savez_compressed(cache,S=S,Z=Z,curve_uids=np.array(nonlinear),fingerprint=fingerprint)
    relative = S/limits[None,:]
    relative = np.where(relative<=1,np.minimum(relative,1),np.maximum(relative,1.000001))
    prep = coverage_solver.prepare(relative,np.ones(n),np.arange(n))
    scans = []
    for k in range(1,MAX_K+1):
        sol = coverage_solver.solve(prep,k,time_limit=30.)
        if not sol["certified_count"]: sol = coverage_solver.solve(prep,k,time_limit=120.)
        scans.append(dict(K_BV=k,nonlinear_denominator=n,linear_count=int(linear.adequate.sum()),
                          eligible_denominator=len(ids),total_covered=sol["covered"]+int(linear.adequate.sum()),**sol))
        print(condition,"K",k,"nonlinear",sol["covered"],"/",n,"certified",sol["certified_count"],flush=True)
    chosen = next((s for s in scans if s["covered"]>=np.ceil(.8*n)),scans[-1])
    selected = sorted(chosen["selected"],key=lambda k:(-grid.iloc[k].alpha,grid.iloc[k].Q_mV,k))
    prefix = "A" if condition=="acid" else "K"
    labels = {k:f"{prefix}{i+1}" for i,k in enumerate(selected)}
    assignments,compatibility,point_rows = [],[],[]
    index = {u:i for i,u in enumerate(nonlinear)}
    for u in ids:
        g = cuts[u]
        j,y = g.j_mA_cm2.to_numpy(),g.eta_mV.to_numpy()
        lf = linear.loc[u]
        if lf.adequate:
            R = lf.R_ohm_cm2
            pred = R*j
            rec = dict(curve_uid=u,kind="linear",family="L",adequate=True,alpha=np.nan,Q_mV=1.,
                       beta=1/R,R_ohm_cm2=R,n_compatible=1,**metrics(y,pred))
        else:
            i = index[u]
            fits = []
            for k in selected:
                r = grid.iloc[k]
                beta = 10**Z[k,i]
                pred = model.predict(j,r.alpha,r.Q_mV,Z[k,i])
                m = metrics(y,pred)
                compatibility.append(dict(curve_uid=u,family=labels[k],candidate_index=k,beta=beta,adequate=passes(m),**m))
                fits.append((m["RMSE_mV"],k,beta,pred,m))
            _,k,beta,pred,m = min(fits,key=lambda f:(f[0],f[1]))
            r = grid.iloc[k]
            rec = dict(curve_uid=u,kind="BV+jR",family=labels[k],adequate=passes(m),alpha=r.alpha,
                       Q_mV=r.Q_mV,beta=beta,R_ohm_cm2=r.Q_mV/beta,
                       n_compatible=sum(passes(f[-1]) for f in fits),**m)
        rec.update(condition=condition,n_points=len(g),pass_R2_and_RMSE3=rec["adequate"] and rec["RMSE_mV"]<=3)
        assignments.append(rec)
        pp = g.copy()
        for field in ["condition","kind","family","adequate","beta"]: pp[field]=rec[field]
        pp["x"],pp["empirical_prediction_mV"] = j/rec["beta"],pred
        point_rows.append(pp)
    aa,pp = pd.DataFrame(assignments),pd.concat(point_rows,ignore_index=True)
    aa.to_csv(dest/"ASSIGNMENTS.csv",index=False)
    pp.to_csv(dest/"POINT_PREDICTIONS.csv",index=False)
    pd.DataFrame(compatibility).to_csv(dest/"COMPATIBILITY.csv",index=False)
    families = []
    for k in selected:
        g = pp[pp.family.eq(labels[k])&pp.adequate]
        members = aa[aa.family.eq(labels[k])&aa.adequate]
        r = grid.iloc[k]
        assert len(g)>0
        families.append(dict(condition=condition,family=labels[k],candidate_index=k,alpha=r.alpha,Q_mV=r.Q_mV,
            b_BV_mV_dec=model.A*np.log(10)/r.alpha,n_curves=len(members),n_points=len(g),
            x_min=g.x.min(),x_max=g.x.max(),mean_inverse_beta=float((1/members.beta).mean()),
            median_R_ohm_cm2=members.R_ohm_cm2.median(),median_RMSE_mV=members.RMSE_mV.median()))
    pd.DataFrame(families).to_csv(dest/"TEMPLATES.csv",index=False)
    pd.DataFrame([{**s,"selected":";".join(map(str,s["selected"]))} for s in scans]).to_csv(dest/"COVERAGE_SCAN.csv",index=False)
    summary = dict(condition=condition,eta_window_mV=[0,upper],n_cohort=full.curve_uid.nunique(),n_eligible=len(ids),
        n_insufficient=int((~membership.eligible).sum()),n_points=len(points),n_linear=int(linear.adequate.sum()),
        n_affine_linear_diagnostic=int(linear.affine_R2.ge(.99).sum()),n_nonlinear=n,
        chosen_K=chosen["K_BV"],nonlinear_covered=chosen["covered"],total_covered=int(aa.adequate.sum()),
        total_R2_and_RMSE3=int(aa.pass_R2_and_RMSE3.sum()),all_candidate_covered=int((S<=limits).any(axis=0).sum()),
        all_counts_certified=all(s["certified_count"] for s in scans),seconds=time.monotonic()-began,
        source=str(source),source_sha256=sha(source),fingerprint=fingerprint,coverage_scan=scans)
    assert summary["total_covered"]==chosen["total_covered"]
    dump(dest/"RESULT.json",summary)
    print(json.dumps(clean({k:v for k,v in summary.items() if k!="coverage_scan"}),indent=2),flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force",action="store_true")
    args = parser.parse_args()
    grid = candidate_grid()
    grid.to_csv(HERE/"CANDIDATE_GRID.csv",index=False)
    protocol = dict(eta_windows_mV={c:[0,v[1]] for c,v in CONDITIONS.items()},min_original_points=MIN_POINTS,
        full_window_crossing_required=False,interpolated_points=False,point_weights="equal per original point within a curve",
        linear="eta=R*j, no intercept, 0<=R<=100 ohm cm2; affine line diagnostic only",
        pass_threshold="R2_eta >=0.99 on all original in-window points; RMSE also reported",
        nonlinear_model="eta=BV(j/beta;alpha,n_eff=2,T=298.15 K)+Q*j/beta",
        candidates=len(grid),alpha_range=[.01,.99],Q_range_mV=[0,1e10],beta_range_mA_cm2=[1e-12,1e8],
        empirical_R_max_ohm_cm2=100,K_scan=list(range(1,MAX_K+1)),
        chosen_budget="Smallest K covering >=80% of eligible non-proportional curves; fallback K=10",
        maximum_coverage="MILP over finite data-independent grid, not a continuous-global certificate",
        labels="New A/K labels ordered by BV slope then Q; not old A80/K6 family identities",
        scope="In-sample representation, not out-of-window prediction or mechanism identification",
        script_sha256=sha(__file__),numerical_dependencies={str(p):sha(p) for p in [VENDOR/"model.py",VENDOR/"coverage_solver.py"]})
    dump(HERE/"PROTOCOL.json",protocol)
    results = [run(c,grid,args.force) for c in CONDITIONS]
    pd.DataFrame([{k:v for k,v in r.items() if k!="coverage_scan"} for r in results]).to_csv(HERE/"EMPIRICAL_SUMMARY.csv",index=False)


if __name__=="__main__": main()
