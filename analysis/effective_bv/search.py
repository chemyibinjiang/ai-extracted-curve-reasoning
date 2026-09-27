"""Search the complete 276,551-template effective-BV library from coordinates."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
os.environ.setdefault('NUMBA_NUM_THREADS', '8')
sys.path.insert(0, str(ROOT / 'analysis/common'))
sys.path.insert(0, str(ROOT / 'analysis/figure6/vendor/empirical'))
import numpy as np
import pandas as pd
import effective_bv as bv
import coverage_solver as coverage
from search_numerics import profile_candidates


def grid():
    q = np.unique(np.r_[0., 1e-12, 1e-10, 1e-8, 1e-6, 1e-5,
        np.logspace(-4, 3, 141), 10.**np.array([4, 5, 6, 7, 8, 9, 9.5, 9.9, 10])])
    records = [(a, 2., x) for a in np.arange(1, 100)/100 for x in q]
    fractions = np.unique(np.r_[.01, .02, .04, .06, .08, np.arange(.1, 1, .025), .95, .97, .99])
    qs = np.unique(np.r_[0., 1e-6, 1e-4, np.logspace(-3, 3, 61), 1e5, 1e8, 1e10])
    sums = [.025, .05, .1, .2, .35, .5, .75, 1., 1.25, 1.5, 1.75]
    records.extend((a, s, x) for a in fractions for s in sums for x in qs)
    seen = {tuple(np.round(r, 12)) for r in records}
    for a in np.arange(1, 100)/100:
        for s in [.001, .005, .01, .025, .05, .1, .2, .35, .5, .75, 1., 1.25, 1.5, 1.75, 1.9, 1.95]:
            for x in q:
                key = tuple(np.round([a, s, x], 12))
                if key not in seen:
                    records.append((a, s, x)); seen.add(key)
    assert len(records) == 276551
    return pd.DataFrame(records, columns=['fraction', 'coefficient_sum', 'Q_mV'])


def cohort(condition):
    folder, upper = ('acidic', 200) if condition == 'acid' else ('alkaline', 300)
    source = ROOT / f'analysis/figure6/inputs/{folder}/cohort_all_points.csv'
    frame = pd.read_csv(source, float_precision='round_trip')
    groups = {}
    for uid, g in frame.groupby('curve_uid', sort=True):
        g = g[g.eta_mV.between(0, upper)].sort_values(['j_mA_cm2', 'fit_point_index'])
        if len(g) < 5 or g.eta_mV.var(ddof=0) <= 1e-20: continue
        j, y = g.j_mA_cm2.to_numpy(), g.eta_mV.to_numpy()
        r = np.clip(j@y/(j@j), 0, 100)
        if np.sum((y-r*j)**2) > .01*np.sum((y-y.mean())**2): groups[uid] = g
    assert len(groups) == (73 if condition == 'acid' else 234)
    ids = sorted(groups)
    n = np.array([len(groups[u]) for u in ids], dtype=np.int64)
    j, y = np.ones((len(ids), n.max())), np.zeros((len(ids), n.max()))
    for i, u in enumerate(ids): j[i,:n[i]], y[i,:n[i]] = groups[u].j_mA_cm2, groups[u].eta_mV
    limits = np.array([.01*np.sum((y[i,:v]-y[i,:v].mean())**2) for i,v in enumerate(n)])
    return source, ids, groups, n, j, y, limits


def run(output, condition, candidates):
    output.mkdir(parents=True, exist_ok=True)
    source, ids, groups, n, j, y, limits = cohort(condition)
    fingerprint = hashlib.sha256(source.read_bytes() + Path(__file__).read_bytes()
        + (HERE/'search_numerics.py').read_bytes() + (ROOT/'analysis/figure6/vendor/empirical/model.py').read_bytes()
        + (ROOT/'analysis/common/effective_bv.py').read_bytes() + candidates.to_csv(index=False).encode()).hexdigest()
    cache = output/'PROFILES.npz'
    if cache.exists():
        with np.load(cache) as saved:
            assert str(saved['fingerprint']) == fingerprint, 'Use a new output directory for changed inputs or code'
            assert list(saved['ids']) == ids
            losses, scales = saved['losses'], saved['scales']
    else:
        blocks = []
        for start in range(0, len(candidates), 2000):
            block = candidates.iloc[start:start+2000].to_numpy(float)
            blocks.append(profile_candidates(j, y, n, block))
            print(f'{condition}: {min(start+2000,len(candidates))}/{len(candidates)} templates', flush=True)
        losses = np.vstack([v[0] for v in blocks]); scales = np.vstack([v[1] for v in blocks])
        for k,i in np.argwhere(abs(losses/limits[None,:]-1) < 1e-5):
            t = candidates.iloc[k]; z = scales[k,i]
            pred = bv.predict(j[i,:n[i]], dict(log_j0=z, fraction=t.fraction,
                coefficient_sum=t.coefficient_sum, R=t.Q_mV*np.exp(-z)))
            losses[k,i] = np.sum((pred-y[i,:n[i]])**2)
        np.savez_compressed(cache, losses=losses, scales=scales, ids=np.array(ids), fingerprint=fingerprint)
    prep = coverage.prepare(losses, limits, np.arange(len(ids)))
    scans = []
    for k in range(1,11):
        result = coverage.solve(prep, k, time_limit=60.)
        if not result['certified_count']: result = coverage.solve(prep, k, time_limit=180.)
        scans.append(dict(condition=condition, K=k, denominator=len(ids), **result))
        print(f'{condition}: K={k}, covered={result["covered"]}, certified={result["certified_count"]}', flush=True)
    pd.DataFrame(scans).to_csv(output/'COVERAGE_SCAN.csv', index=False)
    chosen = next(r for r in scans if r['covered'] >= np.ceil(.8*len(ids)))
    selected = sorted(chosen['selected'], key=lambda k: bv.VT*np.log(10)/(candidates.iloc[k].fraction*candidates.iloc[k].coefficient_sum))
    rows, members = [], []
    for index,k in enumerate(selected):
        t = candidates.iloc[k]
        rows.append(dict(candidate_index=k, family=('A' if condition=='acid' else 'B')+str(index+1),
            **t.to_dict(), alpha_a=(1-t.fraction)*t.coefficient_sum,
            alpha_c=t.fraction*t.coefficient_sum, b_mV_dec=bv.VT*np.log(10)/(t.fraction*t.coefficient_sum)))
    for i,uid in enumerate(ids):
        k = min(selected, key=lambda k: losses[k,i]); t = candidates.iloc[k]; z = scales[k,i]
        pred = bv.predict(j[i,:n[i]], dict(log_j0=z, fraction=t.fraction,
            coefficient_sum=t.coefficient_sum, R=t.Q_mV*np.exp(-z)))
        loss = np.sum((pred-y[i,:n[i]])**2)
        np.testing.assert_allclose(loss, losses[k,i], rtol=2e-6, atol=2e-6)
        members.append(dict(curve_uid=uid, family=rows[selected.index(k)]['family'],
            beta=np.exp(z), r2=1-.01*loss/limits[i], rmse=np.sqrt(loss/n[i]),
            adequate=bool(loss<=limits[i]), compatible_count=int((losses[selected,i]<=limits[i]).sum())))
    assert sum(r['adequate'] for r in members) == chosen['covered']
    pd.DataFrame(rows).to_csv(output/'TEMPLATES.csv', index=False)
    pd.DataFrame(members).to_csv(output/'ASSIGNMENTS.csv', index=False)
    (output/'SELECTED.json').write_text(json.dumps(chosen, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/effective-bv-search')
    parser.add_argument('--condition', choices=('acid','KOH','both'), default='both')
    parser.add_argument('--grid-only', action='store_true')
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.output == ROOT/'analysis' or ROOT/'analysis' in args.output.parents: parser.error('Keep outputs outside analysis/')
    args.output.mkdir(parents=True, exist_ok=True)
    candidates = grid(); candidates.to_csv(args.output/'CANDIDATES.csv', index=False)
    if not args.grid_only:
        for condition in (('acid','KOH') if args.condition=='both' else (args.condition,)):
            run(args.output/condition, condition, candidates)


if __name__ == '__main__': main()
