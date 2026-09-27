"""Static numerical comparison; publication artwork is not changed."""
import html
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

COLORS={'BV':'#177db0','BV+jR':'#d34259','Nernst':'#68767b','Nernst+jR':'#168f78',
        'VHT':'#a76b10','VHT family replay':'#a76b10'}


def table(rows,columns):
    out='<table><thead><tr>'+''.join('<th>'+html.escape(label)+'</th>' for key,label in columns)+'</tr></thead><tbody>'
    for row in rows:
        cells=[]
        for key,label in columns:
            value=row[key]
            cells.append(f'{value:.3f}' if isinstance(value,float) else html.escape(str(value)))
        out+='<tr>'+''.join('<td>'+c+'</td>' for c in cells)+'</tr>'
    return out+'</tbody></table>'


def render(out,source):
    result=json.loads((out/'RESULTS.json').read_text())
    templates=pd.read_csv(out/'TEMPLATE_PREDICTIONS.csv')
    stats=pd.read_csv(out/'TEMPLATE_FITS.csv')
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'savefig.dpi':160,'font.family':'DejaVu Sans'})
    fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
    for family,ax in zip(sorted(templates.family.unique()),axes.flat):
        frame=templates[templates.family.eq(family)]
        first=frame[frame.model.eq('Nernst+jR')]
        ax.plot(first.reference_mV,first.x,color='black',lw=2.6,label='Current empirical template')
        for name in ['Nernst+jR','VHT']:
            g=frame[frame.model.eq(name)]
            ax.plot(g.prediction_mV,g.x,color=COLORS[name],lw=1.8,
                    ls='--' if name=='Nernst+jR' else ':',label=name)
        ax.set(yscale='log',xlabel='Overpotential magnitude (mV)',ylabel='Normalized current',title=family)
        own=stats[stats.family.eq(family)].set_index('model')
        ax.text(.97,.04,f"Voltage RMSE (mV)\nNernst+jR: {own.loc['Nernst+jR','rmse']:.3f}\nVHT: {own.loc['VHT (shared rates, DeltaG-only)','rmse']:.3f}",
                ha='right',va='bottom',transform=ax.transAxes,fontsize=9)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside upper center',ncol=3,frameon=False)
    fig.savefig(out/'template_comparison.png');plt.close(fig)
    fits=pd.read_csv(out/'CURVE_FITS.csv')
    cv=pd.read_csv(out/'HELDOUT_METRICS.csv')
    members=pd.read_csv(source/'figure6/acid/ASSIGNMENTS.csv').set_index('curve_uid')
    fig,axes=plt.subplots(1,2,figsize=(10,4.6),layout='constrained')
    for ax,frame,title in zip(axes,[fits,cv],['All-point fit, 73 curves','Held-out-point prediction, 73 curves']):
        pivot=frame.pivot(index='curve_uid',columns='model',values='rmse')
        for flag,color,label in [(True,'#168f78','Current four-family members (59)'),(False,'#b64b38','Other nonlinear responses (14)')]:
            own=pivot[members.loc[pivot.index,'adequate'].to_numpy()==flag]
            ax.scatter(own['BV+jR'],own['Nernst+jR'],s=25,facecolors='none',edgecolors=color,label=label)
        low=max(.001,min(pivot['BV+jR'].min(),pivot['Nernst+jR'].min())*.8)
        high=max(pivot['BV+jR'].max(),pivot['Nernst+jR'].max())*1.3
        ax.plot([low,high],[low,high],color='black',lw=1,ls='--')
        ax.set(xscale='log',yscale='log',xlim=(low,high),ylim=(low,high),xlabel='Effective BV+jR RMSE (mV)',
               ylabel='Nernst+jR RMSE (mV)',title=title)
    axes[0].legend(frameon=False,fontsize=8,loc='upper left')
    fig.savefig(out/'curve_comparison.png');plt.close(fig)
    scan=pd.read_csv(out/'COVERAGE_SCAN.csv')
    previous=pd.read_csv(source/'figure6/acid/COVERAGE_SCAN.csv')
    paper=pd.read_csv(out/'PAPER_CV.csv').groupby('K')[['test_covered','test_n']].sum()
    oldpaper=pd.read_csv(source/'figure6/acid/PAPER_CV.csv').groupby('K')[['test_covered','test_n']].sum()
    fig,axes=plt.subplots(1,2,figsize=(10,4.3),layout='constrained')
    for name,style,label in [('matched_Q_grid',':','Nernst+jR, matched Q grid'),('refined_Q_grid','-','Nernst+jR, refined Q grid')]:
        g=scan[scan.grid.eq(name)]
        axes[0].plot(g.K,100*g.covered/73,ls=style,color=COLORS['Nernst+jR'],marker='o',ms=3,label=label)
    axes[0].plot(previous.K,100*previous.covered/73,color=COLORS['BV+jR'],marker='s',ms=3,label='Current effective-BV library')
    axes[0].set(title='Maximum training coverage, 73 curves',xlabel='Number of templates',ylabel='Covered curves (%)',ylim=(0,105))
    axes[0].axhline(80,color='black',lw=.8,ls='--');axes[0].legend(frameon=False,fontsize=8)
    for g,color,label in [(paper,COLORS['Nernst+jR'],'Nernst+jR'),(oldpaper,COLORS['BV+jR'],'Current effective BV')]:
        axes[1].plot(g.index,100*g.test_covered/g.test_n,color=color,marker='o',label=label)
    axes[1].set(title='Five-fold paper-held-out shape transfer',xlabel='Number of training templates',ylabel='Covered held-out curves (%)',ylim=(0,105))
    axes[1].legend(frameon=False)
    fig.savefig(out/'family_coverage.png');plt.close(fig)
    columns=[('model','Model'),('curves','Curves'),('accepted','R2 >= 0.99'),('median_rmse_mV','Median RMSE / mV'),('pooled_rmse_mV','Pooled RMSE / mV')]
    family=result['families']
    nernst=fits[fits.model.eq('Nernst+jR')]
    bvfit=fits[fits.model.eq('BV+jR')]
    converged=int(bvfit.equivalent_converged.sum())
    body='<h1>Acidic Pt/C: Nernst boundary control</h1><p>27 September 2026 | 73 nonlinear responses | 0-200 mV | 0.5 M H<sub>2</sub>SO<sub>4</sub></p>'
    body+='<p><strong>Purpose:</strong> test whether the same acidic response shapes are compatible with the concentration-polarization boundary, without changing the manuscript or figures.</p>'
    body+='<h2>Matched curve fits</h2>'+table(result['full_population'],columns)
    body+='<p>Nernst and Nernst+jR have one and two fitted parameters. Effective BV and BV+jR have three and four. All models use the same original points, equal-point voltage SSE and no voltage offset.</p>'
    body+='<h2>Held-out-point prediction</h2>'+table(result['heldout_points'],columns)
    body+='<p>Three interleaved folds per curve; each point is predicted once using parameters initialized and fitted without that point. These folds test interpolation of digitized traces, not independent experimental replication.</p><img src="curve_comparison.png" alt="Matched training and held-out RMSE comparisons">'
    body+='<h2>Same 59 current family members</h2>'+table(result['shared_59_members'],columns)
    body+='<p>The VHT row replays the existing shared-rate, DeltaG-only four-family reconstruction with its fitted member amplitudes. It is not an independent four-parameter fit to each trace. Its parameters and family assignment were not cross-validated here.</p>'
    body+='<h2>Current template reconstruction</h2><img src="template_comparison.png" alt="Four acidic empirical templates reconstructed with Nernst+jR and VHT">'
    body+='<p>Same 1,000 log-current points per template and empirical target used for the VHT audit. Nernst+jR fits two constants per template; its linear coefficient is expressed per normalized-current unit.</p>'
    body+=f'<h2>Family compression</h2><p>Smallest tested K reaching 80%: <strong>{family["minimum_K_80_percent"]}</strong>. Selected Q values (mV): '+', '.join(f'{q:.4g}' for q in family['Q_mV'])+'. Coverage optimality is certified over the explicit finite candidate grid only.</p>'
    body+='<img src="family_coverage.png" alt="Family coverage and paper-held-out transfer"><p>Nernst+jR has one shape parameter Q = jL R per template; the current effective-BV library has three. Each curve additionally fits one amplitude. Paper-held-out evaluation selects shapes without the test papers but refits an amplitude for each test curve; this is distinct from held-out-point prediction.</p>'
    body+='<h2>Reversibility and interpretation</h2><p>Prats and Chan distinguish kinetic current from measured current. Their effective-BV argument uses a shared rate-determining step for HER/HOR. Their concentration-polarization limit instead assumes kinetics fast enough to maintain interfacial Nernst equilibrium, with steady transport and specified bulk concentrations. A reversible Pt interface can therefore yield transport-controlled polarization.</p>'
    body+='<p>For positive HER magnitudes, J = jL[exp(2Fu/RT) - 1], equivalent to effective BV at alpha_c = 2, alpha_a = 0. The control adds a fitted R term. Agreement establishes response-shape compatibility, not that each source experiment meets the transport assumptions. Gas saturation, hydrodynamics, scan-rate independence and active-area/loading information are not present in the supplied cohort metadata.</p>'
    body+='<p>The current BV implementation restricts the cathodic fraction to 0.01-0.99, so it does not include the exact endpoint. Small improvements by Nernst+jR are therefore not violations of a nested-model bound.</p>'
    body+=f'<p>Numerical check: {converged}/73 BV+jR full fits have an equivalent converged optimum. Nernst+jR uses global scalar profiling with an exactly optimized bounded linear coefficient.</p>'
    body+='<p><a href="https://doi.org/10.1039/D1CP04134G">Prats and Chan (2021)</a> | <a href="https://www.rsc.org/suppdata/d1/cp/d1cp04134g/d1cp04134g1.pdf">Supporting Information</a> | <a href="RESULTS.json">Results</a> | <a href="PROTOCOL.json">Protocol and source hashes</a> | <a href="CURVE_FITS.csv">Curve fits</a> | <a href="TEMPLATE_FITS.csv">Template fits</a></p>'
    markup='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Acid Pt/C Nernst control</title><style>body{font:16px/1.5 Arial,sans-serif;color:#151515;max-width:1120px;margin:32px auto;padding:0 20px}h1{font-size:28px}h2{font-size:21px;margin-top:30px;border-top:1px solid #aaa;padding-top:16px}img{width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:8px;border-bottom:1px solid #ccc}a{color:#006ca3}@media(max-width:650px){table{display:block;overflow-x:auto}h1{font-size:23px}}</style>'+body+'</html>'
    (out/'index.html').write_text(markup,encoding='utf-8')
