"""Exact maximum coverage over an explicit candidate library, not greedy labels.
Continuous template discovery/refinement is handled separately. Optimality here
only concerns the supplied finite candidate set. Curve compatibility is retained.
"""
from pathlib import Path
import csv,json,time
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import csc_matrix,hstack,vstack,eye

def read_csv(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write_csv(p,rows):
 rows=list(rows)
 if not rows:return
 with Path(p).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def prepare(loss,limits,ids,allowed=None):
    """Deduplicate and prune dominated coverage sets using TRAINING curves only."""
    if allowed is None:allowed=np.arange(len(loss))
    L=loss[np.ix_(allowed,ids)]/limits[ids][None,:]
    B=L<=1.+1e-9
    quality=(np.minimum(L,1.)).mean(axis=1)
    bysig={}
    for k,b in enumerate(B):
        if not b.any():continue
        key=np.packbits(b,bitorder='little').tobytes()
        if key not in bysig or quality[k]<quality[bysig[key]]:bysig[key]=k
    seq=sorted(bysig.values(),key=lambda k:(-int(B[k].sum()),quality[k],int(allowed[k])))
    keep=[];bits=[]
    for k in seq:
        bit=int.from_bytes(np.packbits(B[k],bitorder='little').tobytes(),'little')
        if any((bit & t)==bit for t in bits):continue
        keep.append(k);bits.append(bit)
    kk=np.array(keep,dtype=int)
    return dict(B=B[kk],indices=allowed[kk],quality=quality[kk],n_before=len(allowed),n_unique=len(seq),n_nondominated=len(kk))

def solve(prep,K,time_limit=15.,weights=None):
    B=prep['B'];ns,n=B.shape
    if weights is None:weights=np.ones(n)
    if ns==0:return dict(selected=[],covered=0,coverage=0.,upper_count=0,certified_count=True,status=0,mip_gap=0.,n_candidates=0,seconds=0.)
    if K==1:
        count=B@weights;best=np.max(count);can=np.where(count==best)[0]
        k=can[np.argmin(prep['quality'][can])]
        return dict(selected=[int(prep['indices'][k])],covered=int(B[k].sum()),coverage=float(B[k].mean()),upper_count=int(B[k].sum()),certified_count=True,status=0,mip_gap=0.,n_candidates=ns,seconds=0.)
    K=min(K,ns);epsilon=1e-5
    obj=np.r_[epsilon*(1+prep['quality']),-weights]
    mat=vstack([hstack([-csc_matrix(B.T.astype(float)),eye(n)]),csc_matrix(np.r_[np.ones(ns),np.zeros(n)][None,:])],format='csc')
    t=time.time()
    result=milp(obj,integrality=np.r_[np.ones(ns),np.zeros(n)],bounds=Bounds(0,1),constraints=LinearConstraint(mat,-np.inf,np.r_[np.zeros(n),K]),options={'time_limit':time_limit,'mip_rel_gap':0.})
    if result.x is None:raise RuntimeError(f'No feasible coverage solution: {result.message}')
    ix=np.where(result.x[:ns]>.5)[0];selection=prep['indices'][ix];passed=B[ix].any(axis=0);count=int(passed.sum())
    ub=min(n,int(np.floor(-result.mip_dual_bound+2*epsilon*K+1e-5))) if np.all(weights==1) else -1
    return dict(selected=[int(v) for v in selection],covered=count,coverage=float(passed.mean()),upper_count=ub,certified_count=bool(ub==count),status=int(result.status),mip_gap=float(result.mip_gap),n_candidates=ns,seconds=time.time()-t)

def strata(meta):
    groups={'all_416':np.arange(len(meta))}
    for val,key in [('1 M KOH','KOH_1M'),('0.5 M H2SO4','H2SO4_0p5M'),('1 m? KOH','KOH_ambiguous_m')]:
        groups[key]=np.array([i for i,r in enumerate(meta) if r['electrolyte_key']==val])
    for val,key in [('Partial reported','KOH_1M_partial_reported'),('Reported; fraction unknown','KOH_1M_reported_fraction_unknown'),('Unknown','KOH_1M_correction_unknown')]:
        groups[key]=np.array([i for i,r in enumerate(meta) if r['electrolyte_key']=='1 M KOH' and r['correction_record']==val])
    return groups

CRITERIA=[('R2_0p99',.01,None),('R2_0p995',.005,None),('R2_0p99_RMSE10mV',.01,10.)]
def limits_for(tau,cap,N,TSS):
    limits=np.full(len(N),tau)
    if cap is not None:limits=np.minimum(limits,cap*cap*N/TSS)
    return limits
