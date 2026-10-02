"""Numerical regression checks against the manuscript's frozen analysis."""
from utils import *


def main():
    out = ROOT/'08_PARTIAL_PCA_CANDIDATE'
    checks = json.loads((out/'CHECKS.json').read_text())
    assert checks['curves'] == 2360 and checks['papers'] == 435 and checks['converged']
    for name, cols in [('SCORES.csv', ['PC1', 'PC2', 'PC3']),
                       ('TEMPLATE_PROJECTIONS.csv', ['PC1', 'PC2', 'PC3']),
                       ('DISPERSION_RATIOS.csv', ['ratio', 'lower95', 'upper95']),
                       ('CV_SUMMARY.csv', ['mean', 'se'])]:
        actual = pd.read_csv(out/name)
        expected = pd.read_csv(PACKAGE/'reference'/name)
        assert len(actual) == len(expected)
        np.testing.assert_allclose(actual[cols], expected[cols], atol=2e-7, rtol=2e-6)
    assert json.loads((out/'SELECTED.json').read_text())['rank'] == 3
    print('Figure 7 reference regression checks passed.', flush=True)


if __name__ == '__main__':
    main()
