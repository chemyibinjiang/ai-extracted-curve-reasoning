"""Rebuild SI Tables S28-S29 from native curves, without latent-score inference."""
from utils import *
from complete_window_statistics import compare_profiles
from metadata import corrected_metadata


def main(verify=True):
    meta = pd.read_csv(INPUT/'LIBRARY_COHORT.csv')
    composition = corrected_metadata(pd.read_csv(INPUT/'canonical_curves.csv')).set_index('curve_uid').enrich_active_elements
    elements = meta.curve_uid.map(composition).map(json.loads)
    known = elements.map(bool)
    meta['noble'] = elements.map(lambda e:bool(set(e)&{'Pt','Pd','Rh','Ru','Ir','Os'}))
    # The inherited function argument is named noble; here it is strictly the six-element PGM flag.
    meta = meta[known].reset_index(drop=True)
    assert len(meta)==2267
    raw=np.load(INPUT/'NATIVE_CURVES.npz'); j,eta,n=raw['J'],raw['Y'],raw['n']
    index=pd.Index(raw['curve_uid']).get_indexer(meta.curve_uid)
    series={}
    for uid,i in zip(meta.curve_uid,index):
        a,b=j[i,:n[i]],eta[i,:n[i]]
        good=np.isfinite(a)&np.isfinite(b)&(a>0)
        z=pd.DataFrame(dict(eta=b[good],logj=np.log10(a[good]))).groupby('eta').logj.median().sort_index()
        series[uid]=(z.index.to_numpy(),z.to_numpy())
    records=[]
    for lo,hi in [(50,150),(25,100),(50,100),(100,200),(150,250)]:
        ids=[]; profiles=[]
        for i,row in meta.iterrows():
            x,y=series[row.curve_uid]
            if len(x)<2 or x[0]>lo or x[-1]<hi or ((x>=lo)&(x<=hi)).sum()<8:continue
            a=max(0,np.searchsorted(x,lo,side='right')-1)
            b=min(len(x)-1,np.searchsorted(x,hi,side='left'))
            if np.diff(x[a:b+1]).max()>20:continue
            ids.append(i);profiles.append(np.interp(np.linspace(lo,hi,41),x,y))
        dd=meta.iloc[ids].reset_index(drop=True); values=np.array(profiles)
        centered=values-values.mean(1,keepdims=True)
        current=10**(values-values.max(1,keepdims=True))
        unit=current/np.sqrt(np.mean(current**2,axis=1,keepdims=True))
        for scope in ['all','acidic','alkaline']:
            take=np.ones(len(dd),bool) if scope=='all' else dd.regime_class.eq(scope).to_numpy()
            for metric, z in [('centered_logj',centered),('unit_rms_current',unit)]:
                result=compare_profiles(dd[take],z[take])
                result={key.replace('non_noble','no_PGM').replace('noble','PGM'):v for key,v in result.items()}
                records.append(dict(window=f'{lo}_{hi}',scope=scope,metric=metric,**result))
    actual=pd.DataFrame(records).sort_values(['window','scope','metric']).reset_index(drop=True)
    if verify:
        expected=pd.read_csv(PACKAGE/'reference/COMPLETE_WINDOW_DISPERSION.csv').sort_values(['window','scope','metric']).reset_index(drop=True)
        for col in ['PGM_curves','no_PGM_curves','dispersion_ratio','ratio_lo','ratio_hi']:
            np.testing.assert_allclose(actual[col],expected[col],rtol=1e-10,atol=1e-10)
    actual.to_csv(TABLE/'complete_window_dispersion.csv',index=False)
    print('All complete-window SI sensitivity results reproduced.',flush=True)


if __name__=='__main__':main()
