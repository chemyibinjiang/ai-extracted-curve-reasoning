"""Original-curve cohort and full-support audit, independent of template labels."""
from utils import *
from metadata import corrected_metadata


def main():
    m=pd.read_csv(INPUT/'CURVES.csv')
    audit=pd.read_csv(INPUT/'CATALYST_AUDIT.csv')[['curve_uid','is_ptc']]
    cols=['curve_uid','enrich_active_elements','enrich_current_normalization_basis',
          'enrich_ir_compensation_status','enrich_electrolyte_identity','enrich_reported_material_name']
    canon=corrected_metadata(pd.read_csv(INPUT/'canonical_curves.csv',usecols=cols,low_memory=False))
    m=m.merge(audit,on='curve_uid',validate='one_to_one').merge(canon,on='curve_uid',validate='one_to_one')
    elements=m.enrich_active_elements.map(json.loads)
    m['composition_known']=elements.map(lambda x:isinstance(x,list) and len(x)>0)
    m['pgm']=elements.map(lambda x:bool(set(x)&{'Pt','Pd','Rh','Ru','Ir','Os'}))
    m['group']=np.where(m.is_ptc,'PtC',np.where(m.pgm,'PGM',np.where(m.composition_known,'no_PGM','unknown')))
    m['condition']=m.regime_class
    m['eligible']=m.canonical_fit_eligible&m.condition.isin(CONDITIONS)&m.enrich_current_normalization_basis.eq('geometric_area')&m.composition_known
    m['base_exclusion']=np.select([~m.canonical_fit_eligible,~m.condition.isin(CONDITIONS),~m.enrich_current_normalization_basis.eq('geometric_area'),~m.composition_known],['source_ineligible','other_condition','other_basis','unknown_composition'],default='eligible')
    library=pd.read_csv(INPUT/'LIBRARY_COHORT.csv'); B=compatibility()
    coverable=set(library.loc[B.any(0),'curve_uid'])
    adequacy=pd.read_csv(INPUT/'INDIVIDUAL_ADEQUACY.csv')
    adequacy=adequacy[adequacy.scenario.eq('pooled_300')]
    assert set(adequacy.loc[adequacy.adequate,'curve_uid'])==coverable
    m['original_template_cohort']=m.curve_uid.isin(library.curve_uid)
    m['original_template_eligible']=m.curve_uid.isin(coverable)
    pairs=corrected_metadata(pd.read_csv(INPUT/'MEMBER_COMPATIBILITY.csv'))
    memberships=pairs.groupby('curve_uid').template.agg(lambda v:';'.join(sorted(set(v))))
    m['original_compatible_templates']=m.curve_uid.map(memberships).fillna('')
    m['original_covered16']=m.original_compatible_templates.ne('')
    m['original_rich6']=m.original_compatible_templates.map(lambda s:bool(set(s.split(';'))&RICH))
    m['original_other10']=m.original_compatible_templates.map(lambda s:bool(set(s.split(';'))&OTHER))
    series=load_series()
    m['usable_eta_min_mV']=m.curve_uid.map(lambda u:series[u][0].min())
    m['usable_eta_max_mV']=m.curve_uid.map(lambda u:series[u][0].max())
    selected,logj,grid,support=profiles(m[m.eligible],series,50,150)
    m['functional_50_150_eligible']=m.curve_uid.isin(selected.curve_uid)
    m['functional_exclusion']=m.curve_uid.map(support.set_index('curve_uid').status).fillna(m.base_exclusion)
    m.to_csv(DATA/'cohort_master.csv',index=False)
    pairs.to_csv(DATA/'template_membership_full.csv',index=False)
    support.to_csv(TABLE/'functional_support_audit.csv',index=False)
    np.savez_compressed(DATA/'functional_profiles_50_150.npz',curve_uid=selected.curve_uid.to_numpy(str),
                        logj=logj,shape=logj-logj[:,[0]],eta_mV=grid,fw=fw_for(len(grid)))
    selected.to_csv(DATA/'pca_cohort.csv',index=False)
    stages=[]
    for name,mask in [('source',np.ones(len(m),bool)),('original_nonlinear_non_PtC',m.original_template_cohort),
                      ('template_eligible',m.original_template_eligible),('covered16',m.original_covered16),
                      ('functional_base',m.eligible),('primary_50_150',m.functional_50_150_eligible)]:
        s=m[mask]; stages.append(dict(stage=name,condition='all',group='all',curves=len(s),papers=s.paper_key.nunique()))
        for (c,g),v in s.groupby(['condition','group']):
            stages.append(dict(stage=name,condition=c,group=g,curves=len(v),papers=v.paper_key.nunique()))
    pd.DataFrame(stages).to_csv(TABLE/'cohort_stages.csv',index=False)
    unknown=m[m.original_covered16&~m.composition_known]
    unknown.to_csv(TABLE/'unknown_composition_audit.csv',index=False)
    assert m.curve_uid.is_unique and len(m)==3033
    print(pd.DataFrame(stages).query("stage=='primary_50_150'").to_string(index=False),flush=True)
    print('Unknown covered:',unknown[['curve_uid','paper_key','enrich_reported_material_name']].to_dict('records'),flush=True)


if __name__=='__main__':main()
