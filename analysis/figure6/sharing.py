"""Parameter sharing and analytic Jacobian for resistance-free VHT."""
import numpy as np
from numba import njit
import independent_model as engine
from numerics import kinetic_and_jacobian
UNIT=engine.KBT_MEV*np.log(10.)
KEYS=["logh","logt","logK","logc"]
SPECS={"DeltaG_only":("logK",),"DeltaG_H":("logK","logh"),"DeltaG_T":("logK","logt"),"independent_H_T_G":("logh","logt","logK")}

def layout(name,n=5,bounds=None):
    free=SPECS[name]
    ix=np.empty((n,4),dtype=np.int64)
    names,lo,hi=[],[],[]
    lows=[-7.,-7.,-300/UNIT,-8.]; highs=[7.,7.,300/UNIT,8.]
    if bounds is not None:
        lows,highs=bounds
    for k,key in enumerate(KEYS):
        if key in free or key=="logc":
            for i in range(n):
                ix[i,k]=len(names);names.append(f"{key}_K{i+1}");lo.append(lows[k]);hi.append(highs[k])
        else:
            ix[:,k]=len(names);names.append(key+"_shared");lo.append(lows[k]);hi.append(highs[k])
    return ix,names,np.array(lo),np.array(hi)


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
