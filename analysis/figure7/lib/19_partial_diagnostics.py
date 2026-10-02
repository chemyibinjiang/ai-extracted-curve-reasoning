"""Uncertainty, observation-mask controls and invariants for the partial PCA candidate."""
from utils import *
import partial_model as f

OUT=ROOT/'08_PARTIAL_PCA_CANDIDATE'


def main():
    meta=pd.read_csv(OUT/'COHORT.csv');obs=np.load(OUT/'OBSERVATIONS.npz');y=obs['y']
    model=dict(np.load(OUT/'MODEL.npz'));post=np.load(OUT/'POSTERIOR.npz')
    score=post['score'];cov=post['covariance'];n,k=score.shape
    assert np.array_equal(obs['curve_uid'],meta.curve_uid)
    assert np.all(np.linalg.eigvalsh(cov)>0)
    assert np.all(meta.groupby('paper_key').fold.nunique()==1)
    masks=np.load(OUT/'CV_TASKS.npz')
    assert not (np.isfinite(masks['train'])&np.isfinite(masks['truth'])).any()
    # The same fully observed donor shapes are shown through every group's real masks.
    donor_ids=np.flatnonzero(np.isfinite(y).all(1));donor_w=weights(meta.iloc[donor_ids])
    first=np.zeros_like(score);second=np.zeros(n)
    mask=np.isfinite(y)
    for weight,i in zip(donor_w,donor_ids):
        result=f.infer(model,np.where(mask,y[i],np.nan))['score']
        first+=weight*result;second+=weight*np.sum(result**2,axis=1)
    control=[]
    for condition in ['pooled',*CONDITIONS]:
        for group in GROUPS:
            cm=meta[meta.group.eq(group)&(True if condition=='pooled' else meta.condition.eq(condition))]
            ids=cm.index.to_numpy();w=weights(cm);center=w@first[ids]
            rms=np.sqrt(max(0,w@second[ids]-center@center))
            control.append(dict(condition=condition,group=group,donor_curves=len(donor_ids),
                donor_papers=meta.iloc[donor_ids].paper_key.nunique(),mask_curves=len(cm),
                identical_shape_masked_RMS=rms,PC1=center[0],PC2=center[1]))
    pd.DataFrame(control).to_csv(OUT/'IDENTICAL_SHAPES_MASK_CONTROL.csv',index=False)
    # Conditional latent draws plus whole-paper resampling; model/basis held fixed.
    rng=np.random.default_rng(SEED+82);draws=999
    vals,vec=np.linalg.eigh(cov);root=vec*np.sqrt(vals)[:,None,:]
    samples=score[None,:,:]+np.einsum('nij,bnj->bni',root,rng.normal(size=(draws,n,k)))
    papers=np.unique(meta.paper_key);codes=pd.Index(papers).get_indexer(meta.paper_key)
    multiplier=rng.multinomial(len(papers),np.full(len(papers),1/len(papers)),size=draws)
    rows=[]
    for condition in ['pooled',*CONDITIONS]:
        cm=meta if condition=='pooled' else meta[meta.condition.eq(condition)]
        strata=cm.condition.astype(str)+'_'+(cm.start//50).astype(int).astype(str)+'_'+(cm.end//50).astype(int).astype(str)
        group_info={};masses={}
        for group in GROUPS:
            z=cm[cm.group.eq(group)];ids=z.index.to_numpy();w=weights(z)
            group_info[group]=(ids,w);masses[group]=pd.Series(w,index=strata.loc[ids]).groupby(level=0).sum()
        target=pd.concat(masses,axis=1).fillna(0).min(axis=1);target=target[target>0];target/=target.sum()
        for matched in [False,True]:
            stats={}
            for group,(ids,original) in group_info.items():
                w=original.copy()
                if matched:w*=np.array([target.get(s,0)/masses[group][s] for s in strata.loc[ids]])
                good=w>0;ix=ids[good];w=w[good];w/=w.sum()
                bw=multiplier[:,codes[ix]]*w;bw/=bw.sum(1)[:,None]
                bs=samples[:,ix];means=np.einsum('bn,bnk->bk',bw,bs)
                disp=np.sqrt(np.maximum(0,np.einsum('bn,bnk,bnk->b',bw,bs,bs)-np.sum(means**2,axis=1)))
                center=w@score[ix];naive=w@np.sum((score[ix]-center)**2,axis=1)
                adjusted=np.sqrt(naive+(w*(1-w))@np.trace(cov[ix],axis1=1,axis2=2))
                stats[group]=(adjusted,disp)
            for denominator in ['PGM','PtC']:
                ratio=stats['no_PGM'][0]/stats[denominator][0]
                lo,hi=np.quantile(stats['no_PGM'][1]/stats[denominator][1],[.025,.975])
                rows.append(dict(condition=condition,support_matched=matched,numerator='no_PGM',
                    denominator=denominator,ratio=ratio,lower95=lo,upper95=hi))
    pd.DataFrame(rows).to_csv(OUT/'DISPERSION_RATIOS.csv',index=False)
    cv=pd.read_csv(OUT/'SELECTED_CV_ERRORS.csv')
    summaries=[]
    for mask_name,part in cv.groupby('mask'):
        percurve=part.groupby(['paper_key','curve_uid'])[['rmse','coverage95']].mean().reset_index()
        perpaper=percurve.groupby('paper_key')[['rmse','coverage95']].mean()
        summaries.append(dict(mask=mask_name,papers=len(perpaper),curves=percurve.curve_uid.nunique(),
                              paper_mean_RMSE=perpaper.rmse.mean(),paper_mean_coverage95=perpaper.coverage95.mean()))
    pd.DataFrame(summaries).to_csv(OUT/'CV_PAPER_SUMMARY.csv',index=False)
    score_table=pd.read_csv(OUT/'SCORES.csv');reliable=score_table[score_table.reliability.ge(.9)]
    robust=[]
    for c in CONDITIONS:
        for g in GROUPS:
            cm=reliable[reliable.condition.eq(c)&reliable.group.eq(g)];ids=cm.index.to_numpy();w=weights(cm)
            mu=w@score[ids]
            robust.append(dict(condition=c,group=g,curves=len(ids),papers=cm.paper_key.nunique(),
                posterior_mean_RMS=np.sqrt(w@np.sum((score[ids]-mu)**2,axis=1))))
    pd.DataFrame(robust).to_csv(OUT/'HIGH_INFORMATION_CHECK.csv',index=False)
    templates=pd.read_csv(OUT/'TEMPLATE_PROJECTIONS.csv');cols=[f'PC{i+1}' for i in range(k)]
    reference=templates[templates.kind.eq('non_PtC')];neighbors=[]
    for _,row in templates[~templates.kind.eq('non_PtC')].iterrows():
        distances=np.linalg.norm(reference[cols].to_numpy()-row[cols].to_numpy(float),axis=1)
        nearest=reference.iloc[distances.argmin()]
        neighbors.append(dict(template=row.template,nearest=nearest.template,PGM_rich=bool(nearest.PGM_rich),
                              distance=float(distances.min()),dimensions=k))
    pd.DataFrame(neighbors).to_csv(OUT/'PTC_NEAREST_TEMPLATES.csv',index=False)
    dump(OUT/'VALIDATION.json',dict(result='PASS',curves=n,rank=k,model_converged=bool(model['converged']),
        paper_holdout=True,no_train_test_native_overlap_by_construction=True,
        positive_posterior_covariances=True,identical_shape_donors=len(donor_ids),
        uncertainty_intervals='Conditional on fitted basis, common Gaussian prior and support-matching target; not full model-bootstrap uncertainty. Prediction calibration is imperfect.'))
    print('PASS: partial-observation invariants; identical-shape mask control:',len(donor_ids),'donors',flush=True)


if __name__=='__main__':main()
