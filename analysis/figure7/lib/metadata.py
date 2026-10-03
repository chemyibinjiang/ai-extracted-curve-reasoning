"""Apply source-checked annotations without rewriting the raw extraction."""
import json
from pathlib import Path


def corrected_metadata(frame):
    frame = frame.copy()
    path = Path(__file__).resolve().parents[1] / 'inputs/METADATA_CORRECTIONS.json'
    for correction in json.loads(path.read_text(encoding='utf-8')):
        selected = frame.curve_uid.eq(correction['curve_uid'])
        elements = json.dumps(correction['active_elements'])
        values = {
            'enrich_active_elements': elements,
            'enrich_reported_material_name': correction['material_name'],
            'active_elements': elements,
            'material_name': correction['material_name'],
            'composition_known': True,
            'contains_noble': False,
        }
        for column, value in values.items():
            if column in frame:
                frame.loc[selected, column] = value
    return frame
