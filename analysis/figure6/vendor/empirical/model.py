"""Archived pure-scaling BV+jR, accurate fast beta profiles and joint derivatives.
No voltage offset. beta in mA/cm2; Q,eta in mV; R=Q/beta in ohm cm2.
"""
import math
import numpy as np
from numba import njit, prange
A=1000*8.31446261815324*298.15/(2*96485.33212)
LN10=math.log(10.)
T0=-40.; DT=.01; NT=10501

@njit(cache=True)
def inverse(x,a):
    if x<=0:return 0.
    if x<1e-8:return x+(.5-a)*x*x
    lo=0.;hi=np.log1p(x)/a;v=hi
    for _ in range(75):
        ep=np.exp(a*v);em=np.exp(-(1-a)*v)
        f=np.expm1(a*v)-np.expm1(-(1-a)*v)-x
        if abs(f)<=1e-13*x:return v
        if f>0:hi=v
        else:lo=v
        vv=v-f/(a*ep+(1-a)*em)
        if vv<=lo or vv>=hi:vv=(lo+hi)/2
        if abs(vv-v)<1e-14*max(1.,abs(v)):return vv
        v=vv
    return v

@njit(cache=True)
def table(a):
    vals=np.empty(NT); ders=np.empty(NT)
    for k in range(NT):
        t=T0+DT*k;x=np.exp(t);v=inverse(x,a)
        vals[k]=v;ders[k]=x/(a*np.exp(a*v)+(1-a)*np.exp(-(1-a)*v))
    return vals,ders

@njit(cache=True)
def interp(t,a,vals,ders):
    if t<T0:return np.exp(t)
    if t>=T0+DT*(NT-1):return t/a
    k=int((t-T0)/DT);r=(t-(T0+DT*k))/DT
    return ((2*r-3)*r*r+1)*vals[k]+((r-2)*r+1)*r*DT*ders[k]+(-2*r+3)*r*r*vals[k+1]+(r-1)*r*r*DT*ders[k+1]

@njit(cache=True)
def sse_interp(j,lj,y,a,q,z,vals,ders):
    rr=q*np.exp(-z); s=0.
    for k in range(len(j)):
        e=A*interp(lj[k]-z,a,vals,ders)+j[k]*rr-y[k]
        s+=e*e
    return s

@njit(cache=True)
def profile(j,lj,y,a,q,vals,ders,ngrid=35):
    lo=-12*LN10 if q<=0 else max(-12*LN10,np.log(q)-2*LN10)
    hi=8*LN10
    if hi<=lo:return hi,sse_interp(j,lj,y,a,q,hi,vals,ders)
    grid=np.linspace(lo,hi,ngrid);loss=np.empty(ngrid)
    for k in range(ngrid):loss[k]=sse_interp(j,lj,y,a,q,grid[k],vals,ders)
    ib=np.argmin(loss); bz=grid[ib];bs=loss[ib];gold=.6180339887498949
    for k in range(ngrid):
        if k>0 and loss[k]>loss[k-1]:continue
        if k<ngrid-1 and loss[k]>loss[k+1]:continue
        left=grid[max(0,k-1)];right=grid[min(ngrid-1,k+1)]
        c=right-gold*(right-left);d=left+gold*(right-left)
        fc=sse_interp(j,lj,y,a,q,c,vals,ders);fd=sse_interp(j,lj,y,a,q,d,vals,ders)
        for _ in range(43):
            if fc<fd:
                right=d;d=c;fd=fc;c=right-gold*(right-left);fc=sse_interp(j,lj,y,a,q,c,vals,ders)
            else:
                left=c;c=d;fc=fd;d=left+gold*(right-left);fd=sse_interp(j,lj,y,a,q,d,vals,ders)
        zz=(left+right)/2;ss=sse_interp(j,lj,y,a,q,zz,vals,ders)
        if ss<bs:bs=ss;bz=zz
    return bz,bs

@njit(parallel=True,cache=True)
def profile_matrix(J,LJ,Y,N,alphas,Qs):
    m=len(alphas);n=len(N);S=np.empty((m,n));Z=np.empty((m,n))
    for k in prange(m):
        a=alphas[k];q=Qs[k];vv,dd=table(a)
        for i in range(n):
            nn=N[i];z,s=profile(J[i,:nn],LJ[i,:nn],Y[i,:nn],a,q,vv,dd)
            S[k,i]=s;Z[k,i]=z/LN10
    return S,Z

@njit(cache=True)
def predict(j,a,q,z10):
    out=np.empty(len(j));beta=10.**z10
    for k in range(len(j)):
        x=j[k]/beta;out[k]=A*inverse(x,a)+q*x
    return out

@njit(cache=True)
def exact_res_jac(j,y,a,lq,z):
    q=10.**lq; beta=10.**z;r=np.empty(len(j));jac=np.empty((len(j),3))
    for k in range(len(j)):
        x=j[k]/beta;v=inverse(x,a);den=a*np.exp(a*v)+(1-a)*np.exp(-(1-a)*v)
        r[k]=A*v+q*x-y[k]
        jac[k,0]=-A*v*x/den
        jac[k,1]=LN10*q*x
        jac[k,2]=-LN10*(A*x/den+q*x)
    return r,jac
