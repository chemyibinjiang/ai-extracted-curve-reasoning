"""Six-panel population-first candidate with matched partial-PCA projections."""
from utils import *
from matplotlib.lines import Line2D
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator,FuncFormatter,NullLocator
import matplotlib.patheffects as pe
from pypdf import PdfReader
import importlib
import html

OUT=ROOT/'08_PARTIAL_PCA_CANDIDATE'
PLOTS=OUT/'figures';PLOTS.mkdir(exist_ok=True)
M=pd.read_csv(OUT/'SCORES.csv');PROJ=pd.read_csv(OUT/'TEMPLATE_PROJECTIONS.csv')
SHAPES=pd.read_csv(DATA/'template_profiles.csv');NATIVE=pd.read_csv(OUT/'TEMPLATE_NATIVE_POINTS.csv')
POST=np.load(OUT/'POSTERIOR.npz');MODEL=np.load(OUT/'MODEL.npz');GRID=MODEL['grid']
FRACTIONS=np.linalg.norm(MODEL['load'],axis=0)**2;FRACTIONS/=FRACTIONS.sum()
SERIES=load_series()
OLD=importlib.import_module('composition_panels')
LIMITS=((-1.2,.62),(-.49,.60))
FULL=((M.PC1.min()-.12,M.PC1.max()+.12),(M.PC2.min()-.10,M.PC2.max()+.10))
DRAW_QA=[]
NAMES={'PGM':'PGM (non-Pt/C)','no_PGM':'non-PGM','PtC':'Pt/C'}
AXIS_SIZE=12
TICK_SIZE=10
LABEL_SIZE=9
LEGEND_SIZE=9
PANEL_SIZE=20
plt.rcParams.update({'font.size':TICK_SIZE,'axes.labelsize':AXIS_SIZE,
                     'axes.titlesize':AXIS_SIZE,'xtick.labelsize':TICK_SIZE,
                     'ytick.labelsize':TICK_SIZE,'legend.fontsize':LEGEND_SIZE})


def export(fig,name):
    for ext in ['png','pdf','svg']:
        fig.savefig(PLOTS/f'{name}.{ext}',dpi=230,bbox_inches='tight',pad_inches=.04)
    plt.close(fig)


def group_legend(ax,counts=False,loc='upper left',size=LEGEND_SIZE):
    handles=[Line2D([],[],color=COLORS[g],lw=1.6,
        label=NAMES[g]+(f' (n={int(M.group.eq(g).sum())})' if counts else '')) for g in ['PtC','PGM','no_PGM']]
    return ax.legend(handles=handles,loc=loc,fontsize=size,frameon=True,facecolor='white',
                     edgecolor='none',framealpha=.90,handlelength=1.5,labelspacing=.25,borderpad=.3)


def raw_lsv(ax,condition=None):
    data=M if condition is None else M[M.condition.eq(condition)]
    counts={}
    for layer,g in enumerate(['no_PGM','PGM','PtC']):
        segments=[];counts[g]=0
        for uid in data[data.group.eq(g)].curve_uid:
            x,y=SERIES[uid];j=10**y
            counts[g]+=1
            for a,b,ja,jb in zip(x[:-1],x[1:],j[:-1],j[1:]):
                if b<20 or a>300 or b-a>20+1e-9:continue
                left,right=max(20,a),min(300,b)
                if left>=right:continue
                v=10**np.interp([left,right],[a,b],np.log10([ja,jb]))
                segments.append(np.column_stack([[left,right],v]))
        alpha={'no_PGM':.09,'PGM':.10,'PtC':.12}[g]
        collection=LineCollection(segments,colors=COLORS[g],linewidths=.48,alpha=alpha,
                                  linestyles='-',zorder=layer+1,rasterized=True)
        ax.add_collection(collection)
    ax.set(yscale='log',xlim=(20,300),ylim=(.18,600),xlabel=r'$|\eta|$ (mV)',ylabel=r'$|j|$ (mA cm$^{-2}$)')
    ax.set_xticks([20,50,150,300]);ax.set_yticks([.2,1,10,100,500]);ax.yaxis.set_major_formatter(FuncFormatter(lambda x,pos:f'{x:g}'))
    ax.yaxis.set_minor_locator(NullLocator())
    if condition is not None:
        ax.text(.03,.97,condition.capitalize(),transform=ax.transAxes,va='top',fontsize=AXIS_SIZE)
    handles=[Line2D([],[],color=COLORS[g],lw=1.5,label=f'{NAMES[g]} (n={counts[g]})') for g in ['PtC','PGM','no_PGM']]
    ax.legend(handles=handles,loc='lower right',frameon=True,facecolor='white',edgecolor='none',framealpha=.93,
              fontsize=LEGEND_SIZE,handlelength=1.7,labelspacing=.25,borderpad=.3)
    DRAW_QA.append(dict(panel='raw_LSV',condition=condition or 'pooled',curves=counts,top_layer='PtC',line_style='solid'))


def scatter(ax,meta=M,overlay=False,full=False):
    for g in ['no_PGM','PGM','PtC']:
        z=meta[meta.group.eq(g)]
        ax.scatter(z.PC1,z.PC2,s=7 if not full else 2.3,c=COLORS[g],
                   alpha=.08 if overlay else (.38 if not full else .35),
                   linewidths=0,zorder=2 if g=='PtC' else 1,rasterized=True)


def pca_panel(ax,overlay=False):
    scatter(ax,overlay=overlay)
    ax.set(xlim=LIMITS[0],ylim=LIMITS[1],xlabel=f'PC1 ({100*FRACTIONS[0]:.1f}%)',ylabel=f'PC2 ({100*FRACTIONS[1]:.1f}%)')
    ax.axhline(0,c='#b4bac0',lw=.45,ls=':',zorder=0);ax.axvline(0,c='#b4bac0',lw=.45,ls=':',zorder=0)
    ax.xaxis.set_major_locator(MaxNLocator(5));ax.yaxis.set_major_locator(MaxNLocator(5))
    inset=ax.inset_axes([.055,.70,.25,.25]);scatter(inset,full=True)
    inset.set(xlim=FULL[0],ylim=FULL[1],xticks=[-3,0,1],yticks=[0,1])
    inset.tick_params(labelsize=8,length=2,pad=1)
    inset.set_title('Full range',fontsize=9,pad=2)
    inset.add_patch(Rectangle((LIMITS[0][0],LIMITS[1][0]),np.ptp(LIMITS[0]),np.ptp(LIMITS[1]),
                              fill=False,ec='#5e686f',lw=.45))
    if overlay:
        for r in PROJ.itertuples():
            if r.kind=='non_PtC':
                c=COLORS['PGM'] if r.PGM_rich else COLORS['no_PGM']
                ax.scatter(r.PC1,r.PC2,s=26,c=c,edgecolors='white',linewidths=.6,zorder=5)
            else:
                ax.scatter(r.PC1,r.PC2,s=26,facecolors='none',edgecolors='#282e32',
                           marker='o' if r.kind=='acid' else 's',linewidths=.9,zorder=6)
        positions={'T01':(.19,-.235),'T02':(.35,-.14),'T03':(-.23,-.24),'T04':(-.03,-.23),
                   'T05':(-.93,.13),'T06':(-.63,.145),'T07':(-.47,-.07),'T08':(-.32,-.10),
                   'T09':(-.37,.205),'T10':(-.17,-.14),'T11':(-.085,.026),'T12':(-.17,.18),
                   'T13':(.015,.22),'T14':(.20,.18),'T15':(.24,.055),'T16':(.40,.025)}
        for r in PROJ[PROJ.kind.eq('non_PtC')].itertuples():
            c=COLORS['PGM'] if r.PGM_rich else COLORS['no_PGM']
            label=ax.annotate(r.template,(r.PC1,r.PC2),xytext=positions[r.template],fontsize=LABEL_SIZE,color=c,
                             arrowprops=dict(arrowstyle='-',lw=.75,color='#505961',shrinkA=1.5,shrinkB=3),zorder=4)
            label.set_path_effects([pe.Stroke(linewidth=1.8,foreground='white'),pe.Normal()])
            label.arrow_patch.set_path_effects([pe.Stroke(linewidth=1.9,foreground='white'),pe.Normal()])
        handles=[Line2D([],[],marker='o',ls='',c=COLORS['PGM'],ms=4,label='Six PGM-rich'),
                 Line2D([],[],marker='o',ls='',c=COLORS['no_PGM'],ms=4,label='Ten other'),
                 Line2D([],[],marker='o',ls='',c='#282e32',mfc='white',ms=4,label='Acidic Pt/C'),
                 Line2D([],[],marker='s',ls='',c='#282e32',mfc='white',ms=4,label='Alkaline Pt/C')]
        ax.legend(handles=handles,loc='upper right',frameon=False,ncol=2,fontsize=LEGEND_SIZE,
                  columnspacing=.7,handletextpad=.3,handlelength=1,labelspacing=.25)
    else:group_legend(ax,loc='upper right')
    visible=M.PC1.between(*LIMITS[0])&M.PC2.between(*LIMITS[1])
    DRAW_QA.append(dict(panel='template_projection' if overlay else 'curve_PCA',central_visible=int(visible.sum()),
                       full_range_points=len(M),xlim=LIMITS[0],ylim=LIMITS[1]))


def template_shapes(fig,spec):
    sub=spec.subgridspec(1,2,wspace=.30)
    palette=['#1484b3','#e83f62','#139d88','#9163c4','#c38b19','#565b60','#59afd3','#b56856','#2760c2','#b52063']
    axes=[];n=0
    for index,(group,title) in enumerate([(RICH,'Six PGM-rich'),(OTHER,'Ten other')]):
        ax=fig.add_subplot(sub[index]);axes.append(ax)
        for i,name in enumerate(sorted(group)):
            q=SHAPES[SHAPES.template.eq(name)&SHAPES.eta_mV.between(50,300)]
            p=NATIVE[NATIVE.template.eq(name)&NATIVE.eta_mV.between(50,300)]
            c=palette[i%len(palette)]
            ax.scatter(p.eta_mV,p.aligned_log_current,s=3.0,facecolors='none',edgecolors=c,
                       linewidths=.24,alpha=.15,rasterized=True,zorder=1)
            ax.plot(q.eta_mV,q.aligned_log10_current,c=c,lw=1.2,ls='-',label=name,zorder=3)
            n+=len(p)
        ax.set(xlim=(50,300),ylim=(-.3,4.7),xlabel=r'$|\eta|$ (mV)')
        if index==0:ax.set_ylabel(r'$\log_{10}(j/j_{\mathrm{ref}})$')
        ax.text(.5,1.015,title,c=COLORS['PGM'] if index==0 else COLORS['no_PGM'],fontsize=11,
                transform=ax.transAxes,ha='center',va='bottom')
        ax.set_xticks([50,150,300]);ax.set_yticks([0,2,4])
        ax.legend(loc='upper left',bbox_to_anchor=(0,.99),ncol=2,frameon=False,fontsize=LEGEND_SIZE,handlelength=1.4,
                  handletextpad=.25,columnspacing=.6,labelspacing=.3)
    DRAW_QA.append(dict(panel='templates_with_native_points',points=n,templates=16,line_style='solid',period_shading=False))
    return axes


def main_figure():
    fig=plt.figure(figsize=(11.0,8.6))
    gs=fig.add_gridspec(3,2,left=.078,right=.985,bottom=.081,top=.966,hspace=.30,wspace=.23)
    axes={}
    for letter,row,col in [('A',0,0),('B',0,1),('C',1,0),('D',1,1),('E',2,0),('F',2,1)]:
        box=gs[row,col].get_position(fig);fig.text(box.x0-.063,box.y1+.006,letter,fontsize=PANEL_SIZE,weight='bold')
        if letter=='D':template_shapes(fig,gs[row,col]);continue
        if letter=='C':
            OLD.panel_c(fig,gs[row,col])
            coverage_ax=fig.axes[-1];coverage_ax.set_title('')
            for label in coverage_ax.texts:
                label.set_fontsize(11 if label.get_text().startswith('16 templates') else LABEL_SIZE)
                if label.get_text()=='80% target':
                    label.set_position((.03,78));label.set_va('top')
            assert len(coverage_ax.patches)==30
            assert len(coverage_ax.lines)==1
            assert np.allclose(coverage_ax.lines[0].get_ydata(),80)
            DRAW_QA.append(dict(panel='template_coverage',bars=30,achieved_coverage_only=True,target_percent=80))
            continue
        if letter=='F':
            OLD.panel_f(fig,gs[row,col],small=True)
            composition_ax=fig.axes[-1];composition_ax.set_title('')
            composition_ax.tick_params(axis='x',labelsize=LABEL_SIZE)
            for label in composition_ax.texts:label.set_fontsize(LABEL_SIZE)
            for label in composition_ax.get_legend().get_texts():label.set_fontsize(LEGEND_SIZE)
            continue
        ax=fig.add_subplot(gs[row,col]);axes[letter]=ax
        if letter=='A':raw_lsv(ax)
        else:pca_panel(ax,overlay=letter=='E')
    fig.canvas.draw()
    a,b=axes['B'].get_position(),axes['E'].get_position()
    assert np.allclose([a.width,a.height],[b.width,b.height])
    assert axes['B'].get_xlim()==axes['E'].get_xlim() and axes['B'].get_ylim()==axes['E'].get_ylim()
    assert all(not ax.get_title() for ax in fig.axes)
    export(fig,'Figure7_partial_population_candidate')
    for name,fn,size in [('A_original_LSVs',raw_lsv,(5.4,3.6)),('B_partial_curve_PCA',pca_panel,(5.4,3.6)),
                        ('E_template_projection',lambda ax:pca_panel(ax,True),(5.4,3.6))]:
        fig,ax=plt.subplots(figsize=size,layout='constrained');fn(ax);export(fig,name)
    fig=plt.figure(figsize=(7.2,3.6));gs=fig.add_gridspec(1,1,left=.09,right=.985,bottom=.17,top=.91)
    template_shapes(fig,gs[0]);export(fig,'D_templates_with_native_points')


def diagnostics():
    fig,axs=plt.subplots(1,2,figsize=(9,3.4),layout='constrained')
    for c,ax in zip(CONDITIONS,axs):raw_lsv(ax,c)
    export(fig,'SI_LSVs_by_condition')
    fig,axs=plt.subplots(1,2,figsize=(9,3.4),layout='constrained')
    for c,ax in zip(CONDITIONS,axs):
        scatter(ax,M[M.condition.eq(c)]);ax.set(xlim=FULL[0],ylim=FULL[1],title=c.capitalize(),xlabel='PC1',ylabel='PC2')
        group_legend(ax,loc='upper left')
    export(fig,'SI_PCA_by_condition_full_range')
    fig,axs=plt.subplots(1,2,figsize=(9,3.4),layout='constrained')
    for ax,title,values in [(axs[0],'Observed potential span',M.span_mV),(axs[1],'Score reliability',M.reliability)]:
        c=ax.scatter(M.PC1,M.PC2,c=values,cmap='viridis',s=7,alpha=.65,linewidths=0,rasterized=True)
        ax.set(xlim=LIMITS[0],ylim=LIMITS[1],title=title,xlabel='PC1',ylabel='PC2');fig.colorbar(c,ax=ax,shrink=.75)
    export(fig,'SI_support_and_reliability')
    fig,axs=plt.subplots(1,2,figsize=(9,3.4),layout='constrained')
    load=MODEL['basis']@MODEL['load'];norm=np.linalg.norm(MODEL['load'],axis=0)
    for k in range(load.shape[1]):axs[0].plot(GRID,load[:,k]/norm[k],label=f'PC{k+1}')
    axs[0].set(xlabel=r'$|\eta|$ (mV)',ylabel='Shape eigenfunction',title='Fitted functional basis');axs[0].legend(frameon=False)
    cv=pd.read_csv(OUT/'CV_PAPER_SUMMARY.csv');x=np.arange(len(cv))
    axs[1].bar(x,cv.paper_mean_coverage95,color='#7894a2');axs[1].axhline(.95,c='#b64461',ls='--',lw=1)
    axs[1].set_xticks(x,cv['mask'].str.replace('_','\n'));axs[1].set(ylim=(0,1.05),ylabel='Held-out 95% coverage',title='Predictive calibration')
    export(fig,'SI_loadings_and_validation')
    fig,axs=plt.subplots(1,2,figsize=(9,3.5),layout='constrained')
    ratios=pd.read_csv(OUT/'DISPERSION_RATIOS.csv')
    for i,den in enumerate(['PGM','PtC']):
        z=ratios[ratios.denominator.eq(den)]
        for j,c in enumerate(['pooled',*CONDITIONS]):
            for matched,offset,color in [(False,-.10,'#8d979d'),(True,.10,'#2384a5')]:
                r=z[z.condition.eq(c)&z.support_matched.eq(matched)].iloc[0]
                axs[i].errorbar(j+offset,r.ratio,yerr=[[r.ratio-r.lower95],[r.upper95-r.ratio]],fmt='o',c=color,ms=4,capsize=2)
        axs[i].axhline(1,c='#888888',ls='--',lw=.7);axs[i].set_xticks([0,1,2],['Pooled','Acidic','Alkaline'])
        axs[i].set(ylabel='Uncertainty-aware dispersion ratio',title=f'non-PGM / {NAMES[den]}')
        axs[i].legend(handles=[Line2D([],[],marker='o',ls='',c='#8d979d',label='Original support'),
                               Line2D([],[],marker='o',ls='',c='#2384a5',label='Support-balanced')],frameon=False,fontsize=LEGEND_SIZE)
    export(fig,'SI_uncertainty_and_support_balance')


def report():
    checks=json.loads((OUT/'CHECKS.json').read_text());cv=pd.read_csv(OUT/'CV_PAPER_SUMMARY.csv')
    ratio=pd.read_csv(OUT/'DISPERSION_RATIOS.csv');control=pd.read_csv(OUT/'IDENTICAL_SHAPES_MASK_CONTROL.csv')
    matched=ratio[ratio.condition.eq('pooled')&ratio.support_matched].set_index('denominator')
    n=matched.loc['PGM'];t=matched.loc['PtC']
    neighbors=pd.read_csv(OUT/'PTC_NEAREST_TEMPLATES.csv')
    visible=M.PC1.between(*LIMITS[0])&M.PC2.between(*LIMITS[1])
    native=json.loads((OUT/'NATIVE_POINTS_PROVENANCE.json').read_text())
    readme=f'''# Partial-observation Figure 7 candidate

## Decision
This is a usable candidate for displaying **overlapping response-shape distributions with different dispersion**, not for claiming exclusive chemical clusters or precise reconstructions of unobserved tails. It retains {len(M):,} curves from {M.paper_key.nunique()} papers without a template gate. The original complete-window figure and its analyses remain unchanged.

## What changed
A shows the actual original LSVs of this same cohort: Pt/C gray and drawn last, PGM red, non-PGM blue, with transparency. All observed segments are solid; no 50-150 mV distinction remains. No extrapolated LSV segments are drawn. B shows individual-curve conditional shape scores. C retains the original template coverage scan. D restores {native['plotted_points']:,} original rescaled data points alongside all 16 template lines. E projects those templates and the eight Pt/C families into exactly the B model. F retains the template composition bars and deduplicated unions.

B/E use identical plotting dimensions, axes and full-range insets. Their central view contains {int(visible.sum())}/{len(M)} original-curve score means; every score is shown at its true coordinates in the inset and the full-range SI views. No outlier is removed from fitting or statistics.

## Does partial observation automatically create clustering?
It can create misleading compactness: short curves have less information, and posterior score means shrink toward the shared population prior. The model never sees PGM/non-PGM/Pt/C labels during fitting or tuning, but that alone would not eliminate a missing-support confound.

We therefore retain score covariance, balance the groups' condition/start/end support distributions, and perform an identical-shapes control: the same 75 complete observed curves from 61 papers are shown through each group's actual masks. In that control, the masks alone do not reproduce the broader non-PGM pattern. This control is conditional on the available complete donor curves, not a proof that missingness is ignorable.

After support balancing and including conditional score uncertainty, pooled non-PGM/PGM RMS dispersion is {n.ratio:.2f} [{n.lower95:.2f}, {n.upper95:.2f}], and non-PGM/Pt/C is {t.ratio:.2f} [{t.lower95:.2f}, {t.upper95:.2f}]. The intervals combine whole-paper bootstrap and latent-score draws with the model basis held fixed. They do not include refitting uncertainty or correction for informative censoring. Both acid and alkaline strata retain the direction of the comparison.

## PCA and projection method
This is an observed-only penalized probabilistic functional factor model, not ordinary PCA applied after filling missing cells. A free per-curve intercept removes multiplicative current amplitude without requiring a measured anchor. A smooth cubic-spline mean and loading functions describe log current over 20-300 mV. Only locally supported cells enter the likelihood. Each paper has equal total fitting weight; its curves share that weight.

Three-fold whole-paper validation compares ranks 1-4 and two smoothing strengths, using a one-standard-error rule. Tail/internal masks are applied to native observations before interpolation; training and target grids come from disjoint native points. The chosen model has three modes; the first two account for {100*FRACTIONS[:2].sum():.1f}% of fitted latent shape variance, not a complete-data raw-PCA variance percentage. All cross-validation fits and the final fit converged. Multiplying individual currents by arbitrary constants changes scores by at most {checks['amplitude_invariance_error']:.2g}.

Templates never enter model training. E uses the fitted mean/loadings and the same regularized score operator, with a free amplitude intercept. Each template contributes only its supported range. Acidic Pt/C families use 20-190 or 20-200 mV; their unknown 200-300 mV parts are not supplied or extrapolated. Their plotted scores are therefore conditional estimates, not exactly observed full-range coordinates. Complete-template ordinary least-squares and regularized projections differ by at most {checks['full_template_direct_vs_regularized_max']:.4f} score units. The stored posterior covariance is model-conditional projection uncertainty, not confidence in the fitted template parameters.

All {int(neighbors.PGM_rich.sum())}/{len(neighbors)} Pt/C families have their nearest non-Pt/C template among the six PGM-rich shapes in the full three-mode score space. This agrees with the original template comparison without using templates to fit the population model. Distances and identities are exported in PTC_NEAREST_TEMPLATES.csv.

## Validation limit
Held-out internal-block predictions have paper-balanced RMSE {cv.set_index('mask').loc['internal_block','paper_mean_RMSE']:.3f} log10 units. The tail-mask RMSE is about 0.11-0.18 log10 units. Nominal 95% predictive intervals cover about 93% for internal blocks, 95% for tail-100, 88% for tail-150 and 82% for tail-200. Thus late-tail uncertainty is under-calibrated. Do not use this candidate to claim precise 95% missing-tail reconstructions or uniquely identified mechanisms. Point-based geometry, support sensitivity and uncertainty-aware dispersion are the appropriate discussion.

## Native point normalization in D
Each original observation is plotted at its observed eta and log10[j_original / (beta * template_current(50 mV))]. Beta is the archived positive current-amplitude factor for that curve-template match. The continuous line is log10[template_current(eta)/template_current(50 mV)]. Points need not cross zero at 50 mV because they retain fit residuals; their denominator is a fitted reference current, not necessarily measured j(50) and not exchange current. The native eta/current values and beta are verified against the packaged native arrays and membership table. All {native['points']:,} archived points are preserved; only the 50-300 mV plotting window restricts the displayed points. A curve can contribute to more than one compatible template.

## Reproduce
From the package root run `python 03_ANALYSIS/17_partial_population.py`, then `python 03_ANALYSIS/19_partial_diagnostics.py`, then `python 03_ANALYSIS/18_partial_figures.py`. These write only this candidate folder. `--reuse-cv` reuses the saved tuning choice, but recomputes the final fit and projections.
'''
    (OUT/'README.md').write_text(readme,encoding='utf-8')
    caption=f'''Figure 7. Population response shapes and empirical template compression. (A) Original geometric-area LSVs for {len(M):,} eligible curves from {M.paper_key.nunique()} papers: 411 Pt/C, 873 PGM excluding Pt/C and 1,076 non-PGM. Gray Pt/C curves are drawn above red PGM and blue non-PGM curves. Opacity reduces occlusion. All traces are solid and confined to observed support over 20-300 mV, without extrapolation. (B) Conditional scores from a label-blind, paper-weighted, partial-observation functional shape model over 20-300 mV. At least four supported 10 mV grid cells, 30 mV span and four native in-window observations are required; interpolation gaps cannot exceed 20 mV. Curve-specific intercepts remove current amplitude. First and second mode percentages refer to fitted latent shape variance. Markers are posterior means; short-support curves are less certain and can shrink toward the common prior. (C) Verified achieved template coverage in the original broader non-Pt/C discovery population, unchanged from the frozen scan. (D) Six PGM-rich and ten other templates with {native['plotted_points']:,} rescaled native observations over 50-300 mV. j_ref for each match is beta times that template's 50 mV reference current; line references have beta=1. These are original data points, not samples from the template lines. (E) Templates projected through the same frozen model and score operator as B; no PCA refitting or input beyond template support is used. Circles/squares mark acidic/alkaline Pt/C families. Acidic template projections remain partial-support estimates. B and E have identical axes and plot dimensions; central views contain {int(visible.sum())}/{len(M)} original-curve score means, while full-range insets show all points. No points are omitted from analysis. (F) Per-template composition counts with deduplicated family-union coverage, 542/695 PGM curves for the six templates and 494/647 non-PGM curves for the other ten. Individual bars overlap in membership; the template discovery and partial-PCA denominators differ. These analyses support overlapping shape distributions with different dispersion, not chemically exclusive clusters. Score uncertainty, support balancing, identical-shape masking controls and held-out calibration are reported in the SI.
'''
    (OUT/'CAPTION.md').write_text(caption,encoding='utf-8')
    files=['Figure7_partial_population_candidate','A_original_LSVs','B_partial_curve_PCA','D_templates_with_native_points',
           'E_template_projection','SI_LSVs_by_condition','SI_PCA_by_condition_full_range','SI_support_and_reliability',
           'SI_loadings_and_validation','SI_uncertainty_and_support_balance']
    blocks=[]
    for name in files:
        blocks.append(f'<section><h2>{html.escape(name.replace("_"," "))}</h2><img src="figures/{name}.png" alt="{name}"><p><a href="figures/{name}.pdf">PDF</a> &middot; <a href="figures/{name}.svg">SVG</a></p></section>')
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Figure 7 partial-observation candidate</title><style>body{font:16px Arial,sans-serif;color:#24292d;max-width:1180px;margin:auto;padding:24px}h1{font-size:25px}h2{font-size:19px}p{line-height:1.5}a{color:#177793}img{max-width:100%;height:auto}section{margin:28px 0 44px}</style><h1>Figure 7: partial-observation candidate</h1><p>2,360 curves &middot; 435 papers &middot; one shared shape basis. <a href="README.md">Results and validation</a> &middot; <a href="CAPTION.md">Caption</a></p>'+''.join(blocks)+'</html>'
    (OUT/'index.html').write_text(page,encoding='utf-8')


if __name__=='__main__':
    main_figure();diagnostics();report()
    pdf=PdfReader(PLOTS/'Figure7_partial_population_candidate.pdf')
    fonts=[str(f.get_object()['/BaseFont']) for f in pdf.pages[0]['/Resources']['/Font'].get_object().values()]
    assert all(FONT.replace(' ','') in name.replace(' ','') for name in fonts)
    page_width=float(pdf.pages[0].mediabox.width)
    print_scale=(180/25.4*72)/page_width
    dump(OUT/'FIGURE_CHECKS.json',dict(panels=DRAW_QA,matched_B_E_geometry=True,fonts=fonts,canvas_inches=[11.0,8.6],
         descriptive_main_titles=False,typography_pt=dict(axis=AXIS_SIZE,tick=TICK_SIZE,label=LABEL_SIZE,
                                                         legend=LEGEND_SIZE,panel=PANEL_SIZE,inset_tick=8),
         publication_180mm_pt=dict(axis=AXIS_SIZE*print_scale,tick=TICK_SIZE*print_scale,
                                  legend=LEGEND_SIZE*print_scale),pdf_width_pt=page_width))
    print('Six-panel candidate and supporting diagnostics exported.',flush=True)
