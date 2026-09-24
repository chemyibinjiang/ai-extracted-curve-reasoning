"""Equal-paper weighting and weighted empirical quantiles."""
import numpy as np


def pw(g):
    return (1 / g.groupby('paper_key').curve_uid.transform('size') / g.paper_key.nunique()).to_numpy()


def quant(values, weights, qs=(.25, .5, .75)):
    v, w = np.asarray(values, float), np.asarray(weights, float)
    if not len(v) or not np.isfinite(v).all() or np.any(w <= 0):
        raise ValueError('Invalid quantile input')
    order = np.argsort(v, kind='stable')
    cdf = np.cumsum(w[order]) / w.sum()
    return [float(v[order][min(np.searchsorted(cdf, q-1e-12), len(v)-1)]) for q in qs]
