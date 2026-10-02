"""Re-evaluate every selected curve-template match from native currents."""
from utils import *
import sys
sys.path.insert(0, str(INPUT))
import effective_bv as bv


def main():
    pairs = pd.read_csv(INPUT/'MEMBER_COMPATIBILITY.csv')
    templates = pd.read_csv(INPUT/'SELECTED_TEMPLATES.csv').set_index('template')
    native = np.load(INPUT/'NATIVE_CURVES.npz')
    currents, potentials, sizes = native['J'], native['Y'], native['n']
    positions = pd.Index(native['curve_uid']).get_indexer(pairs.curve_uid)
    errors = []
    for row, i in zip(pairs.itertuples(), positions):
        assert i >= 0
        n = int(sizes[i]); t = templates.loc[row.template]
        j, eta = currents[i,:n], potentials[i,:n]
        prediction = bv.predict(j/row.current_scale_beta,
            dict(log_j0=0., fraction=t.fraction, coefficient_sum=t.coefficient_sum, R=t.Q_mV))
        r2 = 1 - np.sum((eta-prediction)**2)/np.sum((eta-eta.mean())**2)
        errors.append(abs(r2-row.empirical_R2))
        assert r2 >= .99-1e-9
    assert max(errors) < 1e-7
    dump(TABLE/'native_match_validation.json',dict(matches=len(pairs),
        unique_curves=pairs.curve_uid.nunique(), maximum_R2_difference=max(errors),
        method='Re-evaluated native voltage residuals at archived amplitude factors; not reoptimized.'))
    print('Native match R2 checks:',len(pairs),'max difference',max(errors),flush=True)


if __name__ == '__main__':
    main()
