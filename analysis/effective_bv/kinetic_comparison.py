"""SI kinetic comparisons from the same pooled fits used by Figure 6."""
import argparse
from pathlib import Path
from types import SimpleNamespace
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import families as f

LABELS={'DeltaG_only':'G','DeltaG_H':'GH','DeltaG_T':'GT','independent_H_T_G':'GHT'}
COLORS=['#177db0','#168f78','#d34259']

def dual(row):
    r=dict(row)
    h=np.log10(r['kH_over_kV']);t=np.log10(r['kT_over_kV'])
    lk=-r['DeltaG_eff_meV']/f.UNIT
    r.update(DeltaG_eff_meV=-r['DeltaG_eff_meV'],kH_over_kV=10**(-h),
             kT_over_kV=10**(t+2*lk-h),current_scale=r['current_scale']*10**h,
             log10_kH_over_kV=-h,log10_kT_over_kV=t+2*lk-h)
    return r

def run(output):
    output=Path(output)
    parameters=f.read(output/'KINETIC_PARAMETERS.csv')
    frames=[];dual_frames=[];errors=[]
    for _,r in parameters.iterrows():
        row=SimpleNamespace(**r.to_dict())
        rec=np.array([r.log10_kH_over_kV,r.log10_kT_over_kV,-r.DeltaG_eff_meV/f.UNIT,
                      np.log10(r.current_scale),.5,.5,0.])
        meta,_,xx,yy=f.data(output,r.condition,f.VERIFY_POINTS)
        i=list(meta.family).index(r.family)
        pred=f.engine.response(xx[i],*rec)
        lo=max(10.,np.ceil(max(yy[i,0],pred[0])))
        hi=min(190. if r.condition=='acid' else 250.,np.floor(min(yy[i,-1],pred[-1])))
        eta=np.arange(lo,hi+.01,.5)
        drc=np.array([f.rate_control(row,e) for e in eta])
        np.testing.assert_allclose(drc.sum(1),1,atol=2e-6)
        frame=pd.DataFrame(drc,columns=['X_V','X_H','X_T'])
        frame.insert(0,'eta_mV',eta)
        frame.insert(0,'family',r.family)
        frame.insert(0,'model',r.model)
        frame.insert(0,'condition',r.condition)
        frame['theta_H']=[f.state(row,e)[1] for e in eta]
        frames.append(frame)
        if r.model=='independent_H_T_G':
            alt=SimpleNamespace(**dual(r.to_dict()))
            adrc=np.array([f.rate_control(alt,e) for e in eta])
            astate=np.array([f.state(alt,e) for e in eta])
            state=np.array([f.state(row,e) for e in eta])
            diff=float(np.max(abs(adrc-drc[:,[1,0,2]])))
            np.testing.assert_allclose(astate[:,0]*alt.current_scale,
                                       state[:,0]*row.current_scale,rtol=1e-10,atol=1e-9)
            np.testing.assert_allclose(astate[:,1]+state[:,1],1,atol=1e-9)
            assert diff<2e-6
            af=frame.copy();af[['X_V','X_H','X_T']]=adrc;af['theta_H']=astate[:,1]
            dual_frames.append(af)
            errors.append(dict(family=r.family,max_DRC_exchange_error=diff))
    profiles=pd.concat(frames,ignore_index=True)
    duals=pd.concat(dual_frames,ignore_index=True)
    profiles.to_csv(output/'ALL_MODEL_RATE_CONTROL.csv',index=False)
    duals.to_csv(output/'GHT_DUAL_RATE_CONTROL.csv',index=False)
    pd.DataFrame([dual(r.to_dict()) for _,r in parameters[parameters.model.eq('independent_H_T_G')].iterrows()]).to_csv(output/'GHT_DUAL_PARAMETERS.csv',index=False)
    assets=output/'comparison';assets.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'Arial','font.size':14,'svg.fonttype':'none',
                        'axes.spines.top':False,'axes.spines.right':False})
    def finish(fig,name):
        for ext in ('png','svg','pdf'):fig.savefig(assets/f'{name}.{ext}',dpi=220,facecolor='white')
        plt.close(fig)
    def draw(ax,q):
        for col,color in zip(['X_V','X_H','X_T'],COLORS):ax.plot(q.eta_mV,q[col],color=color,lw=1.8)
        ax.set(xlim=(10,250),ylim=(-.03,1.03),xticks=[50,150,250],yticks=[0,.5,1])
        ax.grid(axis='y',color='#ddd',lw=.5)
    handles=[Line2D([],[],color=c,lw=2) for c in COLORS]
    fig,axes=plt.subplots(3,4,figsize=(11.5,7.8),sharex=True,sharey=True)
    for i,model in enumerate(['DeltaG_T','DeltaG_H','independent_H_T_G']):
        for j,name in enumerate(['B1','B2','B3','B4']):
            ax=axes[i,j]
            draw(ax,profiles[(profiles.model==model)&(profiles.family==name)])
            if i==0:ax.set_title(name,loc='left')
            if j==0:ax.set_ylabel(LABELS[model]+'\nDegree of rate control')
            if i==2:ax.set_xlabel(r'$|\eta|$ / mV')
    fig.legend(handles,['Volmer','Heyrovsky','Tafel'],ncol=3,loc='upper center',frameon=False)
    fig.subplots_adjust(left=.09,right=.97,top=.91,bottom=.10,hspace=.2,wspace=.18)
    finish(fig,'FigureS14_alkaline_sharing_controls')
    fig,axes=plt.subplots(2,2,figsize=(8.8,6.2),sharex=True,sharey=True)
    for ax,model in zip(axes.flat,['DeltaG_T','DeltaG_H','independent_H_T_G','dual']):
        q=duals[duals.family.eq('B3')] if model=='dual' else profiles[(profiles.family=='B3')&(profiles.model==model)]
        draw(ax,q)
        ax.set_title('Complementary GHT' if model=='dual' else LABELS[model],loc='left')
    for ax in axes[1]:ax.set_xlabel(r'$|\eta|$ / mV')
    for ax in axes[:,0]:ax.set_ylabel('Degree of rate control')
    fig.legend(handles,['Volmer','Heyrovsky','Tafel'],ncol=3,loc='upper center',frameon=False)
    fig.subplots_adjust(left=.12,right=.97,top=.88,bottom=.12,hspace=.25,wspace=.18)
    finish(fig,'FigureS15_B3_complementary_controls')
    f.dump(output/'KINETIC_COMPARISON_CHECKS.json',dict(passed=True,alpha=[.5,.5],
        objective='pooled voltage MSE',all_parameter_rows=len(parameters),duality_checks=errors,
        GHT_convention='Positive effective adsorption energy is the displayed representative, not a physical branch selection.'))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,default=f.ROOT/'build/effective-bv-20260930/figure6')
    run(p.parse_args().data)
