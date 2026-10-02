"""Label-blind pooled partial-observation shape model and leakage-safe paper CV."""
from utils import *
import partial_model as f
from concurrent.futures import ProcessPoolExecutor
import argparse
import hashlib

OUT=ROOT/'08_PARTIAL_PCA_CANDIDATE'


def observe(x,y):
    result=np.full(len(f.GRID),np.nan)
    for k,t in enumerate(f.GRID):
        pos=np.searchsorted(x,t)
        if pos<len(x) and np.isclose(x[pos],t,atol=1e-8,rtol=0):
            result[k]=y[pos]
        elif 0<pos<len(x) and x[pos]-x[pos-1]<=20+1e-9:
            result[k]=np.interp(t,x[pos-1:pos+1],y[pos-1:pos+1])
    return result


def prepare():
    OUT.mkdir(exist_ok=True)
    master=pd.read_csv(DATA/'cohort_master.csv')
    base=master[master.eligible].copy()
    series=load_series();obs=[];audit=[]
    for row in base.itertuples():
        x,y=series[row.curve_uid];v=observe(x,y);ok=np.isfinite(v)
        n=int(ok.sum());span=np.ptp(f.GRID[ok]) if n else 0
        native=int(((x>=20)&(x<=300)).sum())
        audit.append(dict(curve_uid=row.curve_uid,n_cells=n,span_mV=span,n_native=native,
                          start=f.GRID[ok][0] if n else np.nan,end=f.GRID[ok][-1] if n else np.nan,
                          partial_eligible=n>=4 and span>=30 and native>=4))
        obs.append(v)
    audit=pd.DataFrame(audit);base=base.merge(audit,on='curve_uid',validate='one_to_one')
    base.to_csv(OUT/'SUPPORT_AUDIT.csv',index=False)
    keep=base.partial_eligible.to_numpy();meta=base[keep].reset_index(drop=True);y=np.array(obs)[keep]
    papers=np.array(sorted(meta.paper_key.unique()));np.random.default_rng(SEED+30).shuffle(papers)
    meta['fold']=meta.paper_key.map({p:i%3 for i,p in enumerate(papers)})
    meta.to_csv(OUT/'COHORT.csv',index=False)
    np.savez_compressed(OUT/'OBSERVATIONS.npz',y=y,grid=f.GRID,curve_uid=meta.curve_uid.to_numpy(str))
    tasks=[]
    for i,row in meta.iterrows():
        x,v=series[row.curve_uid]
        for cutoff in [100,150,200]:
            tr=x<=cutoff;te=x>cutoff
            train=observe(x[tr],v[tr]);truth=observe(x[te],v[te])
            if np.isfinite(train).sum()>=4 and np.isfinite(truth).sum()>=3:
                tasks.append((i,f'tail_{cutoff}',train,truth))
        inside=(x>=20)&(x<=300)
        if inside.sum()>=8:
            lo,hi=np.quantile(x[inside],[1/3,2/3]);te=(x>=lo)&(x<=hi);tr=~te
            train=observe(x[tr],v[tr]);truth=observe(x[te],v[te])
            # Interpolated training cells inside the removed block are not training observations.
            train[(f.GRID>=lo)&(f.GRID<=hi)]=np.nan
            if np.isfinite(train).sum()>=4 and np.isfinite(truth).sum()>=3:
                tasks.append((i,'internal_block',train,truth))
    np.savez_compressed(OUT/'CV_TASKS.npz',index=np.array([x[0] for x in tasks]),
                        kind=np.array([x[1] for x in tasks]),train=np.array([x[2] for x in tasks]),
                        truth=np.array([x[3] for x in tasks]))
    print('Partial cohort:',len(meta),'curves;',meta.paper_key.nunique(),'papers;',len(tasks),'CV masks',flush=True)
    return meta,y


def job(setting):
    fold,rank,smooth=setting
    m=pd.read_csv(OUT/'COHORT.csv');y=np.load(OUT/'OBSERVATIONS.npz')['y'];task=np.load(OUT/'CV_TASKS.npz')
    tr=m.fold.ne(fold).to_numpy();ids=task['index'];which=m.iloc[ids].fold.eq(fold).to_numpy()
    assert not set(m[tr].paper_key)&set(m[~tr].paper_key)
    model=f.fit(y[tr],weights(m[tr]),rank,smooth,max_iter=4000)
    p=task['train'][which];truth=task['truth'][which];ix=ids[which]
    inferred=f.infer(model,p);full=f.infer(model,y[ix])
    var=f.prediction_variance(model,p,inferred)+model['sigma2']
    rows=[]
    for k,i in enumerate(ix):
        valid=np.isfinite(truth[k]);err=inferred['prediction'][k,valid]-truth[k,valid]
        rows.append(dict(fold=fold,rank=rank,smoothing=smooth,curve_uid=m.iloc[i].curve_uid,
            paper_key=m.iloc[i].paper_key,condition=m.iloc[i].condition,group=m.iloc[i].group,
            mask=task['kind'][which][k],rmse=np.sqrt(np.mean(err**2)),bias=err.mean(),
            coverage95=np.mean(np.abs(err)<=1.96*np.sqrt(var[k,valid])),
            score_shift=np.linalg.norm(inferred['score'][k]-full['score'][k]),
            full_score_norm=np.linalg.norm(full['score'][k]),masked_score_norm=np.linalg.norm(inferred['score'][k]),
            score_uncertainty=np.trace(inferred['covariance'][k]),n_train=np.isfinite(p[k]).sum(),
            n_test=int(valid.sum()),fit_converged=model['converged'],iterations=model['iterations']))
    return rows


def tune():
    tasks=[(fold,k,s) for fold in range(3) for k in [1,2,3,4] for s in [10.,1000.]]
    rows=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for i,result in enumerate(pool.map(job,tasks),1):
            rows.extend(result)
            pd.DataFrame(rows).to_csv(OUT/'CV_ERRORS.csv',index=False)
            print(f'Whole-paper held-out model {i}/{len(tasks)}; converged={all(r["fit_converged"] for r in result)}',flush=True)
    errors=pd.DataFrame(rows)
    per_curve=errors.groupby(['rank','smoothing','paper_key','curve_uid']).rmse.mean().reset_index()
    per_paper=per_curve.groupby(['rank','smoothing','paper_key']).rmse.mean().reset_index()
    summary=per_paper.groupby(['rank','smoothing']).rmse.agg(['mean','std','count']).reset_index()
    summary['se']=summary['std']/np.sqrt(summary['count'])
    convergence=errors.groupby(['rank','smoothing']).fit_converged.all()
    summary['all_fits_converged']=[convergence.loc[(r.rank,r.smoothing)] for r in summary.itertuples()]
    summary.to_csv(OUT/'CV_SUMMARY.csv',index=False)
    acceptable=summary[summary.all_fits_converged]
    if acceptable.empty:raise RuntimeError('No converged cross-validation candidates')
    best=acceptable.loc[acceptable['mean'].idxmin()];threshold=best['mean']+best.se
    chosen=acceptable[acceptable['mean']<=threshold].sort_values(['rank','smoothing'],ascending=[True,False]).iloc[0]
    setting=dict(rank=int(chosen['rank']),smoothing=float(chosen.smoothing),mean_rmse=float(chosen['mean']),
                 threshold=float(threshold),minimum_rmse=float(best['mean']))
    dump(OUT/'SELECTED.json',setting)
    return setting


def group_diagnostics(meta,score,cov):
    rows=[]
    for condition in ['pooled',*CONDITIONS]:
        cm=meta if condition=='pooled' else meta[meta.condition.eq(condition)]
        strata=(cm.condition.astype(str)+'_'+(cm.start//50).astype(int).astype(str)+'_'+(cm.end//50).astype(int).astype(str))
        sets={};masses={}
        for g in GROUPS:
            z=cm[cm.group.eq(g)];w=weights(z);ids=z.index.to_numpy()
            sets[g]=(ids,w);masses[g]=pd.Series(w,index=strata.loc[ids]).groupby(level=0).sum()
        target=pd.concat(masses,axis=1).fillna(0).min(axis=1);target=target[target>0];target/=target.sum()
        for matched in [False,True]:
            for g,(ids,original) in sets.items():
                w=original.copy()
                if matched:
                    w*=np.array([target.get(s,0)/masses[g][s] for s in strata.loc[ids]])
                good=w>0;ix=ids[good];w=w[good];w/=w.sum()
                mu=w@score[ix];naive=w@np.sum((score[ix]-mu)**2,axis=1)
                added=(w*(1-w))@np.trace(cov[ix],axis1=1,axis2=2)
                rows.append(dict(condition=condition,support_matched=matched,group=g,
                    curves=len(ix),papers=meta.loc[ix].paper_key.nunique(),PC1=mu[0],PC2=mu[1] if len(mu)>1 else 0,
                    posterior_mean_RMS=np.sqrt(naive),uncertainty_aware_RMS=np.sqrt(naive+added),
                    uncertainty_share=added/(naive+added),mean_cells=w@meta.loc[ix,'n_cells']))
    pd.DataFrame(rows).to_csv(OUT/'GROUP_DIAGNOSTICS.csv',index=False)


def native_points():
    source=INPUT/'RESCALED_NATIVE_POINTS.csv';p=pd.read_csv(source)
    pairs=pd.read_csv(INPUT/'MEMBER_COMPATIBILITY.csv')
    assert not p.duplicated(['template','curve_uid','point_index']).any()
    beta=pairs.set_index(['template','curve_uid']).current_scale_beta
    actual=beta.reindex(pd.MultiIndex.from_frame(p[['template','curve_uid']])).to_numpy()
    assert np.allclose(p.current_scale_beta,actual)
    assert np.allclose(p.current_template_units,p.j_original/p.current_scale_beta)
    raw=np.load(INPUT/'NATIVE_CURVES.npz');ix=pd.Index(raw['curve_uid']).get_indexer(p.curve_uid)
    assert (ix>=0).all();point=p.point_index.to_numpy(int)
    assert np.allclose(p.j_original,raw['J'][ix,point])
    assert np.allclose(p.eta_mV,raw['Y'][ix,point])
    profiles=pd.read_csv(DATA/'template_profiles.csv')
    anchor=profiles[profiles.eta_mV.eq(50)].set_index('template').log10_template_current
    p['aligned_log_current']=np.log10(p.current_template_units)-p.template.map(anchor)
    p.to_csv(OUT/'TEMPLATE_NATIVE_POINTS.csv',index=False)
    dump(OUT/'NATIVE_POINTS_PROVENANCE.json',dict(source='01_PROVENANCE/inputs/RESCALED_NATIVE_POINTS.csv',
        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),points=len(p),unique_curves=p.curve_uid.nunique(),
        matches=len(p[['template','curve_uid']].drop_duplicates()),
        plotted_points=int(p.eta_mV.between(50,300).sum()),
        alignment='log10(j_original/beta) - log10(template_current_at_50mV); beta is the archived compatibility amplitude; no refit'))


def finish(m,y,setting):
    model=f.fit(y,weights(m),setting['rank'],setting['smoothing'],max_iter=6000)
    if not model['converged']:raise RuntimeError('Final factor model has not converged')
    result=f.infer(model,y);scales=np.linalg.norm(model['load'],axis=0)
    shifted=f.infer(model,y+np.random.default_rng(SEED).normal(size=(len(y),1))*2)
    difference=float(np.max(np.abs(result['score']-shifted['score'])))
    assert difference<1e-7
    np.savez_compressed(OUT/'MODEL.npz',**model,grid=f.GRID,basis=f.B,penalty=f.P)
    np.savez_compressed(OUT/'POSTERIOR.npz',**result,curve_uid=m.curve_uid.to_numpy(str))
    scores=m.copy()
    for k in range(setting['rank']):
        scores[f'PC{k+1}']=result['score'][:,k];scores[f'PC{k+1}_sd']=np.sqrt(result['covariance'][:,k,k])
    scores['reliability']=1-np.trace(result['covariance'],axis1=1,axis2=2)/(scales@scales)
    scores.to_csv(OUT/'SCORES.csv',index=False)
    group_diagnostics(m,result['score'],result['covariance'])
    profiles=pd.read_csv(DATA/'template_profiles.csv');template_rows=[];ty=[];names=[]
    for name,q in profiles.groupby('template',sort=False):
        values=np.interp(f.GRID,q.eta_mV,q.log10_template_current,left=np.nan,right=np.nan)
        ty.append(values);names.append(name)
    ty=np.array(ty);projection=f.infer(model,ty)
    for i,name in enumerate(names):
        q=profiles[profiles.template.eq(name)];known=np.isfinite(ty[i])
        error=projection['prediction'][i,known]-ty[i,known]
        row=dict(template=name,kind=q.kind.iloc[0],PGM_rich=name in RICH,n_cells=known.sum(),
                 first_mV=f.GRID[known][0],last_mV=f.GRID[known][-1],observed_RMSE=np.sqrt(np.mean(error**2)))
        for k in range(setting['rank']):row[f'PC{k+1}']=projection['score'][i,k]
        row['projection_uncertainty']=np.trace(projection['covariance'][i])
        template_rows.append(row)
    pd.DataFrame(template_rows).to_csv(OUT/'TEMPLATE_PROJECTIONS.csv',index=False)
    np.savez_compressed(OUT/'TEMPLATE_POSTERIOR.npz',**projection,observed=ty,template=np.array(names))
    # Compare direct full-function coordinates to the regularized observation operator.
    complete=np.isfinite(ty).all(1);design=np.column_stack([np.ones(len(f.GRID)),f.B@model['load']])
    direct=np.linalg.lstsq(design,ty[complete].T-(f.B@model['mu'])[:,None],rcond=None)[0][1:].T*scales
    direct_delta=np.linalg.norm(direct-projection['score'][complete],axis=1)
    selected_cv=pd.read_csv(OUT/'CV_ERRORS.csv')
    selected_cv=selected_cv[selected_cv['rank'].eq(setting['rank'])&selected_cv.smoothing.eq(setting['smoothing'])]
    selected_cv.to_csv(OUT/'SELECTED_CV_ERRORS.csv',index=False)
    diagnostics=selected_cv.groupby(['condition','group','mask']).agg(rmse=('rmse','mean'),coverage95=('coverage95','mean'),
        score_shift=('score_shift','mean'),masked_score_norm=('masked_score_norm','mean'),full_score_norm=('full_score_norm','mean'),
        curves=('curve_uid','nunique'),papers=('paper_key','nunique')).reset_index()
    diagnostics.to_csv(OUT/'MASK_DIAGNOSTICS.csv',index=False)
    native_points()
    dump(OUT/'CHECKS.json',dict(curves=len(m),papers=m.paper_key.nunique(),converged=model['converged'],
        iterations=model['iterations'],amplitude_invariance_error=difference,
        factor_variance_fraction=(scales**2/(scales@scales)).tolist(),
        full_template_direct_vs_regularized_max=float(direct_delta.max()),
        fitting_labels_used=False,template_fit_gate=False,templates_used_to_train=False))
    dump(OUT/'PROTOCOL.json',dict(window=[20,300],grid_step=10,max_interpolation_gap=20,min_cells=4,min_span=30,min_native=4,
        model='Pooled penalized probabilistic functional factor model with diffuse curve intercept; not classical complete-data PCA or PACE.',
        amplitude='Free intercept removes a constant vertical log-current offset without requiring a measured anchor.',
        fit='Only observed cells enter the likelihood. Equal papers, equal curves within paper. Composition/condition/template labels do not fit or tune the model.',
        validation='3-fold whole-paper holdout. Tail and internal masks are applied to native points BEFORE interpolation; train/test use disjoint native observations. One-SE rule favors lower rank then stronger smoothness. Nonconverged candidates excluded.',
        score='Conditional posterior mean; short segments shrink toward a shared, group-blind prior. Score covariance retained. Main plotted points are estimates, not fully observed coordinates.',
        template_projection='Frozen basis and mean, same intercept-eliminating regularized score operator. Only each template supported potential range is supplied. Acid Pt/C templates are partial; no extension beyond support.',
        uncertainty='Conditional on fitted basis/model. Not total model or experiment uncertainty. Held-out prediction coverage and masking diagnostics exported.',
        limitations='Missingness may depend on current and study design; the model does not correct informative censoring. Population prior and smooth low-rank assumptions affect missing regions. No discrete chemical clusters asserted.'))
    print('Final pooled fit:',model['iterations'],'iterations; rank',model['rank'],'; variance fractions',scales**2/(scales@scales),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--reuse-cv',action='store_true');args=parser.parse_args()
    meta,observed=prepare()
    selected=json.loads((OUT/'SELECTED.json').read_text()) if args.reuse_cv else tune()
    finish(meta,observed,selected)
