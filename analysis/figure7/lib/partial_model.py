"""Observed-only smooth latent-factor model with a diffuse curve intercept.

This is a penalized probabilistic functional factor model, not the PACE algorithm.
The intercept is eliminated analytically using only each curve's observed cells.
"""
import os
for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):
    os.environ[k]='1'
import numpy as np
from scipy.interpolate import BSpline

GRID=np.arange(20,301,10,dtype=float)

def basis():
    knots=np.r_[np.zeros(4),[.2,.4,.6,.8],np.ones(4)]
    spl=BSpline(knots,np.eye(len(knots)-4),3)
    u=np.linspace(0,1,1001)
    dense=spl(u); mean=np.trapezoid(dense,u,axis=0)
    centered=dense-mean
    gram=np.trapezoid(centered[:,:,None]*centered[:,None,:],u,axis=0)
    val,vec=np.linalg.eigh(gram); good=val>1e-10
    transform=vec[:,good]/np.sqrt(val[good])
    b=(spl((GRID-GRID[0])/(GRID[-1]-GRID[0]))-mean)@transform
    second=spl.derivative(2)(u)@transform
    penalty=np.trapezoid(second[:,:,None]*second[:,None,:],u,axis=0)
    penalty/=np.trace(penalty)
    return b,penalty,dict(knots=knots,mean=mean,transform=transform)

B,P,BASIS=basis()

def moments(y):
    mask=np.isfinite(y); n=mask.sum(1)
    if np.any(n<2):raise ValueError('At least two observed cells required')
    clean=np.nan_to_num(y)
    ym=clean.sum(1)/n
    bm=mask@B/n[:,None]
    g=np.einsum('ni,ij,ik->njk',mask,B,B)-n[:,None,None]*bm[:,:,None]*bm[:,None,:]
    h=clean@B-n[:,None]*bm*ym[:,None]
    yy=(clean*clean).sum(1)-n*ym*ym
    return dict(g=g,h=h,yy=yy,n=n,bm=bm,ym=ym)

def posterior(stats,mu,load,sigma2):
    g,h=stats['g'],stats['h']
    gl=np.einsum('nij,jk->nik',g,load)
    precision=np.eye(load.shape[1])+np.einsum('ik,nij->nkj',load,gl)/sigma2
    covariance=np.linalg.inv(precision)
    rhs=(h-np.einsum('nij,j->ni',g,mu))@load/sigma2
    z=np.einsum('nij,nj->ni',covariance,rhs)
    return z,covariance

def fit(y,weights,rank,smoothing,max_iter=100,noise_floor=.02):
    stats=moments(y);g,h=stats['g'],stats['h'];w=weights/np.sum(weights);q=B.shape[1]
    mu=np.linalg.solve(np.einsum('n,nij->ij',w,g)+.001*P+1e-9*np.eye(q),w@h)
    residual=h-np.einsum('nij,j->ni',g,mu)
    ev,vec=np.linalg.eigh((residual*w[:,None]).T@residual)
    load=vec[:,np.argsort(ev)[::-1][:rank]]*.12
    sigma2=.05**2;history=[]
    for iteration in range(max_iter):
        z,cov=posterior(stats,mu,load,sigma2)
        first=np.column_stack([np.ones(len(y)),z])
        second=np.einsum('ni,nj->nij',first,first);second[:,1:,1:]+=cov
        lhs=np.einsum('n,nab,nij->aibj',w,second,g).reshape((rank+1)*q,(rank+1)*q)
        lhs+=sigma2*smoothing*np.kron(np.eye(rank+1),P)+np.eye(len(lhs))*1e-9
        rhs=np.einsum('n,na,ni->ai',w,first,h).ravel()
        beta=np.linalg.solve(lhs,rhs).reshape(rank+1,q).T
        newmu,newload=beta[:,0],beta[:,1:]
        ss=stats['yy']-2*np.einsum('ni,ia,na->n',h,beta,first)+np.einsum('ia,nij,jb,nab->n',beta,g,beta,second)
        newsigma=max(noise_floor**2,float(w@ss/(w@(stats['n']-1))))
        # Use rotation-invariant parameters for convergence, not latent-axis rotation.
        change=max(np.linalg.norm(newmu-mu)/max(.1,np.linalg.norm(newmu)),
                   np.linalg.norm(newload@newload.T-load@load.T)/max(.01,np.linalg.norm(newload@newload.T)),
                   abs(newsigma-sigma2)/max(noise_floor**2,newsigma))
        mu,load,sigma2=newmu,newload,newsigma
        history.append(change)
        if iteration>15 and change<1e-4:break
    # The basis is orthonormal in the full-domain integral metric.
    u,s,_=np.linalg.svd(load,full_matrices=False)
    load=u*s
    for k in range(rank):
        phi=B@load[:,k]
        if phi[np.argmax(abs(phi))]<0:load[:,k]*=-1
    return dict(mu=mu,load=load,sigma2=sigma2,rank=rank,smoothing=smoothing,
                iterations=iteration+1,converged=bool(history[-1]<1e-4),last_change=history[-1])

def infer(model,y):
    stats=moments(y)
    z,cov=posterior(stats,model['mu'],model['load'],model['sigma2'])
    coeff=model['mu']+z@model['load'].T
    intercept=stats['ym']-np.einsum('ni,ni->n',stats['bm'],coeff)
    prediction=intercept[:,None]+coeff@B.T
    scales=np.linalg.norm(model['load'],axis=0)
    score=z*scales
    score_cov=cov*scales[None,:,None]*scales[None,None,:]
    return dict(score=score,covariance=score_cov,prediction=prediction,intercept=intercept,z=z,latent_covariance=cov)

def prediction_variance(model,y,result):
    stats=moments(y)
    design=(B[None,:,:]-stats['bm'][:,None,:])@model['load']
    return np.einsum('nik,nkl,nil->ni',design,result['latent_covariance'],design)+model['sigma2']/stats['n'][:,None]
