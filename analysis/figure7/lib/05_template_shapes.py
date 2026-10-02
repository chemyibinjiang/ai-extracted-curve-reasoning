"""Frozen empirical shape evaluation only; no VHT model is used."""
from utils import *
import sys
sys.path.insert(0,str(INPUT))
import effective_bv as bv
from scipy.optimize import brentq


def template_eta(j,t):
    return bv.predict(np.asarray(j),dict(log_j0=0.,fraction=t.fraction,coefficient_sum=t.coefficient_sum,R=t.Q_mV))


def log_current(eta,t):
    return np.array([brentq(lambda z:template_eta(np.array([np.exp(z)]),t)[0]-e,-50,50)/np.log(10) for e in eta])


def main():
    templates=pd.read_csv(INPUT/'TEMPLATES.csv');rows=[];profiles=[]
    for t in templates.itertuples():
        lo,hi=template_eta(np.array([t.x_min,t.x_max]),t)
        grid=np.arange(5,301,1.)
        grid=grid[(grid>=lo)&(grid<=hi)]
        required=np.arange(50,151,5.)
        assert lo<=50 and hi>=150,(t.template,lo,hi)
        grid=np.unique(np.r_[grid,required]);yy=log_current(grid,t);anchor=log_current([50],t)[0]
        rows.append(dict(template=t.template,kind=t.kind,pgm_rich=t.template in RICH,
                         supported_eta_min=lo,supported_eta_max=hi))
        profiles.extend(dict(template=t.template,kind=t.kind,eta_mV=e,log10_template_current=v,aligned_log10_current=v-anchor) for e,v in zip(grid,yy))
    pd.DataFrame(rows).to_csv(TABLE/'template_support.csv',index=False)
    pd.DataFrame(profiles).to_csv(DATA/'template_profiles.csv',index=False)
    print('Frozen empirical profiles:',len(templates),flush=True)


if __name__=='__main__':main()
