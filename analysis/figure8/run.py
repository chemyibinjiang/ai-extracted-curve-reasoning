"""Reproduce Figure 8 from native screening records and the fixed Figure 7 model."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import sys
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FIG7 = ROOT / 'analysis/figure7'
sys.path.insert(0, str(FIG7 / 'lib'))
import partial_model as model_api
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

GRID = model_api.GRID
PGM = {'Pt', 'Pd', 'Rh', 'Ru', 'Ir', 'Os'}
INITIAL = 'initial_screening_561'
WINDOWS = [(50, 150), (50, 250), (100, 250)]
MEMBERS = {
    'A': ['Pt-Pt', 'Mo-Pt', 'W-Pt', 'Eu-Pt', 'Mn-Pt'],
    'B': ['Ni-Ce', 'Ni-Co', 'Ni-Sr'],
    'C': ['Eu-Ru', 'Ga-Ru', 'Mo-Ru', 'Ga-Pt', 'Sc-Pt', 'V-Pt'],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def elements(sample):
    return sorted(set(sample.split('-')))


def parse_raw(raw, area=1.):
    lines = raw.decode('utf-8-sig').splitlines()
    if lines[0].startswith('CSStudioFile,ID_LSVA,'):
        lines = lines[1:]
    header = lines[0].split()
    density = header == ['E(V)', 'i(A/cm\u00b2)', 'T(s)']
    require(density or header == ['Potential(V)', 'Current(A)', 'Time(s)'], 'Unexpected raw-data header')
    data = np.loadtxt(io.StringIO('\n'.join(lines[1:])), ndmin=2)
    require(data.shape[1] == 3 and len(data) >= 4 and np.isfinite(data).all(), 'Invalid native LSV record')
    if density:
        data[:, 1] *= area
    return data


def collapse(eta, current):
    values = pd.DataFrame({'eta': eta, 'logj': np.log10(current)}).groupby('eta').logj.median().sort_index()
    return values.index.to_numpy(), values.to_numpy()


def prepare(data, area):
    require(np.isfinite(area) and area > 0, 'Invalid geometric area')
    eta = -(data[:, 0] + .9268) * 1000
    current = -data[:, 1] * 1000 / area
    keep = (current >= .2) & (current <= 500) & (np.arange(len(data)) >= np.argmin(current))
    return collapse(eta[keep], current[keep])


def observe(x, y, grid=GRID):
    values = np.full(len(grid), np.nan)
    for k, potential in enumerate(grid):
        pos = np.searchsorted(x, potential)
        if pos < len(x) and np.isclose(x[pos], potential, atol=1e-8, rtol=0):
            values[k] = y[pos]
        elif 0 < pos < len(x) and x[pos] - x[pos - 1] <= 20 + 1e-9:
            values[k] = np.interp(potential, x[pos - 1:pos + 1], y[pos - 1:pos + 1])
    return values


def support(x, observed):
    mask = np.isfinite(observed)
    count = int(mask.sum())
    span = float(np.ptp(GRID[mask])) if count else 0.
    native = int(((x >= 20) & (x <= 300)).sum())
    return dict(n_native=native, n_grid=count, span_mV=span,
                eligible=count >= 4 and span >= 30 and native >= 4)


def load_inputs():
    manifest = json.loads((HERE / 'inputs/manifest.json').read_text(encoding='utf-8'))
    archive = HERE / 'inputs/initial_screening.zip'
    require(sha(archive.read_bytes()) == manifest['archive_sha256'], 'Input ZIP checksum mismatch; check Git LFS')
    model_path = FIG7 / 'reference/MODEL.npz'
    require(sha(model_path.read_bytes()) == manifest['figure7_model_sha256'], 'Figure 7 model changed')
    model = dict(np.load(model_path))
    require(np.array_equal(model['grid'], GRID), 'Figure 7 grid mismatch')
    require(np.allclose(model['basis'], model_api.B, atol=1e-13, rtol=0), 'Figure 7 basis mismatch')
    with ZipFile(archive) as z:
        require(set(z.namelist()) == set(manifest['members']), 'Unexpected ZIP contents')
        for name, checksum in manifest['members'].items():
            require(sha(z.read(name)) == checksum, f'Input checksum mismatch: {name}')
        meta = pd.read_csv(io.BytesIO(z.read(manifest['metadata_path'])))
        require(len(meta) == 709 and meta['sample'].is_unique, 'Unexpected source metadata')
        meta = meta[meta.source_type.eq(INITIAL)]
        require(len(meta) == 561, 'Expected 561 initial-screening records')
        records, observations, profiles = [], [], {}
        for row in meta.itertuples(index=False):
            name = f'hd_separation_ml/data_extraction/all_data/LSV/{row.sample}.txt'
            x, y = prepare(parse_raw(z.read(name), row.LSV_geometry_area_cm2), row.LSV_geometry_area_cm2)
            v = observe(x, y)
            el = elements(row.sample)
            records.append(dict(sample=row.sample, id=row.sample, study='-'.join(el),
                elements=';'.join(el), group='PGM' if PGM.intersection(el) else 'no_PGM',
                area_cm2=row.LSV_geometry_area_cm2, raw_path=name, raw_sha256=manifest['members'][name],
                **support(x, v)))
            observations.append(v)
            profiles[row.sample] = (x, y)
    cohort = pd.DataFrame(records)
    observed = np.array(observations)[cohort.eligible]
    experiment = cohort[cohort.eligible].reset_index(drop=True)
    result = model_api.infer(model, observed)
    for k in range(3):
        experiment[f'PC{k+1}'] = result['score'][:, k]
    experiment['observed_log_RMSE'] = np.sqrt(np.nanmean((result['prediction'] - observed)**2, axis=1))
    lit = pd.read_csv(FIG7 / 'reference/SCORES.csv')
    points = pd.read_csv(FIG7 / 'inputs/POINTS.csv')
    by_curve = {}
    for uid, group in points.groupby('curve_uid', sort=False):
        good = np.isfinite(group.eta_mV) & np.isfinite(group.j) & group.j.gt(0)
        by_curve[uid] = collapse(group.loc[good, 'eta_mV'], group.loc[good, 'j'])
    ly = np.array([observe(*by_curve[uid]) for uid in lit.curve_uid])
    lr = model_api.infer(model, ly)
    require(np.allclose(lr['score'], lit[['PC1', 'PC2', 'PC3']], atol=1e-8, rtol=0), 'Literature projection mismatch')
    posterior = np.load(FIG7 / 'reference/POSTERIOR.npz')
    require(np.array_equal(posterior['curve_uid'], lit.curve_uid.to_numpy(str)), 'Literature row order mismatch')
    require(np.allclose(lr['covariance'], posterior['covariance'], atol=1e-10, rtol=0), 'Literature covariance mismatch')
    lit['id'], lit['study'] = lit.curve_uid, lit.paper_key
    return model, cohort, experiment, observed, profiles, lit, ly


def pair_errors(profiles):
    rms, maximum = np.zeros((2, len(profiles), len(profiles)))
    for i, profile in enumerate(profiles):
        d = profile - profiles
        residual = d - d.mean(axis=1, keepdims=True)
        rms[i] = np.sqrt(np.mean(residual**2, axis=1))
        maximum[i] = np.max(abs(residual), axis=1)
    return rms, maximum


def group_series(cohort, native):
    grid = np.arange(50., 251., 5.)
    names = sorted(cohort['sample'])
    y = np.array([observe(*native[name], grid) for name in names])
    good = np.isfinite(y).all(axis=1)
    names, y = np.array(names)[good], y[good]
    rms, maximum = pair_errors(y)
    distance = np.maximum(rms/.02, maximum/.05)
    distance = (distance + distance.T) / 2
    np.fill_diagonal(distance, 0)
    labels = fcluster(linkage(squareform(distance), method='complete'), 1, criterion='distance')
    groups = [np.flatnonzero(labels == label) for label in np.unique(labels)]
    groups.sort(key=lambda g: (-len(g), tuple(names[g])))
    return pd.DataFrame([dict(series=f'S{k:02d}', n=len(g), members=';'.join(names[g]),
        worst_RMS=float(rms[np.ix_(g, g)].max()), worst_maximum=float(maximum[np.ix_(g, g)].max()))
        for k, g in enumerate(groups, 1)])


def series_outputs(cohort, native, out):
    groups = group_series(cohort, native)
    groups.to_csv(out / 'all_series.csv', index=False)
    rows, checks, profiles = [], [], {}
    for panel, names in MEMBERS.items():
        match = groups[groups.members.map(lambda s: set(s.split(';')) == set(names))]
        require(len(match) == 1, f'Panel {panel} is not a complete series')
        for name in names:
            x, y = native[name]
            values = observe(x, y, np.arange(50., 301., 5.))
            require(np.isfinite(values).all(), f'Incomplete display support: {name}')
            inside = (x > 50) & (x < 300)
            xx = np.r_[50, x[inside], 300]
            yy = np.interp(xx, x, y)
            profiles[name] = (xx, yy, values[0])
            rows.extend(dict(panel=panel, sample=name, eta_mV=t, current_mA_cm2=10**v,
                normalized_log_current=v-values[0]) for t, v in zip(xx, yy))
        for high in [250, 300]:
            grid = np.arange(50., high+1, 5.)
            values = np.array([observe(*native[name], grid) for name in names])
            rms, maximum = pair_errors(values)
            require(rms.max() <= .02 and maximum.max() <= .05, f'Panel {panel} exceeds matching tolerances')
            checks.append(dict(panel=panel, series=match.iloc[0].series, window=f'50-{high}', n=len(names),
                amplitude_span=float(10**np.ptp(values.mean(axis=1))),
                worst_RMS=float(rms.max()), worst_maximum=float(maximum.max())))
    pd.DataFrame(rows).to_csv(out / 'panel_ABC_native_profiles.csv', index=False)
    pd.DataFrame(checks).to_csv(out / 'panel_ABC_series_checks.csv', index=False)
    return profiles


def spread(x, weights, mask, covariance=None):
    w = weights[mask] / weights[mask].sum()
    xx = x[mask]
    center = np.sum(w[:, None]*xx, axis=0)
    variance = np.sum(w*np.sum((xx-center)**2, axis=1))
    if covariance is not None:
        variance += np.sum(w*(1-w)*np.trace(covariance[mask], axis1=1, axis2=2))
    return float(np.sqrt(variance))


def contrast(frame, observed, model, seed, draws=1999):
    result = model_api.infer(model, observed)
    x, cov = result['score'], result['covariance']
    pgm = frame.group.isin(['PGM', 'PtC']).to_numpy()
    bins = frame.assign(comparison_group=np.where(pgm, 'PGM-containing', 'non-PGM'))
    weights = (1/bins.groupby(['comparison_group', 'study']).id.transform('size')).to_numpy()
    r0, r1 = [spread(x, weights, m, cov) for m in [pgm, ~pgm]]
    clusters, indices = np.unique(frame.study, return_inverse=True)
    rng = np.random.default_rng(seed)
    chol = np.linalg.cholesky(cov)
    ratios = []
    for _ in range(draws):
        counts = rng.multinomial(len(clusters), np.ones(len(clusters))/len(clusters))
        w = weights*counts[indices]
        if min(w[pgm].sum(), w[~pgm].sum()) <= 0:
            continue
        sampled = x + np.einsum('nij,nj->ni', chol, rng.normal(size=x.shape))
        denominator = spread(sampled, w, pgm)
        if denominator > 0:
            ratios.append(spread(sampled, w, ~pgm)/denominator)
    require(len(ratios) > 0, 'No valid resampled dispersion ratios')
    stats = dict(PGM_n=int(pgm.sum()), nonPGM_n=int((~pgm).sum()),
        PGM_clusters=int(frame.loc[pgm, 'study'].nunique()),
        nonPGM_clusters=int(frame.loc[~pgm, 'study'].nunique()),
        PGM_radius=r0, nonPGM_radius=r1, ratio=r1/r0,
        low=float(np.quantile(ratios, .025)), high=float(np.quantile(ratios, .975)), draws=len(ratios))
    scores = frame[['id', 'study', 'group']].copy()
    for k in range(3):
        scores[f'PC{k+1}'] = x[:, k]
    scores['posterior_trace'] = np.trace(cov, axis1=1, axis2=2)
    return stats, scores


def dispersion_outputs(model, lit, ly, exp, ey, out):
    stats, score_tables = [], []
    for source, frame, observations in [('literature', lit, ly), ('experiment', exp, ey)]:
        initial = frame.condition.eq('alkaline').to_numpy() if source == 'literature' else np.ones(len(exp), bool)
        for low, high in WINDOWS:
            cells = (GRID >= low) & (GRID <= high)
            keep = initial & np.isfinite(observations[:, cells]).all(axis=1)
            m, y = frame[keep].copy(), observations[keep].copy()
            y[:, ~cells] = np.nan
            row, scores = contrast(m, y, model, 20261010+low+(source == 'experiment'))
            stats.append(dict(source=source, window=f'{low}-{high}', **row))
            scores['source'], scores['window'] = source, f'{low}-{high}'
            score_tables.append(scores)
    pd.DataFrame(stats).to_csv(out / 'matched_support_dispersion.csv', index=False)
    pd.concat(score_tables).to_csv(out / 'matched_support_scores.csv', index=False)
    exp.to_csv(out / 'panel_E_experimental_scores.csv', index=False)
    lit[lit.condition.eq('alkaline')].to_csv(out / 'panel_D_literature_scores.csv', index=False)


def verify(out, cohort, model, ey):
    require(len(cohort) == 561 and cohort.eligible.sum() == 524, 'Experimental inclusion changed')
    counts = cohort[cohort.eligible].group.value_counts().to_dict()
    require(counts == {'no_PGM': 464, 'PGM': 60}, 'Experimental composition counts changed')
    errors = {}
    for filename, keys in [
        ('panel_ABC_native_profiles.csv', ['panel', 'sample', 'eta_mV']),
        ('panel_ABC_series_checks.csv', ['panel', 'window']),
        ('matched_support_dispersion.csv', ['source', 'window']),
        ('panel_D_literature_scores.csv', ['curve_uid']),
        ('panel_E_experimental_scores.csv', ['sample'])]:
        expected = pd.read_csv(HERE / 'reference' / filename).set_index(keys).sort_index()
        actual = pd.read_csv(out / filename).set_index(keys).sort_index()
        require(actual.index.equals(expected.index), f'Rows changed: {filename}')
        cols = expected.select_dtypes(include='number').columns
        errors[filename] = float(np.max(abs(actual[cols].to_numpy()-expected[cols].to_numpy())))
        require(np.allclose(actual[cols], expected[cols], atol=1e-7, rtol=1e-8), f'Numeric mismatch: {filename}')
    original = model_api.infer(model, ey)['score']
    shifted = model_api.infer(model, ey + np.random.default_rng(15).normal(size=(len(ey), 1)))['score']
    error = float(np.max(abs(original-shifted)))
    require(error < 1e-7, 'Projection is not invariant to current scaling')
    report = dict(initial_records=561, included=524, excluded=37, composition=counts,
                  reference_max_errors=errors, amplitude_invariance_error=error, verified=True)
    dump(out / 'verification.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/figure8')
    parser.add_argument('--no-figure', action='store_true', help='Reproduce and verify numerical results only')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    model, cohort, exp, ey, native, lit, ly = load_inputs()
    cohort.to_csv(args.output / 'experimental_selection.csv', index=False)
    profiles = series_outputs(cohort, native, args.output)
    dispersion_outputs(model, lit, ly, exp, ey, args.output)
    report = verify(args.output, cohort, model, ey)
    if not args.no_figure:
        from plot import build
        build(model, lit, exp, profiles, args.output)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
