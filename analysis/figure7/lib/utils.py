"""Shared cohort, paper-weighted statistics and plotting conventions."""
from pathlib import Path
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[key] = '1'
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get('FIGURE7_OUTPUT', PACKAGE.parents[1]/'build/figure7')).resolve()
INPUT = PACKAGE/'inputs'
DATA = ROOT/'02_DATA'
TABLE = ROOT/'04_TABLES'
FIG = ROOT/'05_FIGURES'
for folder in [DATA, TABLE, FIG]:
    folder.mkdir(parents=True, exist_ok=True)


def compatibility():
    with np.load(INPUT/'LIBRARY_COMPATIBILITY.npz') as data:
        return data['compatible']
RICH = {'T01','T02','T04','T11','T15','T16'}
OTHER = {f'T{i:02d}' for i in range(1,17)}-RICH
GROUPS = ['PGM','no_PGM','PtC']
CONDITIONS = ['acidic','alkaline']
COLORS = dict(PGM='#cf4969',no_PGM='#2384a5',PtC='#50575b')
LABELS = dict(PGM='PGM, excluding Pt/C',no_PGM='non-PGM',PtC='Pt/C')
NBOOT = 1999
SEED = 20261001
FONT = 'Arial' if any(f.name == 'Arial' for f in font_manager.fontManager.ttflist) else 'DejaVu Sans'
plt.rcParams.update({'font.family':FONT,'font.weight':'bold','font.size':8,'axes.titlesize':9,
    'axes.titleweight':'bold','axes.labelweight':'bold',
    'mathtext.fontset':'custom','mathtext.rm':FONT+':bold','mathtext.it':FONT+':bold:italic',
    'mathtext.bf':FONT+':bold','mathtext.sf':FONT+':bold',
    'axes.labelsize':8,'legend.fontsize':7,'xtick.labelsize':7,'ytick.labelsize':7,
    'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none',
    'axes.linewidth':.65,'lines.linewidth':1.4,'savefig.facecolor':'white'})


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, default=lambda x: x.item() if isinstance(x,np.generic) else str(x))+'\n', encoding='utf-8')


def fw_for(n):
    w = np.ones(n); w[[0,-1]]=.5
    return w/w.sum()


def weights(m):
    n = m.groupby('paper_key').curve_uid.transform('size').to_numpy(float)
    w = 1/n
    return w/w.sum()


def quantiles(x, w, qs=(.025,.25,.5,.75,.975)):
    x=np.asarray(x)
    if x.ndim==1: x=x[:,None]
    out=[]
    for v in x.T:
        order=np.argsort(v); ww=w[order]; xx=v[order]
        out.append(np.interp(qs,(np.cumsum(ww)-ww/2)/ww.sum(),xx))
    return np.array(out).T


def dispersion(x,w,fw):
    mu=w@x
    return float(np.sqrt(max(0, w@((x-mu)**2@fw))))


def bootstrap_weights(m, n=NBOOT, seed=SEED, universe=None):
    papers = np.unique(m.paper_key) if universe is None else np.asarray(universe)
    pos=pd.Index(papers).get_indexer(m.paper_key)
    rng=np.random.default_rng(seed)
    counts=rng.multinomial(len(papers),np.ones(len(papers))/len(papers),size=n)
    base=1/m.groupby('paper_key').curve_uid.transform('size').to_numpy(float)
    w=counts[:,pos]*base[None,:]
    return w/np.maximum(w.sum(1,keepdims=True),1)


def bootstrap_stats(m, logj, fw, seed=SEED):
    w=weights(m); bw=bootstrap_weights(m,seed=seed)
    shape=logj-logj[:,[0]]
    features=np.column_stack([logj[:,0],shape[:,-1]])
    centers=w@features; boot=bw@features
    center=dispersion(shape,w,fw)
    mu=bw@shape
    bs=np.sqrt(np.maximum(0,bw@(shape**2@fw)-(mu**2@fw)))
    result=[]
    for k,name in enumerate(['logj_anchor','growth']):
        lo,hi=np.quantile(boot[:,k],[.025,.975])
        result.append((name,centers[k],lo,hi))
    lo,hi=np.quantile(bs,[.025,.975]); result.append(('dispersion',center,lo,hi))
    return result


def load_series():
    pts=pd.read_csv(INPUT/'POINTS.csv')
    series={}
    for uid,g in pts.groupby('curve_uid',sort=False):
        g=g[np.isfinite(g.eta_mV)&np.isfinite(g.j)&g.j.gt(0)]
        p=g.assign(logj=np.log10(g.j)).groupby('eta_mV').logj.median().sort_index()
        series[uid]=(p.index.to_numpy(),p.to_numpy())
    return series


def profiles(meta, series, low, high):
    grid=np.arange(low,high+1,5,dtype=float)
    matrices=[]; selected=[]; audit=[]
    for i,r in meta.iterrows():
        x,y=series[r.curve_uid]; n=int(((x>=low)&(x<=high)).sum())
        status='outside_support'; gap=np.nan
        if len(x)>1 and x[0]<=low and x[-1]>=high:
            a=max(0,np.searchsorted(x,low,side='right')-1)
            b=min(len(x)-1,np.searchsorted(x,high,side='left'))
            gap=np.diff(x[a:b+1]).max()
            status='ok' if n>=4 and gap<=20+1e-9 else 'sparse'
        audit.append(dict(curve_uid=r.curve_uid,window=f'{low}_{high}',status=status,native_points=n,max_gap_mV=gap))
        if status=='ok':
            selected.append(i);matrices.append(np.interp(grid,x,y))
    return meta.loc[selected].reset_index(drop=True),np.asarray(matrices),grid,pd.DataFrame(audit)


def pca(x,w,fw):
    z=x*np.sqrt(fw); mean=w@z; c=z-mean
    val,vec=np.linalg.eigh(c.T@(c*w[:,None]))
    ix=np.argsort(val)[::-1];val=np.maximum(val[ix],0);vec=vec[:,ix]
    for i in range(vec.shape[1]):
        if vec[np.argmax(np.abs(vec[:,i])),i]<0: vec[:,i]*=-1
    return (z-mean)@vec,mean,vec,val


def save(fig,name,folder='SUPPORTING'):
    target=FIG/folder/name
    target.parent.mkdir(parents=True,exist_ok=True)
    for ext in ['png','pdf','svg']:
        fig.savefig(target.with_suffix('.'+ext),dpi=220,bbox_inches='tight',pad_inches=.045)
    plt.close(fig)


def primary():
    m=pd.read_csv(DATA/'pca_scores.csv')
    d=np.load(DATA/'functional_profiles_50_150.npz')
    assert np.array_equal(m.curve_uid.to_numpy(str),d['curve_uid'])
    return m,d['logj'],d['eta_mV'],d['fw']
