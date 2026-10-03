"""Recompute composition bars and unique unions, never summing overlapping bars."""
from utils import *
from metadata import corrected_metadata


def main():
    pairs = corrected_metadata(pd.read_csv(INPUT/'MEMBER_COMPATIBILITY.csv'))
    elements = pairs.active_elements.fillna('[]').map(json.loads)
    pairs['known'] = elements.map(lambda e: isinstance(e, list) and bool(e))
    pairs['pgm'] = elements.map(lambda e: bool(set(e) & {'Pt', 'Pd', 'Rh', 'Ru', 'Ir', 'Os'}))
    records = []
    for name, rows in pairs.groupby('template', sort=True):
        rows = rows.drop_duplicates('curve_uid')
        records.append(dict(template=name, PGM_count=int(rows.pgm.sum()),
            no_PGM_count=int((rows.known & ~rows.pgm).sum()), known_composition=int(rows.known.sum())))
    pd.DataFrame(records).to_csv(TABLE/'template_composition.csv', index=False)
    records = []
    for group, mask in [('PGM', pairs.pgm), ('no_PGM', pairs.known & ~pairs.pgm)]:
        rows = pairs[mask]
        denominator = rows.curve_uid.nunique()
        rich = rows[rows.template.isin(RICH)].curve_uid.nunique()
        other = rows[rows.template.isin(OTHER)].curve_uid.nunique()
        records.append(dict(group=group, covered_population=denominator, rich6=rich, other10=other,
                            rich6_fraction=rich/denominator, other10_fraction=other/denominator))
    pd.DataFrame(records).to_csv(TABLE/'template_composition_union.csv', index=False)
    assert records[0]['covered_population'] == 695 and records[0]['rich6'] == 542
    assert records[1]['covered_population'] == 648 and records[1]['other10'] == 495
    assert pairs.curve_uid.nunique() == 1343 and pairs.known.all()


if __name__ == '__main__':
    main()
