"""Shared, detailed-balanced VHT reconstruction and unchanged-point replay."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import time

from paths import PACKAGE, EMPIRICAL_OUT
HERE = EMPIRICAL_OUT
VENDOR = PACKAGE / "vendor/vht"
os.environ["NUMBA_CACHE_DIR"] = str(HERE/"numba_cache")
for key in ["OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMBA_NUM_THREADS"]:
    os.environ[key]="1"
sys.dont_write_bytecode=True
sys.path.insert(0,str(VENDOR))
import independent_model as engine
from numerics import kinetic_and_jacobian, optimize_scale
import numpy as np
import pandas as pd
from scipy.optimize import minimize

UNIT = engine.KBT_MEV*np.log(10.)
CAP = {"acid":2.,"KOH":3.}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@lru_cache(None)
def inputs(condition,count=160):
    meta = pd.read_csv(HERE/condition/"TEMPLATES.csv")
    points = pd.read_csv(HERE/condition/"POINT_PREDICTIONS.csv")
    points = points[points.adequate & points.kind.eq("BV+jR")].copy()
    xx = np.array([np.geomspace(r.x_min,r.x_max,count) for r in meta.itertuples()])
    yy = np.array([engine.bv_response(x,r.alpha,r.Q_mV) for x,r in zip(xx,meta.itertuples())])
    return meta,points,xx,yy


def bounds(n):
    lo = np.r_[[-7.,-7.,.5,.5],np.full(n,-300/UNIT),np.full(n,-8.)]
    hi = np.r_[[7.,7.,.5,.5],np.full(n,300/UNIT),np.full(n,8.)]
    return lo,hi


def make_starts(condition,count):
    meta,_,xx,yy = inputs(condition)
    n = len(meta)
    rng = np.random.default_rng(20260921+(condition=="KOH")*1000)
    backbones = [(-3.,0.),(-3.,1.),(-2.,-2.),(2.,-2.),(1.,0.),(0.,2.),(-1.,3.),(3.,0.)]
    starts = []
    lo,hi = bounds(n)
    for seed in range(count):
        lh,lt = backbones[seed] if seed<len(backbones) else rng.uniform(-4,4,2)
        logK = rng.uniform(-2.5,2.5,n)
        lc = []
        for i in range(n):
            mid = len(xx[i])//2
            current = engine.state(max(yy[i,mid],.1)/engine.THERMAL,lh,lt,logK[i],.5,.5)[0]
            lc.append(np.log10(xx[i,mid]/max(current,1e-30)))
        p = np.clip(np.r_[lh,lt,.5,.5,logK,lc],lo,hi)
        starts.append(dict(condition=condition,seed=seed,initial=p.tolist()))
    return starts


def fit_job(job):
    began=time.monotonic()
    c,loss = job["condition"],job["loss"]
    meta,_,xx,yy=inputs(c)
    n=len(meta)
    cap2=CAP[c]**2
    weights=meta.mean_inverse_beta.to_numpy()
    upperQ=np.min(yy/xx,axis=1)
    low,high=bounds(n)
    p0=np.array(job["initial"])

    def qprofile(eta):
        return np.clip(np.mean(xx*(yy-eta),axis=1)/np.mean(xx**2,axis=1),0,upperQ) if loss else np.zeros(n)

    def accuracy(p):
        eta,jac=kinetic_and_jacobian(p,xx)
        q=qprofile(eta)
        err=eta+q[:,None]*xx-yy
        return float(np.mean(err**2)/cap2),2*np.mean(err[:,:,None]*jac,axis=(0,1))/cap2

    acc=minimize(accuracy,p0,jac=True,method="L-BFGS-B",bounds=list(zip(low,high)),
                 options=dict(maxiter=job["maxiter"],maxls=50,ftol=1e-12,gtol=1e-6))
    p=acc.x if accuracy(acc.x)[0]<accuracy(p0)[0] else p0
    q=qprofile(kinetic_and_jacobian(p,xx)[0])
    z=np.r_[p,q*weights] if loss else p.copy()
    accuracy_z=z.copy()
    zlo=np.r_[low,np.zeros(n)] if loss else low
    zhi=np.r_[high,upperQ*weights] if loss else high

    def ratios(z):
        p,q=(z[:-n],z[-n:]/weights) if loss else (z,np.zeros(n))
        eta,jac=kinetic_and_jacobian(p,xx)
        err=eta+q[:,None]*xx-yy
        value=np.mean(err**2,axis=1)/cap2
        grad=2*np.mean(err[:,:,None]*jac,axis=1)/cap2
        if loss: grad=np.column_stack([grad,np.diag(2*np.mean(err*xx,axis=1)/(weights*cap2))])
        return value,grad

    history=[dict(stage="mean_accuracy",success=bool(acc.success),iterations=int(acc.nit),message=str(acc.message))]
    if ratios(z)[0].max()>.995:
        def cons(v):
            val,jac=ratios(v[:-1])
            return v[-1]-val,np.column_stack([-jac,np.ones(n)])
        grad=np.r_[np.zeros(len(z)),1.]
        opt=minimize(lambda v:(v[-1],grad),np.r_[z,max(1.,ratios(z)[0].max())],jac=True,method="SLSQP",
                     bounds=list(zip(np.r_[zlo,0.],np.r_[zhi,1e7])),
                     constraints=dict(type="ineq",fun=lambda v:cons(v)[0],jac=lambda v:cons(v)[1]),
                     options=dict(maxiter=job["maxiter"],ftol=1e-10))
        if np.isfinite(opt.x).all() and ratios(opt.x[:-1])[0].max()<ratios(z)[0].max(): z=opt.x[:-1]
        history.append(dict(stage="worst_family_accuracy",success=bool(opt.success),iterations=int(opt.nit),message=str(opt.message)))
    before_regularization=z.copy()
    if loss and ratios(z)[0].max()<=1.001:
        previous=z.copy()
        grad=np.r_[np.zeros(len(z)-n),np.ones(n)/n]
        opt=minimize(lambda v:(float(v[-n:].mean()),grad),z,jac=True,method="SLSQP",
                     bounds=list(zip(zlo,zhi)),constraints=dict(type="ineq",fun=lambda v:.990-ratios(v)[0],jac=lambda v:-ratios(v)[1]),
                     options=dict(maxiter=job["maxiter"],ftol=2e-10))
        valid=[v for v in [previous,opt.x] if np.isfinite(v).all() and ratios(v)[0].max()<=1+1e-6]
        if valid: z=min(valid,key=lambda v:v[-n:].mean())
        history.append(dict(stage="minimum_nonnegative_residual_R",success=bool(opt.success),iterations=int(opt.nit),message=str(opt.message)))
    _,_,xd,yd=inputs(c,1000)

    def snapshot(v):
        p,q=(v[:-n],v[-n:]/weights) if loss else (v,np.zeros(n))
        rec=np.array([[p[0],p[1],p[4+i],p[4+n+i],.5,.5,q[i]] for i in range(n)])
        pred=np.array([engine.response(x,*r) for x,r in zip(xd,rec)])
        rmse=np.sqrt(np.mean((pred-yd)**2,axis=1))
        max_ratio=float(max(np.max(rmse**2/cap2),ratios(v)[0].max()))
        return dict(condition=c,loss=loss,seed=job["seed"],records=rec.tolist(),params=p.tolist(),
                    family_RMSE_mV=rmse.tolist(),pooled_template_RMSE_mV=float(np.sqrt(np.mean(rmse**2))),
                    max_ratio=max_ratio,feasible=bool(max_ratio<=1+1e-5),mean_R=float(np.mean(q*weights)),
                    boundary_indices=np.flatnonzero((np.minimum(p-low,high-p)<1e-5)&(low<high)).tolist())
    result=snapshot(z)
    result.update(accuracy_snapshot=snapshot(accuracy_z),balanced_snapshot=snapshot(before_regularization),
                  history=history,seconds=time.monotonic()-began)
    return result


def choose(runs):
    selected={}
    for c in CAP:
        noR=[s for r in runs if r["condition"]==c and not r["loss"] for s in [r["accuracy_snapshot"],r["balanced_snapshot"]]]
        feasible=[r for r in noR if r["feasible"]]
        if feasible:
            best=min(feasible,key=lambda r:r["pooled_template_RMSE_mV"])
        else:
            lowest=min(r["max_ratio"] for r in noR)
            best=min([r for r in noR if r["max_ratio"]<=lowest+1e-5],key=lambda r:r["pooled_template_RMSE_mV"])
        selected[c+"_kinetics_only"]=dict(best,selection="Best feasible mean error, else lowest worst-family normalized error")
        # Explicitly include zero loss: adding parameters cannot remove the simpler model.
        augmented=[s for r in runs if r["condition"]==c and r["loss"]
                   for s in [r["accuracy_snapshot"],r["balanced_snapshot"],{k:v for k,v in r.items() if not k.endswith("snapshot")}]]
        augmented += [dict(r,loss=True,nested_zero_loss=True) for r in noR]
        best_accuracy=min(augmented,key=lambda r:r["pooled_template_RMSE_mV"])
        selected[c+"_residual_R_accuracy"]=dict(best_accuracy,selection="Lowest mean squared template error, no loss penalty")
        feasible=[r for r in augmented if r["feasible"]]
        best=min(feasible,key=lambda r:(r["mean_R"],r["pooled_template_RMSE_mV"])) if feasible else min(augmented,key=lambda r:r["max_ratio"])
        selected[c+"_residual_R_minimum"]=dict(best,selection="Lowest mean residual R among template-cap-feasible searched solutions")
    return selected


def replay(selected):
    families,curves,point_rows,template_rows,fluxes,summaries=[],[],[],[],[],[]
    for name,result in selected.items():
        c=result["condition"]
        meta,points,xx,yy=inputs(c,1000)
        local_curves=[]
        local_points=[]
        for i,(r,record) in enumerate(zip(meta.itertuples(),result["records"])):
            rec=np.array(record)
            predictor=lambda x:engine.response(np.asarray(x,dtype=float),*rec)
            pred=predictor(xx[i])
            metric=engine.metrics(yy[i],pred)
            own=[]
            for uid,g in points[points.family.eq(r.family)].groupby("curve_uid"):
                x,y=g.x.to_numpy(),g.eta_mV.to_numpy()
                fixed=predictor(x)
                mult,lo,hi,bound=optimize_scale(x,y,predictor,r.x_min,r.x_max)
                newx=x/mult
                beta=float(g.beta.iloc[0])*mult
                prediction=predictor(newx)
                mm=engine.metrics(y,prediction)
                ff=engine.metrics(y,fixed)
                row=dict(model=name,condition=c,family=r.family,curve_uid=uid,n_points=len(g),
                         beta_empirical=float(g.beta.iloc[0]),beta_refit=beta,scale_multiplier=mult,
                         scale_at_bound=bound,fixed_beta_R2=ff["R2"],fixed_beta_RMSE_mV=ff["RMSE_mV"],
                         R_residual_ohm_cm2=rec[6]/beta,R_empirical_ohm_cm2=r.Q_mV/float(g.beta.iloc[0]),
                         pass_R2=mm["R2"]>=.99,pass_R2_and_RMSE3=mm["R2"]>=.99 and mm["RMSE_mV"]<=3,**mm)
                own.append(row);local_curves.append(row);curves.append(row)
                pp=g.copy()
                pp["model"],pp["beta_refit"],pp["x_refit"],pp["vht_prediction_mV"]=name,beta,newx,prediction
                pp["kinetic_eta_mV"],pp["residual_loss_mV"]=prediction-rec[6]*newx,rec[6]*newx
                pp["fixed_beta_prediction_mV"]=fixed
                point_rows.append(pp);local_points.append(pp)
            own=pd.DataFrame(own)
            families.append(dict(model=name,condition=c,family=r.family,n_curves=len(own),
                template_RMSE_mV=metric["RMSE_mV"],template_R2=metric["R2"],template_cap_mV=CAP[c],
                within_cap=metric["RMSE_mV"]<=CAP[c]*(1+1e-5),alphaV=.5,alphaH=.5,
                log10_kH_over_kV=rec[0],log10_kT_over_kV=rec[1],kH_over_kV=10**rec[0],kT_over_kV=10**rec[1],
                DeltaG_eff_meV=-rec[2]*UNIT,current_scale_c=10**rec[3],Q_residual_mV=rec[6],
                Q_empirical_mV=r.Q_mV,b_BV_mV_dec=r.b_BV_mV_dec,
                median_R_residual=own.R_residual_ohm_cm2.median(),median_R_empirical=own.R_empirical_ohm_cm2.median(),
                fixed_beta_pass=int(own.fixed_beta_R2.ge(.99).sum()),refit_beta_pass=int(own.pass_R2.sum())))
            for x,y,yp in zip(xx[i],yy[i],pred):
                template_rows.append(dict(model=name,condition=c,family=r.family,x=x,empirical_eta_mV=y,
                    vht_eta_mV=yp,kinetic_eta_mV=yp-rec[6]*x,residual_loss_mV=rec[6]*x))
            for eta in np.linspace(0,max(pred-rec[6]*xx[i]),121):
                j,theta,vacant,V,H,T=engine.state(eta/engine.THERMAL,*rec[:3],.5,.5)
                fluxes.append(dict(model=name,condition=c,family=r.family,eta_kinetic_mV=eta,
                    current_gauge=j,theta_H=theta,vacancy=vacant,V_net=V,H_net=H,T_net=T))
        cc=pd.DataFrame(local_curves);pp=pd.concat(local_points)
        empirical=json.loads((HERE/c/"RESULT.json").read_text())
        linear=pd.read_csv(HERE/c/"ASSIGNMENTS.csv").query("kind == 'linear'")
        ff=pd.DataFrame(families).query("model == @name")
        summaries.append(dict(model=name,condition=c,n_families=len(meta),n_nonlinear_replayed=len(cc),
            template_caps_pass=int(ff.within_cap.sum()),template_RMSE_mV=result["pooled_template_RMSE_mV"],
            worst_template_RMSE_mV=float(max(result["family_RMSE_mV"])),
            fixed_beta_pass=int(cc.fixed_beta_R2.ge(.99).sum()),refit_beta_pass=int(cc.pass_R2.sum()),
            refit_beta_pass_RMSE3=int(cc.pass_R2_and_RMSE3.sum()),scale_boundary_count=int(cc.scale_at_bound.sum()),
            raw_point_RMSE_mV=float(np.sqrt(np.mean((pp.vht_prediction_mV-pp.eta_mV)**2))),
            unchanged_linear_pass=len(linear),total_with_linear=int(cc.pass_R2.sum())+len(linear),
            eligible_denominator=empirical["n_eligible"],full_cohort=empirical["n_cohort"],
            empirical_total=empirical["total_covered"],mean_R=result["mean_R"]))
    for name,rows in [("VHT_FAMILY_PARAMETERS",families),("VHT_RAW_CURVE_REPLAY",curves),
                      ("VHT_TEMPLATE_RECONSTRUCTION",template_rows),("VHT_COVERAGE_FLUX",fluxes),("VHT_SUMMARY",summaries)]:
        pd.DataFrame(rows).to_csv(HERE/f"{name}.csv",index=False)
    pd.concat(point_rows,ignore_index=True).to_csv(HERE/"VHT_RAW_POINT_REPLAY.csv",index=False)
    print(pd.DataFrame(summaries).to_string(index=False),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--workers",type=int,default=8)
    parser.add_argument("--starts",type=int,default=16)
    parser.add_argument("--refinement-starts",type=int,default=8)
    parser.add_argument("--maxiter",type=int,default=650)
    parser.add_argument("--replay-only",action="store_true")
    parser.add_argument("--select-only",action="store_true")
    args=parser.parse_args()
    paths=[HERE/c/n for c in CAP for n in ["TEMPLATES.csv","POINT_PREDICTIONS.csv","RESULT.json"]]
    paths += [VENDOR/n for n in ["independent_model.py","numerics.py"]]
    hashes={str(p):sha(p) for p in paths}
    began=time.monotonic()
    if args.select_only:
        selected=choose(json.loads((HERE/"VHT_ALL_RUNS.json").read_text()))
        (HERE/"VHT_SELECTED.json").write_text(json.dumps(selected,indent=2))
    elif args.replay_only:
        selected=json.loads((HERE/"VHT_SELECTED.json").read_text())
    else:
        jobs=[dict(s,loss=loss,maxiter=args.maxiter) for c in CAP for s in make_starts(c,args.starts) for loss in [False,True]]
        (HERE/"VHT_STARTS.json").write_text(json.dumps(jobs,indent=2))
        kinetic_and_jacobian(np.array(jobs[0]["initial"]),inputs("acid")[2])
        runs=[]
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for phase in [0,1]:
                if phase:
                    warm=choose(runs)
                    rng=np.random.default_rng(7391921)
                    refinement=[]
                    for c in CAP:
                        for loss in [False,True]:
                            for seed in range(args.refinement_starts):
                                key=c+("_residual_R_accuracy" if loss and seed%2 else "_kinetics_only")
                                p=np.array(warm[key]["params"])
                                if seed>=2:
                                    perturb=rng.normal(0,.25 if seed<5 else .8,len(p));perturb[2:4]=0
                                    p+=perturb
                                lo,hi=bounds(len(inputs(c)[0]));p=np.clip(p,lo,hi)
                                refinement.append(dict(condition=c,loss=loss,seed=args.starts+seed,initial=p.tolist(),maxiter=args.maxiter))
                    jobs.extend(refinement)
                    (HERE/"VHT_STARTS.json").write_text(json.dumps(jobs,indent=2))
                    batch=refinement
                else: batch=jobs.copy()
                futures=[pool.submit(fit_job,j) for j in batch]
                for future in as_completed(futures):
                    r=future.result();runs.append(r)
                    (HERE/"VHT_ALL_RUNS.json").write_text(json.dumps(runs,indent=2))
                    print(r["condition"],"loss",r["loss"],"seed",r["seed"],"feasible",r["feasible"],
                          "RMSE",round(r["pooled_template_RMSE_mV"],3),"max",round(max(r["family_RMSE_mV"]),3),
                          "seconds",round(r["seconds"],1),flush=True)
        selected=choose(runs)
        (HERE/"VHT_SELECTED.json").write_text(json.dumps(selected,indent=2))
    replay(selected)
    assert hashes=={str(p):sha(p) for p in paths}
    manifest=dict(settings=vars(args),seconds=time.monotonic()-began,source_sha256=hashes,script_sha256=sha(__file__),
        network="Reversible Volmer-Heyrovsky-Tafel; steady state V-H-2T=0, current=V+H; kV_forward=1 gauge",
        detailed_balance="K=kVf/kVr; kHf/kHr=1/K; kTf/kTr=1/K^2; DeltaG_eff=-kBT ln K",
        shared="Separate network per electrolyte; shared kHf/kVf and kTf/kVf; alphaV=alphaH=0.5 fixed",
        per_family="DeltaG_eff and current scale c; optional nonnegative residual Q in eta=eta_VHT(x/c)+Q*x",
        support="Full min/max normalized support of accepted empirical members, no percentile trimming",
        template_objective="Equal family and equal log-current grid weights; 160 fit points, 1000 independent dense validation points",
        caps_mV=CAP,cap_meaning="Absolute per-template RMS error against full BV+iR template, not a raw-data allowance",
        residual_loss_selection="Report accuracy-only and minimum mean per-family R under caps separately; explicit zero-R nesting control",
        raw_replay="Keep every accepted original point and family assignment. Compare fixed beta and one recalibrated beta within same template support; no independent per-curve R/offset",
        bounds=dict(log10_h=[-7,7],log10_t=[-7,7],DeltaG_meV=[-300,300],log10_c=[-8,8]),
        identifiability="Multistart representative solutions, not certified global optima or unique mechanisms",
        discovery="Fresh empirical grid; VHT starts do not read previous fitted kinetic parameters")
    (HERE/"VHT_MANIFEST.json").write_text(json.dumps(manifest,indent=2))


if __name__=="__main__": main()
