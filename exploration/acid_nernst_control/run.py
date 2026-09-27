"""Matched acid Pt/C test: concentration polarization, effective BV and VHT replay."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import sys

for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[key] = '1'
os.environ.setdefault('NUMBA_NUM_THREADS','4')

import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
from model import ROOT, bv, fit, predict, metrics, profile_grid

sys.path.append(str(ROOT/'analysis/figure6/vendor/empirical'))
import coverage_solver as coverage


def read(path):
    return pd.read_csv(path, float_precision='round_trip')


def dump(path, value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def save(path, rows):
    pd.DataFrame(rows).to_csv(path,index=False,lineterminator='\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fit_models(j,y,references=None):
    n = fit(j,y,False)
    nr = fit(j,y,True)
    b = bv.fit(j,y,False,[(n['log_jL'],.99,2.,0.)] +
               ([bv.seed(references['BV'])] if references else []))
    br = bv.fit(j,y,True,[bv.seed(b),(nr['log_jL'],.99,2.,nr['R'])] +
                ([bv.seed(references['BV+jR'])] if references else []))
    return {'Nernst':n,'Nernst+jR':nr,'BV':b,'BV+jR':br}


def prediction(j,name,row):
    return predict(j,row) if name.startswith('Nernst') else bv.predict(j,row)


def worker(job):
    uid, j, y, indices = job
    fits = fit_models(j,y)
    rows, preds, cv = [],[],[]
    for name,r in fits.items():
        rows.append(dict(curve_uid=uid,model=name,**r))
        yp = prediction(j,name,r)
        preds.extend(dict(curve_uid=uid,fit_point_index=int(index),model=name,j_mA_cm2=x,
                          eta_mV=actual,prediction_mV=value) for index,x,actual,value in zip(indices,j,y,yp))
    # Interleaved three-fold prediction: model fitting never sees a held-out point.
    for fold in range(3):
        test = np.arange(len(j))%3 == fold
        train = ~test
        own = fit_models(j[train],y[train])
        for name,r in own.items():
            yp = prediction(j[test],name,r)
            cv.extend(dict(curve_uid=uid,fold=fold,fit_point_index=int(index),model=name,
                           j_mA_cm2=x,eta_mV=actual,prediction_mV=value)
                for index,x,actual,value in zip(indices[test],j[test],y[test],yp))
    return rows,preds,cv


def summary(fits):
    rows=[]
    for name,g in fits.groupby('model',sort=False):
        rows.append(dict(model=name,curves=len(g),accepted=int(g.r2.ge(.99).sum()),
            median_rmse_mV=float(g.rmse.median()),pooled_rmse_mV=float(np.sqrt(g.sse.sum()/g.n.sum())),
            median_R2=float(g.r2.median()),points=int(g.n.sum())))
    return rows


def template_test(source,output):
    frame=read(source/'figure6/TEMPLATE_RECONSTRUCTION.csv')
    frame=frame[frame.condition.eq('acid') & frame.model.eq('DeltaG_only')]
    rows,points=[],[]
    for family,g in frame.groupby('family'):
        for name,resistance in [('Nernst',False),('Nernst+jR',True)]:
            row=fit(g.x.to_numpy(),g.empirical_eta_mV.to_numpy(),resistance)
            yp=predict(g.x.to_numpy(),row)
            rows.append(dict(family=family,model=name,**row))
            points.extend(dict(family=family,model=name,x=x,reference_mV=y,prediction_mV=v)
                for x,y,v in zip(g.x,g.empirical_eta_mV,yp))
        rows.append(dict(family=family,model='VHT (shared rates, DeltaG-only)',
                         **metrics(g.empirical_eta_mV,g.vht_eta_mV)))
        points.extend(dict(family=family,model='VHT',x=x,reference_mV=y,prediction_mV=v)
            for x,y,v in zip(g.x,g.empirical_eta_mV,g.vht_eta_mV))
    save(output/'TEMPLATE_FITS.csv',rows)
    save(output/'TEMPLATE_PREDICTIONS.csv',points)
    return rows


def family_test(groups,source,output):
    ids=sorted(groups)
    N=np.array([len(groups[u]) for u in ids])
    J,Y=np.ones((len(ids),max(N))),np.zeros((len(ids),max(N)))
    for i,u in enumerate(ids):
        J[i,:N[i]],Y[i,:N[i]]=groups[u].j_mA_cm2,groups[u].eta_mV
    limits=np.array([.01*np.sum((Y[i,:n]-Y[i,:n].mean())**2) for i,n in enumerate(N)])
    # The coarser grid matches the Q coordinates used in the previous discovery.
    coarse=np.unique(np.r_[0.,1e-12,1e-10,1e-8,1e-6,1e-5,np.logspace(-4,3,141),
                           10.**np.array([4,5,6,7,8,9,9.5,9.9,10])])
    fine=np.unique(np.r_[coarse,np.logspace(-4,3,561)])
    S,Z=profile_grid(J,Y,N,fine)
    np.savez_compressed(output/'FAMILY_PROFILES.npz',S=S,Z=Z,ids=np.array(ids),Q=fine)
    scans=[]
    choices={}
    for name,allowed in [('matched_Q_grid',np.flatnonzero(np.isin(fine,coarse))),('refined_Q_grid',np.arange(len(fine)))]:
        prep=coverage.prepare(S,limits,np.arange(len(ids)),allowed)
        for k in range(1,11):
            sol=coverage.solve(prep,k,time_limit=60.)
            row=dict(grid=name,K=k,shape_parameters=k,denominator=len(ids),**sol)
            scans.append(row)
            if name=='refined_Q_grid':
                choices[k]=sol
        print(name,[(r['K'],r['covered']) for r in scans if r['grid']==name],flush=True)
    save(output/'COVERAGE_SCAN.csv',scans)
    selected_k=next((k for k,r in choices.items() if r['covered'] >= np.ceil(.8*len(ids))),None)
    chosen=choices[selected_k or 10]
    selected=sorted(chosen['selected'],key=lambda k:fine[k])
    assignments=[]
    for i,uid in enumerate(ids):
        k=min(selected,key=lambda k:S[k,i])
        assignments.append(dict(curve_uid=uid,template='N'+str(selected.index(k)+1),Q_mV=fine[k],
            beta=np.exp(Z[k,i]),R=fine[k]*np.exp(-Z[k,i]),rmse=np.sqrt(S[k,i]/N[i]),
            r2=1-.01*S[k,i]/limits[i],adequate=bool(S[k,i]<=limits[i])))
    save(output/'NERNST_ASSIGNMENTS.csv',assignments)
    save(output/'NERNST_TEMPLATES.csv',[dict(template='N'+str(i+1),Q_mV=float(fine[k])) for i,k in enumerate(selected)])
    # Paper-blocked shape transfer, using the same deterministic folds as Figure 6.
    meta=read(ROOT/'analysis/figure6/inputs/acidic/cohort_metadata.csv').set_index('curve_uid')
    paper=meta.loc[ids,'paper_key'].astype(str).to_numpy()
    unique=sorted(set(paper),key=lambda p:hashlib.sha256(p.encode()).hexdigest())
    mapping={p:i%5 for i,p in enumerate(unique)}
    folds=np.array([mapping[p] for p in paper])
    cv=[]
    for fold in range(5):
        train,test=np.flatnonzero(folds!=fold),np.flatnonzero(folds==fold)
        prep=coverage.prepare(S,limits,train)
        for k in range(1,7):
            sol=coverage.solve(prep,k,time_limit=60.)
            passed=(S[np.ix_(sol['selected'],test)]<=limits[test]).any(axis=0)
            cv.append(dict(fold=fold,K=k,train_n=len(train),train_covered=sol['covered'],
                train_certified=sol['certified_count'],test_n=len(test),test_covered=int(passed.sum())))
    save(output/'PAPER_CV.csv',cv)
    return dict(minimum_K_80_percent=selected_k,selected=chosen,Q_mV=[float(fine[k]) for k in selected],
                coarse_candidates=len(coarse),fine_candidates=len(fine),
                all_counts_certified=all(r['certified_count'] for r in scans))


def run(args):
    out=args.output
    out.mkdir(parents=True,exist_ok=True)
    source=args.source
    pp=read(source/'figure6/acid/POINT_PREDICTIONS.csv')
    groups={u:g.sort_values(['j_mA_cm2','fit_point_index']) for u,g in pp.groupby('curve_uid')}
    assert len(groups)==73
    protocol=dict(paper='Prats and Chan, PCCP 2021, DOI 10.1039/D1CP04134G, main Eq. 4; ESI S2-S3',
        condition='0.5 M H2SO4',curves=73,window_mV=[0,200],linear_curves_excluded=5,
        objective='Equal-point voltage SSE; same points and R2 >= 0.99 criterion as Figure 6',
        nernst='eta_mV = (RT/2F)*1000*ln(1+j/jL) + R*j, positive cathodic magnitudes',
        nernst_assumptions='Steady state, infinitely fast interfacial kinetics, defined bulk H2 and transport boundary; H+ transport neglected in this limiting form',
        inference='Shape-compatibility control, not evidence that individual experiments meet the transport assumptions',
        nernst_bounds=dict(jL=[1e-12,1e8],R=[0,100]),BV_protocol=bv.PROTOCOL,
        BV_endpoint_note='Published BV fraction bounds [.01,.99] exclude the exact alpha_c=2, alpha_a=0 Nernst boundary; do not assert strict numerical nesting',
        point_CV='Three interleaved folds per curve; both initialization and fitting use training points only',
        family_CV='Five paper-blocked folds; held-out curves recalibrate amplitude, so this is shape transfer, not held-out-point prediction',
        VHT_comparison='Replay the existing four-template DeltaG-only model on the same 59 selected members; no new independent per-curve VHT fit',
        manuscript_and_figures_modified=False)
    inputs=[source/'figure6/acid/POINT_PREDICTIONS.csv',source/'figure6/acid/TEMPLATES.csv',
        source/'figure6/RAW_VHT_REPLAY.csv',source/'figure6/TEMPLATE_RECONSTRUCTION.csv',
        ROOT/'analysis/figure6/inputs/acidic/cohort_metadata.csv',Path(__file__),Path(__file__).with_name('model.py'),
        ROOT/'analysis/common/effective_bv.py',ROOT/'analysis/figure6/vendor/empirical/coverage_solver.py']
    protocol['hashes']={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    old=out/'PROTOCOL.json'
    if old.exists():
        assert json.loads(old.read_text())['hashes']==protocol['hashes'],'Code/input changed: use another output directory'
    dump(old,protocol)
    completed=out/'CURVE_FITS.csv'
    if not completed.exists():
        fits,predictions,cv=[],[],[]
        jobs=[(u,g.j_mA_cm2.to_numpy(),g.eta_mV.to_numpy(),g.fit_point_index.to_numpy()) for u,g in groups.items()]
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for number,result in enumerate(as_completed([pool.submit(worker,j) for j in jobs]),1):
                a,b,c=result.result();fits.extend(a);predictions.extend(b);cv.extend(c)
                print(f'Acid curve {number}/73 complete (full fit and 3-fold prediction)',flush=True)
        save(completed,sorted(fits,key=lambda r:(r['curve_uid'],r['model'])))
        save(out/'POINT_PREDICTIONS.csv',predictions)
        save(out/'HELDOUT_POINTS.csv',cv)
    fits=read(completed)
    cv=read(out/'HELDOUT_POINTS.csv')
    cvfits=[dict(curve_uid=u,model=m,**metrics(g.eta_mV,g.prediction_mV)) for (u,m),g in cv.groupby(['curve_uid','model'])]
    save(out/'HELDOUT_METRICS.csv',cvfits)
    current=read(source/'figure6/RAW_VHT_REPLAY.csv')
    current=current[current.condition.eq('acid') & current.model.eq('DeltaG_only')]
    assert len(current)==59
    shared=fits[fits.curve_uid.isin(current.curve_uid)].copy()
    vrows=[]
    for r in current.itertuples():
        n=len(groups[r.curve_uid])
        vrows.append(dict(curve_uid=r.curve_uid,model='VHT family replay',n=n,
            rmse=r.RMSE_mV,r2=r.R2,sse=r.RMSE_mV**2*n))
    shared=pd.concat([shared,pd.DataFrame(vrows)],ignore_index=True)
    save(out/'SHARED_59_FITS.csv',shared)
    results=dict(full_population=summary(fits),heldout_points=summary(pd.DataFrame(cvfits)),
                 shared_59_members=summary(shared))
    save(out/'MODEL_SUMMARY.csv',results['full_population'])
    save(out/'HELDOUT_SUMMARY.csv',results['heldout_points'])
    save(out/'SHARED_59_SUMMARY.csv',results['shared_59_members'])
    results['template_fits']=template_test(source,out)
    results['families']=family_test(groups,source,out)
    dump(out/'RESULTS.json',results)
    from report import render
    render(out,source)
    print(json.dumps({k:v for k,v in results.items() if k!='template_fits'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'build/effective-bv-20260927')
    parser.add_argument('--output',type=Path,default=ROOT/'build/acid-nernst-control-20260927')
    parser.add_argument('--workers',type=int,default=4)
    run(parser.parse_args())
