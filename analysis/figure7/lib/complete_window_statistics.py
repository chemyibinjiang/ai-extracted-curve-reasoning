"""Cross-paper profile distances used only for SI Tables S28-S29."""
import numpy as np
SEED=20260929

def bootstrap_counts(papers,n=3000,offset=0):
    unique=np.array(sorted(set(papers)))
    rng=np.random.default_rng(SEED+offset)
    return unique,rng.multinomial(len(unique),np.ones(len(unique))/len(unique),size=n)

def bundle_profiles(z,papers,allpapers):
    index={p:i for i,p in enumerate(allpapers)}
    mu=np.zeros((len(allpapers),z.shape[1]));ss=np.zeros(len(allpapers));n=np.zeros(len(allpapers))
    for p in set(papers):
        i=index[p];a=z[np.asarray(papers)==p]
        mu[i]=a.mean(0);ss[i]=np.mean(a*a);n[i]=len(a)
    return mu,ss,n

def cross_paper_rms(mu,ss,n,multipliers,mode='paper'):
    c=np.atleast_2d(multipliers).astype(float)
    w=c*((n>0) if mode=='paper' else n)[None,:]
    total=w.sum(1);den=total**2-(w*w).sum(1)
    combined=w@mu
    diagonal=2*(ss-np.mean(mu*mu,axis=1))
    num=2*(w@ss)*total-2*np.mean(combined*combined,axis=1)-(w*w)@diagonal
    out=np.sqrt(np.maximum(num,0)/np.maximum(den,1e-20))
    out[den<=0]=np.nan
    return out

def compare_profiles(d,z,nboot=3000,mode='paper'):
    papers,counts=bootstrap_counts(d.paper_key,nboot,17)
    result={};boot={}
    for noble,label in [(True,'noble'),(False,'non_noble')]:
        mask=d.noble.eq(noble).to_numpy();dd=d[mask]
        if dd.paper_key.nunique()<10:return None
        mu,ss,n=bundle_profiles(z[mask],dd.paper_key.to_numpy(),papers)
        estimate=cross_paper_rms(mu,ss,n,np.ones(len(papers)),mode)[0]
        bs=cross_paper_rms(mu,ss,n,counts,mode)
        boot[label]=bs
        result[label+'_rms']=float(estimate)
        result[label+'_curves']=len(dd);result[label+'_papers']=dd.paper_key.nunique()
        result[label+'_lo'],result[label+'_hi']=np.nanquantile(bs,[.025,.975]).tolist()
    ratio=boot['non_noble']/boot['noble']
    result['dispersion_ratio']=result['non_noble_rms']/result['noble_rms']
    result['ratio_lo'],result['ratio_hi']=np.nanquantile(ratio,[.025,.975]).tolist()
    result['difference']=result['non_noble_rms']-result['noble_rms']
    result['difference_lo'],result['difference_hi']=np.nanquantile(boot['non_noble']-boot['noble'],[.025,.975]).tolist()
    return result
