"""Check released dataset hashes, counts and provenance joins without refitting."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data_literature/zenodo_extracted_curve_dataset_v1'


def validate(folder=DATA):
    for line in (folder / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        digest, name = line.split('  ', 1)
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Dataset checksum mismatch: {name}')

    def rows(name):
        with (folder / name).open(encoding='utf-8-sig', newline='') as stream:
            return list(csv.DictReader(stream))

    sources = rows('source_publication_records.csv')
    panels = rows('panel_metadata.csv')
    curves = rows('curve_metadata.csv')
    points = rows('curve_points_long.csv')
    axes = rows('axis_fits.csv')
    source_ids = {r['source_record_id'] for r in sources}
    panel_ids = {r['panel_uid'] for r in panels}
    curve_ids = {r['curve_uid'] for r in curves}
    counts = dict(source_records=len(sources), unique_dois=len({r['source_doi'] for r in sources}),
                  panels=len(panels), curves=len(curves), points=len(points), axis_fits=len(axes))
    expected = dict(source_records=590, unique_dois=573, panels=1035, curves=4211,
                    points=132314, axis_fits=2070)
    if counts != expected:
        raise ValueError(f'Dataset counts changed: {counts}')
    if (len(source_ids), len(panel_ids), len(curve_ids)) != (590, 1035, 4211):
        raise ValueError('Duplicate primary keys')
    if not all(r['source_record_id'] in source_ids and r['panel_uid'] in panel_ids for r in curves):
        raise ValueError('Missing source or panel provenance')
    if {r['curve_uid'] for r in points} != curve_ids:
        raise ValueError('Missing or unmatched curve coordinates')
    return dict(checksums='pass', provenance_joins='pass', **counts)


if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
