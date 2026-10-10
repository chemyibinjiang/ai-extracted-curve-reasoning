"""Figure 8 artwork; plotting follows the approved manuscript layout."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, NullLocator
from matplotlib import font_manager
from run import MEMBERS, WINDOWS, dump

RED, BLUE, GRAY = '#cf4969', '#2384a5', '#50575b'
SOURCE_COLORS = {'literature': GRAY, 'experiment': '#277e72'}
PALETTE = ['#1484b3', '#e83f62', '#139d88', '#9163c4', '#c38b19', '#565b60']

def style():
    font = 'Arial'
    if not any(f.name == font for f in font_manager.fontManager.ttflist):
        font = 'DejaVu Sans'
    plt.rcParams.update({'font.family':font, 'font.weight':'bold', 'font.size':10,
        'axes.labelsize':12, 'axes.labelweight':'bold', 'axes.titleweight':'bold',
        'xtick.labelsize':10, 'ytick.labelsize':10, 'legend.fontsize':8.5,
        'mathtext.fontset':'custom', 'mathtext.rm':font+':bold',
        'mathtext.it':font+':bold:italic', 'mathtext.bf':font+':bold', 'mathtext.sf':font+':bold',
        'axes.spines.top':False, 'axes.spines.right':False, 'axes.linewidth':.65,
        'pdf.fonttype':42, 'svg.fonttype':'path', 'savefig.facecolor':'white', 'legend.frameon':False})


def series_panel(ax, letter, raw):
    names = MEMBERS[letter]
    colors = ([GRAY, PALETTE[1], PALETTE[0], PALETTE[3], PALETTE[4]] if letter == 'A'
              else [PALETTE[i] for i in range(len(names))])
    styles = (['-', '-', '--', '-.', ':'] if letter == 'A'
              else ['-', '--', '-.'] if letter == 'B' else ['-', '-', '-', '--', '--', '--'])
    arial = plt.rcParams['font.family'][0] == 'Arial'
    inset = ax.inset_axes([.64, .12, .33, .34] if arial else [.69, .12, .28, .29])
    for name, color, linestyle in zip(names, colors, styles):
        x, y, anchor = raw[name]
        ax.plot(x, 10**y, color=color, lw=1.45, ls=linestyle, label=name)
        inset.plot(x, y-anchor, color=color, lw=1.05, ls=linestyle)
    limits={'A':(5,200),'B':(1,50),'C':(3,200)}
    ticks={'A':[5,10,50,100],'B':[1,5,10,50],'C':[5,10,50,100]}
    ax.set(xlim=(50, 300), ylim=limits[letter], yscale='log', xticks=[50, 150, 300], yticks=ticks[letter],
        xlabel=r'$|\eta|$ (mV)', ylabel=r'$|j|$ (mA cm$^{-2}$)')
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, pos: f'{v:g}'))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.legend(loc='upper left', ncol=2, labelspacing=.23, columnspacing=.55,
        handlelength=1.5, handletextpad=.35, borderaxespad=.3, fontsize=8.5)
    inset.set(xlim=(50,300), ylim=(-.025,1.28), xticks=[50,300], yticks=[0,.5,1])
    inset.set_xlabel(r'$|\eta|$ (mV)', fontsize=8 if arial else 7.5, labelpad=.5)
    inset.set_ylabel(r'$\log_{10}[j/j(50)]$', fontsize=8 if arial else 7.5, labelpad=1)
    inset.tick_params(labelsize=7.5, length=2.5, pad=1)
    for spine in inset.spines.values():
        spine.set_linewidth(.55)
    return inset


def pca_panel(ax, d, experiment=False):
    counts = {}
    for group, color in [('no_PGM',BLUE), ('PGM',RED), ('PtC',GRAY)]:
        z = d[d.group.eq(group)]
        if not len(z):
            continue
        counts[group] = len(z)
        ax.scatter(z.PC1, z.PC2, s=10 if experiment else 7,
            alpha=.45 if experiment else .38, color=color, edgecolors='none',
            zorder={'no_PGM':1,'PGM':2,'PtC':3}[group], rasterized=True)
    ax.axhline(0, color='#b4bac0', lw=.45, ls=':', zorder=0)
    ax.axvline(0, color='#b4bac0', lw=.45, ls=':', zorder=0)
    ax.set(xlim=(-1.8,1.2), ylim=(-.92,.92), xticks=[-1.5,-.5,.5], yticks=[-.8,-.4,0,.4,.8],
        xlabel='PC1 (78.5%)', ylabel='PC2 (18.5%)')
    assert d.PC1.between(-1.8,1.2).all() and d.PC2.between(-.92,.92).all()
    label = 'Experimental library' if experiment else 'Alkaline literature'
    ax.text(.025, .97, label, transform=ax.transAxes, va='top', fontsize=10)
    names = {'PGM':'PGM' if experiment else 'PGM (non-Pt/C)', 'no_PGM':'non-PGM','PtC':'Pt/C'}
    handles = [Line2D([],[],color={'PGM':RED,'no_PGM':BLUE,'PtC':GRAY}[g],lw=1.5,
                     label=f'{names[g]} (n={counts[g]})') for g in ['PtC','PGM','no_PGM'] if g in counts]
    ax.legend(handles=handles, loc='lower right', fontsize=8, handlelength=1.4,
        labelspacing=.2, borderaxespad=.25)
    if experiment:
        p = d[d['sample'].eq('Pt-Pt')].iloc[0]
        ax.scatter([p.PC1],[p.PC2],s=42,marker='*',color=GRAY,edgecolors='white',linewidths=.55,zorder=6)
        ax.annotate('Pt-Pt',(p.PC1,p.PC2),xytext=(.38,.46),fontsize=8.5,color=GRAY,
            arrowprops=dict(arrowstyle='-',color=GRAY,lw=.7,shrinkA=2,shrinkB=4),zorder=7)


def dispersion_panel(ax, stats):
    main = stats
    for k, (lo, hi) in enumerate(WINDOWS):
        for source, dy, marker in [('literature',-.13,'o'), ('experiment',.13,'s')]:
            row = main[main.source.eq(source)&main.window.eq(f'{lo}-{hi}')].iloc[0]
            ax.errorbar(row.ratio, k+dy, xerr=[[row.ratio-row.low],[row.high-row.ratio]],
                color=SOURCE_COLORS[source], fmt=marker, ms=4.5, lw=1.15, capsize=3,
                label=source.capitalize() if k==0 else None)
    ax.axvline(1,color='#949b9e',lw=.7,zorder=0)
    high=max(2.,np.ceil(main.high.max()*2)/2+.05)
    low=min(.75,np.floor(main.low.min()*4)/4-.05)
    ax.set(xlim=(low,high),ylim=(2.85,-.6),yticks=[0,1,2],yticklabels=['50-150','50-250','100-250'],
        xlabel='Shape spread ratio\n(non-PGM / PGM-containing)',ylabel=r'$|\eta|$ window (mV)')
    ticks=np.arange(.5,high,.5)
    ax.set_xticks(ticks[ticks>=low])
    handles=[Line2D([],[],ls='',marker=marker,ms=4.5,color=SOURCE_COLORS[source],label=source.capitalize())
             for source,marker in [('literature','o'),('experiment','s')]]
    ax.legend(handles=handles,loc='lower left',bbox_to_anchor=(.20,.01),fontsize=8.5,
        ncol=2,columnspacing=.8,handlelength=1.1,borderaxespad=0)


def layout_check(fig, axes):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    checks, overlaps = [], []
    for label, ax in axes.items():
        all_axes=[ax, *ax.child_axes]
        for aa in all_axes:
            text=[aa.xaxis.label,aa.yaxis.label,*aa.texts,*aa.get_xticklabels(),*aa.get_yticklabels()]
            if aa.get_legend():
                text.extend(aa.get_legend().get_texts())
            for t in text:
                if not t.get_visible() or not t.get_text():
                    continue
                bb=t.get_window_extent(renderer)
                assert bb.x0>=0 and bb.y0>=0 and bb.x1<=fig.bbox.width and bb.y1<=fig.bbox.height, t.get_text()
            checks.append(dict(panel=label,child=aa is not ax,text_bounds_pass=True,
                               bounds=list(aa.get_position().bounds)))
        for child in ax.child_axes:
            legend=ax.get_legend()
            if legend and legend.get_window_extent(renderer).overlaps(child.get_tightbbox(renderer)):
                overlaps.append(label)
            for line in ax.lines:
                xy=ax.transData.transform(np.column_stack([line.get_xdata(),line.get_ydata()]))
                boxes=[child.bbox,child.xaxis.label.get_window_extent(renderer),child.yaxis.label.get_window_extent(renderer)]
                for box in boxes:
                    assert not any(box.contains(*v) for v in xy), f'Inset hides data in {label}'
    assert not overlaps, f'Legend/inset overlap: {overlaps}'
    f=axes['F']
    assert f.get_legend().get_window_extent(renderer).x0 > f.transData.transform((1,0))[0]
    for t in fig.texts:
        assert fig.bbox.contains(*t.get_window_extent(renderer).get_points()[0])
    return checks


def build(model, lit, exp, raw, out):
    style()
    fractions=np.linalg.norm(model['load'],axis=0)**2
    fractions/=fractions.sum()
    assert np.allclose(np.round(100*fractions[:2],1),[78.5,18.5])
    fig=plt.figure(figsize=(11.0,7.0))
    gs=fig.add_gridspec(2,3,left=.074,right=.986,bottom=.10,top=.957,wspace=.36,hspace=.38,
                       height_ratios=[1,1])
    axes={}
    for k,letter in enumerate('ABCDEF'):
        ax=fig.add_subplot(gs[k//3,k%3]);axes[letter]=ax
        box=ax.get_position()
        fig.text(box.x0-.059,box.y1+.010,letter,fontsize=20,weight='bold')
    for letter in 'ABC':
        series_panel(axes[letter],letter,raw)
    pca_panel(axes['D'],lit[lit.condition.eq('alkaline')])
    pca_panel(axes['E'],exp,True)
    stats=pd.read_csv(out/'matched_support_dispersion.csv')
    dispersion_panel(axes['F'],stats)
    checks=layout_check(fig,axes)
    for ext in ['png','pdf','svg']:
        fig.savefig(out/f'Figure8.{ext}',dpi=300,facecolor='white')
    plt.close(fig)
    dump(out/'layout_validation.json',dict(figure_inches=[11,7],font=plt.rcParams['font.family'][0],font_weight='bold',
         label_pt=12,tick_pt=10,legend_pt=8.5,panel_letter_pt=20,axes=checks,
         same_PCA_limits=True,clipped_PCA_points=0,original_Figure7_colors=True))
