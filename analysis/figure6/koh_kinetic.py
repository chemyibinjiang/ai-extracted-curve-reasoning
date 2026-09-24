"""Fixed-alpha, zero-extra-loss VHT dimension comparison on frozen KOH targets."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import time

from paths import PACKAGE, EMPIRICAL_OUT, KOH_OUT
HERE=KOH_OUT
SOURCE=EMPIRICAL_OUT
VENDOR=PACKAGE / "vendor/vht"
os.environ["NUMBA_CACHE_DIR"]=str(HERE/"numba_cache")
for key in ["OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMBA_NUM_THREADS"]: os.environ[key]="1"
sys.dont_write_bytecode=True
sys.path.insert(0,str(VENDOR))
import independent_model as engine
from numerics import kinetic_and_jacobian, optimize_scale
import numpy as np
import pandas as pd
from numba import njit
from scipy.optimize import least_squares, minimize

UNIT=engine.KBT_MEV*np.log(10.)
KEYS=["logh","logt","logK","logc"]
SPECS={"DeltaG_only":("logK",),"DeltaG_H":("logK","logh"),
       "DeltaG_T":("logK","logt"),"independent_H_T_G":("logh","logt","logK")}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path,obj): Path(path).write_text(json.dumps(obj,indent=2),encoding="utf-8")


@lru_cache(None)
def data(count=160):
    meta=pd.read_csv(SOURCE/"KOH/TEMPLATES.csv")
    points=pd.read_csv(SOURCE/"KOH/POINT_PREDICTIONS.csv")
    points=points[points.adequate & points.kind.eq("BV+jR")].copy()
    xx=np.array([np.geomspace(r.x_min,r.x_max,count) for r in meta.itertuples()])
    yy=np.array([engine.bv_response(x,r.alpha,r.Q_mV) for x,r in zip(xx,meta.itertuples())])
    return meta,points,xx,yy


def layout(name,n=5):
    free=SPECS[name]
    ix=np.empty((n,4),dtype=np.int64)
    names,lo,hi=[],[],[]
    lows=[-7.,-7.,-300/UNIT,-8.]; highs=[7.,7.,300/UNIT,8.]
    for k,key in enumerate(KEYS):
        if key in free or key=="logc":
            for i in range(n):
                ix[i,k]=len(names);names.append(f"{key}_K{i+1}");lo.append(lows[k]);hi.append(highs[k])
        else:
            ix[:,k]=len(names);names.append(key+"_shared");lo.append(lows[k]);hi.append(highs[k])
    return ix,names,np.array(lo),np.array(hi)


def pack(records,name):
    rec=np.asarray(records)
    ix,names,lo,hi=layout(name,len(rec))
    expanded=rec[:,:4]
    p=np.zeros(len(names));count=np.zeros(len(names))
    for i in range(len(rec)):
        for k in range(4): p[ix[i,k]]+=expanded[i,k];count[ix[i,k]]+=1
    return np.clip(p/count,lo,hi)


def records(p,name):
    ix,_,_,_=layout(name)
    expanded=np.asarray(p)[ix]
    return np.column_stack([expanded,np.full((len(expanded),2),.5),np.zeros(len(expanded))])


@njit(cache=True)
def prediction_jacobian(p,xx,ix):
    n,count=xx.shape
    out=np.empty((n,count)); jac=np.zeros((n,count,len(p)))
    for i in range(n):
        q=p[ix[i]]
        single=np.array([q[0],q[1],.5,.5,q[2],q[3]])
        pred,derivative=kinetic_and_jacobian(single,xx[i:i+1])
        out[i]=pred[0]
        local=np.array([0,1,4,5])
        for k in range(4):
            for j in range(count): jac[i,j,ix[i,k]]=derivative[0,j,local[k]]
    return out,jac


def score(recs,name,source=None):
    recs=np.asarray(recs)
    _,_,x,y=data(1000)
    pred=np.array([engine.response(xx,*r) for xx,r in zip(x,recs)])
    rms=np.sqrt(np.mean((pred-y)**2,axis=1))
    p=pack(recs,name);_,names,lo,hi=layout(name)
    # Selected records must actually obey the sharing restriction.
    np.testing.assert_allclose(records(p,name),recs,rtol=1e-10,atol=1e-10)
    return dict(model=name,records=recs.tolist(),params=p.tolist(),family_RMSE_mV=rms.tolist(),
        pooled_RMSE_mV=float(np.sqrt(np.mean(rms**2))),worst_RMSE_mV=float(rms.max()),
        families_under_3mV=int((rms<=3.).sum()),n_parameters=len(p),
        boundary_parameters=[names[k] for k in np.flatnonzero(np.minimum(p-lo,hi-p)<1e-5)],source=source)


def fit_job(job):
    begun=time.monotonic()
    name=job["model"]; ix,names,lo,hi=layout(name)
    _,_,xx,yy=data()
    p0=np.clip(np.asarray(job["initial"]),lo+1e-9,hi-1e-9)

    def errors(p):
        pred,jac=prediction_jacobian(p,xx,ix)
        return pred-yy,jac

    def mean_objective(p):
        e,j=errors(p)
        return float(np.mean(e**2)/9),2*np.mean(e[:,:,None]*j,axis=(0,1))/9

    opt=least_squares(lambda p:errors(p)[0].ravel()/3,p0,
        jac=lambda p:errors(p)[1].reshape(-1,len(p))/3,bounds=(lo,hi),x_scale="jac",
        max_nfev=job["maxiter"],ftol=1e-10,xtol=1e-10,gtol=1e-7)
    p=opt.x if mean_objective(opt.x)[0]<mean_objective(p0)[0] else p0
    initial=score(records(p0,name),name,dict(stage="initial",seed=job["seed"]))
    accuracy=score(records(p,name),name,dict(stage="mean_accuracy",seed=job["seed"]))
    history=[dict(stage="least_squares",success=bool(opt.success),nfev=int(opt.nfev),message=str(opt.message))]

    def ratios(p):
        e,j=errors(p)
        return np.mean(e**2,axis=1)/9,2*np.mean(e[:,:,None]*j,axis=1)/9

    if name!="independent_H_T_G":
        def constraint(v):
            val,jac=ratios(v[:-1])
            return v[-1]-val,np.column_stack([-jac,np.ones(len(xx))])
        gradient=np.r_[np.zeros(len(p)),1.]
        mm=minimize(lambda v:(v[-1],gradient),np.r_[p,ratios(p)[0].max()],jac=True,method="SLSQP",
            bounds=list(zip(np.r_[lo,0.],np.r_[hi,1e6])),
            constraints=dict(type="ineq",fun=lambda v:constraint(v)[0],jac=lambda v:constraint(v)[1]),
            options=dict(maxiter=job["maxiter"],ftol=1e-10))
        if np.isfinite(mm.x).all() and ratios(mm.x[:-1])[0].max()<ratios(p)[0].max(): p=mm.x[:-1]
        history.append(dict(stage="minimax",success=bool(mm.success),nfev=int(mm.nit),message=str(mm.message)))
        cap=float(ratios(p)[0].max())*1.0001+1e-8
        polish=minimize(mean_objective,p,jac=True,method="SLSQP",bounds=list(zip(lo,hi)),
            constraints=dict(type="ineq",fun=lambda v:cap-ratios(v)[0],jac=lambda v:-ratios(v)[1]),
            options=dict(maxiter=min(400,job["maxiter"]),ftol=1e-10))
        if np.isfinite(polish.x).all() and ratios(polish.x)[0].max()<=cap+1e-7 and mean_objective(polish.x)[0]<mean_objective(p)[0]: p=polish.x
        history.append(dict(stage="mean_polish",success=bool(polish.success),nfev=int(polish.nit)))
    balanced=score(records(p,name),name,dict(stage="worst_family_accuracy",seed=job["seed"]))
    return dict(model=name,seed=job["seed"],snapshots=[initial,accuracy,balanced],history=history,seconds=time.monotonic()-begun)


def starting_jobs(name,count,maxiter):
    baseline=np.array(json.loads((SOURCE/"VHT_SELECTED.json").read_text())["KOH_kinetics_only"]["records"])
    rng=np.random.default_rng(20260921+sum(map(ord,name)))
    _,_,xx,yy=data()
    ix,names,lo,hi=layout(name)
    jobs=[]
    for seed in range(count):
        if seed==0: p=pack(baseline,name)
        else:
            rec=baseline.copy()
            rec[:,0]=rng.uniform(-4,4,5)
            rec[:,1]=rng.uniform(-4,4,5)
            rec[:,2]=rng.uniform(-2.5,2.5,5)
            p=pack(rec,name)
            # Sampling shared parameters directly preserves broad initial branches.
            for k,label in enumerate(names):
                if label.endswith("_shared"): p[k]=rng.uniform(-4,4)
            rec=records(p,name)
            for i,r in enumerate(rec):
                mid=len(xx[i])//2
                current=engine.state(yy[i,mid]/engine.THERMAL,*r[:3],.5,.5)[0]
                p[ix[i,3]]=np.log10(xx[i,mid]/max(current,1e-30))
        jobs.append(dict(model=name,seed=seed,initial=np.clip(p,lo+1e-9,hi-1e-9).tolist(),maxiter=maxiter))
    return jobs


def choose(runs):
    snapshots=[s for r in runs for s in r["snapshots"]]
    baseline=np.array(json.loads((SOURCE/"VHT_SELECTED.json").read_text())["KOH_kinetics_only"]["records"])
    snapshots.append(score(baseline,"DeltaG_only",dict(stage="frozen_no_R_baseline")))
    selected={}
    for name in ["DeltaG_only","DeltaG_H","DeltaG_T"]:
        legal=[s for s in snapshots if s["model"]==name]
        if name!="DeltaG_only":
            legal += [score(s["records"],name,dict(stage="nested_1D",parent=s["source"])) for s in snapshots if s["model"]=="DeltaG_only"]
        best_worst=min(s["worst_RMSE_mV"] for s in legal)
        selected[name]=min([s for s in legal if s["worst_RMSE_mV"]<=best_worst+1e-4],key=lambda s:s["pooled_RMSE_mV"])
        selected[name]=dict(selected[name],best_mean_error_RMSE_mV=min(s["pooled_RMSE_mV"] for s in legal),
                            selection="Lowest worst-family RMS; mean RMS breaks ties within 0.0001 mV")
    # No coordinates are shared in this control, so the best family fits can be combined.
    candidates=snapshots+list(selected.values())
    family_sources=[min(candidates,key=lambda s:s["family_RMSE_mV"][i]) for i in range(5)]
    rec=[s["records"][i] for i,s in enumerate(family_sources)]
    selected["independent_H_T_G"]=score(rec,"independent_H_T_G",dict(stage="best_per_family_assembly",
        parents=[dict(model=s["model"],source=s["source"]) for s in family_sources]))
    return selected


def parallel(jobs,args,runs):
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(fit_job,j) for j in jobs]
        for future in as_completed(futures):
            r=future.result();runs.append(r)
            dump(HERE/"ALL_RUNS.json",runs)
            s=min(r["snapshots"],key=lambda s:s["worst_RMSE_mV"])
            print(r["model"],"seed",r["seed"],"worst",round(s["worst_RMSE_mV"],3),
                  "pooled",round(s["pooled_RMSE_mV"],3),"sec",round(r["seconds"],1),flush=True)


def evaluate(selected):
    meta,points,xx,yy=data(1000)
    summary,curves,point_frames,families,grid_rows,flux=[] ,[],[],[],[],[]
    for name,s in selected.items():
        local=[];raw=[]
        for i,(m,r) in enumerate(zip(meta.itertuples(),s["records"])):
            predictor=lambda x:engine.response(np.asarray(x,dtype=float),*r)
            pred=predictor(xx[i]);own=[]
            for uid,g in points[points.family.eq(m.family)].groupby("curve_uid"):
                x,y=g.x.to_numpy(),g.eta_mV.to_numpy()
                fixed=predictor(x)
                mult,lo,hi,bound=optimize_scale(x,y,predictor,m.x_min,m.x_max)
                newx=x/mult;prediction=predictor(newx)
                fixed_metric=engine.metrics(y,fixed);mm=engine.metrics(y,prediction)
                row=dict(model=name,family=m.family,curve_uid=uid,n_points=len(g),
                    beta_empirical=float(g.beta.iloc[0]),beta_refit=float(g.beta.iloc[0])*mult,scale_multiplier=mult,
                    scale_at_bound=bound,fixed_beta_R2=fixed_metric["R2"],fixed_beta_RMSE_mV=fixed_metric["RMSE_mV"],
                    pass_R2=mm["R2"]>=.99,pass_R2_RMSE3=mm["R2"]>=.99 and mm["RMSE_mV"]<=3,**mm)
                own.append(row);local.append(row);curves.append(row)
                pp=g.copy();pp["model"],pp["x_refit"],pp["vht_eta_mV"]=name,newx,prediction
                pp["beta_refit"],pp["fixed_beta_prediction_mV"]=row["beta_refit"],fixed
                point_frames.append(pp);raw.append(pp)
            own=pd.DataFrame(own)
            families.append(dict(model=name,family=m.family,n_curves=len(own),
                template_RMSE_mV=s["family_RMSE_mV"][i],DeltaG_eff_meV=-r[2]*UNIT,
                log10_kH_over_kV=r[0],log10_kT_over_kV=r[1],kH_over_kV=10**r[0],kT_over_kV=10**r[1],
                alphaV=r[4],alphaH=r[5],current_scale_c=10**r[3],Q_residual_mV=r[6],
                fixed_beta_pass=int(own.fixed_beta_R2.ge(.99).sum()),refit_beta_pass=int(own.pass_R2.sum())))
            for x,y,yp in zip(xx[i],yy[i],pred):
                grid_rows.append(dict(model=name,family=m.family,x=x,empirical_eta_mV=y,vht_eta_mV=yp))
            for eta in np.linspace(0,min(300,max(pred)),151):
                j,theta,vac,V,H,T=engine.state(eta/engine.THERMAL,*r[:3],.5,.5)
                flux.append(dict(model=name,family=m.family,eta_kinetic_mV=eta,current_gauge=j,
                                 theta_H=theta,vacancy=vac,V_net=V,H_net=H,T_net=T))
        cc=pd.DataFrame(local);pp=pd.concat(raw)
        summary.append(dict(model=name,family_kinetic_dimensions=len(SPECS[name]),n_parameters=s["n_parameters"],
            pooled_template_RMSE_mV=s["pooled_RMSE_mV"],worst_template_RMSE_mV=s["worst_RMSE_mV"],
            families_under_3mV=s["families_under_3mV"],fixed_beta_pass=int(cc.fixed_beta_R2.ge(.99).sum()),
            refit_beta_pass=int(cc.pass_R2.sum()),refit_beta_pass_RMSE3=int(cc.pass_R2_RMSE3.sum()),
            nonlinear_curves=len(cc),raw_point_RMSE_mV=float(np.sqrt(np.mean((pp.vht_eta_mV-pp.eta_mV)**2))),
            scale_boundary_count=int(cc.scale_at_bound.sum()),unchanged_linear_pass=29,
            total_with_linear=29+int(cc.pass_R2.sum()),eligible_denominator=263,full_cohort=267,
            boundary_parameters=";".join(s["boundary_parameters"])))
    for name,rows in [("SUMMARY",summary),("FAMILY_PARAMETERS",families),("RAW_CURVE_REPLAY",curves),
                      ("TEMPLATE_RECONSTRUCTION",grid_rows),("COVERAGE_FLUX",flux)]:
        pd.DataFrame(rows).to_csv(HERE/f"{name}.csv",index=False)
    pd.concat(point_frames,ignore_index=True).to_csv(HERE/"RAW_POINT_REPLAY.csv",index=False)
    print(pd.DataFrame(summary).to_string(index=False),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--workers",type=int,default=8)
    parser.add_argument("--starts",type=int,default=16)
    parser.add_argument("--refine-starts",type=int,default=6)
    parser.add_argument("--maxiter",type=int,default=700)
    parser.add_argument("--replay-only",action="store_true")
    args=parser.parse_args();begun=time.monotonic()
    sources=[SOURCE/"KOH"/n for n in ["TEMPLATES.csv","POINT_PREDICTIONS.csv","RESULT.json"]]
    sources += [SOURCE/"VHT_SELECTED.json",VENDOR/"independent_model.py",VENDOR/"numerics.py"]
    hashes={str(p):sha(p) for p in sources}
    meta,points,_,_=data()
    assert len(meta)==5 and points.curve_uid.nunique()==195
    meta.to_csv(HERE/"FROZEN_TEMPLATES.csv",index=False)
    if args.replay_only:
        selected=choose(json.loads((HERE/"ALL_RUNS.json").read_text()))
    else:
        jobs=[j for name in SPECS for j in starting_jobs(name,args.starts,args.maxiter)]
        dump(HERE/"STARTS.json",jobs)
        prediction_jacobian(np.array(jobs[0]["initial"]),data()[2],layout(jobs[0]["model"])[0])
        runs=[];parallel(jobs,args,runs)
        selected=choose(runs)
        rng=np.random.default_rng(301922)
        refine=[]
        for name in SPECS:
            for seed in range(args.refine_starts):
                if seed==1 and name!="independent_H_T_G": p=pack(selected["independent_H_T_G"]["records"],name)
                else: p=np.array(selected[name]["params"])
                if seed>=2: p+=rng.normal(0,.2 if seed<4 else .65,len(p))
                ix,names,lo,hi=layout(name)
                refine.append(dict(model=name,seed=args.starts+seed,initial=np.clip(p,lo+1e-9,hi-1e-9).tolist(),maxiter=args.maxiter))
        jobs+=refine;dump(HERE/"STARTS.json",jobs)
        parallel(refine,args,runs)
        selected=choose(runs)
    dump(HERE/"SELECTED_MODELS.json",selected)
    evaluate(selected)
    assert hashes=={str(p):sha(p) for p in sources}
    manifest=dict(settings=vars(args),seconds=time.monotonic()-begun,source_sha256=hashes,script_sha256=sha(__file__),
        templates="Frozen fresh KOH five-template library; original 0-300 mV observations, 195 empirical nonlinear passes",
        specs={k:list(v) for k,v in SPECS.items()},no_extra_R=True,no_voltage_offset=True,alphaV=.5,alphaH=.5,
        current_scale="One family c is always free and not counted as a kinetic shape coordinate",
        detailed_balance="K=kVf/kVr; kHf/kHr=1/K; kTf/kTr=1/K^2; DeltaG_eff=-kBT ln K",
        steady_state="rV-rH-2*rT=0, current proportional to rV+rH",
        objective="Equal family/log-current grid weights; 160 fit points and independent 1000-point dense check",
        selection="Lowest worst-family RMS, then lowest pooled RMS within 0.0001 mV; nested 1D candidates retained in both 2D pools",
        independent_control="Best per-family solutions assembled legally; no shared coordinates, not a rigorous global lower bound",
        raw_replay="Same 195 curves and every original in-window point, fixed family; unchanged beta and one recalibrated beta, no support extrapolation",
        threshold="R2_eta>=0.99 on original points; absolute template cap 3 mV is reported separately",
        bounds=dict(log10_rate_ratios=[-7,7],DeltaG_meV=[-300,300],log10_c=[-8,8]),
        limits="Numerical multistart search within fixed reduced VHT model; not proof of a unique mechanism or global impossibility")
    dump(HERE/"MANIFEST.json",manifest)


if __name__=="__main__": main()
