from utils import *
PROJ=pd.read_csv(TABLE/"template_composition.csv")
COUNTS=pd.read_csv(TABLE/"template_composition_union.csv").set_index("group")

def panel_c(fig,spec,small=False):
    ax=fig.add_subplot(spec);s=pd.read_csv(TABLE/'template_coverage_scan.csv');k=s[s.K.eq(16)].iloc[0]
    colors=np.where(s.K.eq(16),COLORS['PGM'],'#9bb9c9')
    ax.bar(s.K,100*s.coverage,width=.8,color=colors)
    ax.axhline(80,c='#999999',lw=.6,ls='--');ax.set(xlim=(0,31),ylim=(0,104),xlabel='Number of templates',ylabel='Eligible curves covered (%)')
    ax.text(.03,81.5,'80% target',transform=ax.get_yaxis_transform(),fontsize=6.3,color='#666666')
    ax.set_xticks([1,8,16,24,30]);ax.set_yticks([0,40,80,100])
    ax.text(.03,.97,f'16 templates\n{int(k.covered_curves):,}/{int(k.denominator):,} ({100*k.coverage:.1f}%)',transform=ax.transAxes,va='top',fontsize=7.5 if small else 9)

def panel_f(fig,spec,small=False):
    ax=fig.add_subplot(spec)
    order=sorted(RICH)+sorted(OTHER);s=PROJ.set_index('template').loc[order]
    assert np.all(s.PGM_count+s.no_PGM_count==s.known_composition)
    x=np.arange(16)
    ax.bar(x,s.no_PGM_count,color=COLORS['no_PGM'],width=.72,label='non-PGM')
    ax.bar(x,s.PGM_count,bottom=s.no_PGM_count,color=COLORS['PGM'],width=.72,label='PGM-containing')
    ax.set(xlim=(-.65,15.65),ylim=(0,360),ylabel='Compatible curves')
    ax.set_title('Template-family composition',pad=5)
    ax.set_xticks(x,order);ax.tick_params(axis='x',labelsize=6.6,pad=3,length=2.5)
    ax.set_yticks([0,100,200,300]);ax.axvline(5.5,color='#aeb4b8',lw=.7,ls=':')
    for group,left,right,color,field,description in [
            ('PGM',-.35,5.35,COLORS['PGM'],'rich6','unique PGM curves'),
            ('no_PGM',5.65,15.35,COLORS['no_PGM'],'other10','unique non-PGM curves')]:
        row=COUNTS.loc[group];num=int(row[field]);den=int(row.covered_population)
        ax.plot([left,left,right,right],[294,306,306,294],color=color,lw=.8)
        ax.text((left+right)/2,316,f'{num}/{den} ({100*num/den:.1f}%)\n{description}',
                ha='center',va='bottom',color=color,fontsize=7.2,linespacing=1.15)
    handles,labels=ax.get_legend_handles_labels()
    ax.legend(handles[::-1],labels[::-1],loc='upper right',bbox_to_anchor=(.99,.78),
              frameon=False,fontsize=7,handlelength=1.15,handletextpad=.45,labelspacing=.3)
    for center,title,color in [(2.5,'Six PGM-rich templates',COLORS['PGM']),
                               (10.5,'Ten other templates',COLORS['no_PGM'])]:
        ax.text(center,-.13,title,transform=ax.get_xaxis_transform(),ha='center',va='top',
                color=color,fontsize=7.5)
