"""Numerical regression checks against the manuscript's frozen analysis."""
from utils import *


def main():
    out = ROOT/'08_PARTIAL_PCA_CANDIDATE'
    checks = json.loads((out/'CHECKS.json').read_text())
    assert checks['curves'] == 2361 and checks['papers'] == 435 and checks['converged']
    for name, cols in [('SCORES.csv', ['PC1', 'PC2', 'PC3']),
                       ('TEMPLATE_PROJECTIONS.csv', ['PC1', 'PC2', 'PC3']),
                       ('DISPERSION_RATIOS.csv', ['ratio', 'lower95', 'upper95']),
                       ('CV_SUMMARY.csv', ['mean', 'se'])]:
        actual = pd.read_csv(out/name)
        expected = pd.read_csv(PACKAGE/'reference'/name)
        assert len(actual) == len(expected)
        np.testing.assert_allclose(actual[cols], expected[cols], atol=2e-7, rtol=2e-6)
    assert json.loads((out/'SELECTED.json').read_text())['rank'] == 3
    actual = pd.read_csv(TABLE/'observed_current_growth_summary.csv')
    expected = pd.read_csv(PACKAGE/'reference/OBSERVED_CURRENT_GROWTH.csv')
    keys = ['condition', 'group', 'metric', 'low_mV', 'high_mV', 'curves', 'papers']
    pd.testing.assert_frame_equal(actual[keys], expected[keys])
    np.testing.assert_allclose(actual[['mean', 'lower95', 'upper95']],
                               expected[['mean', 'lower95', 'upper95']],
                               atol=2e-7, rtol=2e-6)
    print('Figure 7 reference regression checks passed.', flush=True)


if __name__ == '__main__':
    main()
