"""Observed-only, paper-weighted current and local-growth comparisons."""
from utils import *


def value_at(x, y, eta):
    pos = np.searchsorted(x, eta)
    if pos < len(x) and np.isclose(x[pos], eta, atol=1e-8, rtol=0):
        return y[pos]
    if 0 < pos < len(x) and x[pos] - x[pos - 1] <= 20 + 1e-9:
        return np.interp(eta, x[pos - 1:pos + 1], y[pos - 1:pos + 1])
    return np.nan


def summarize(rows):
    records = []
    keys = ['condition', 'group', 'metric', 'low_mV', 'high_mV']
    for key, data in rows.groupby(keys, sort=True):
        paper = data.groupby('paper_key', sort=True).value.mean().to_numpy()
        rng = np.random.default_rng(SEED + 103)
        boot = paper[rng.integers(len(paper), size=(1999, len(paper)))].mean(axis=1)
        lo, hi = np.quantile(boot, [.025, .975])
        records.append(dict(zip(keys, key), mean=paper.mean(), lower95=lo,
                            upper95=hi, curves=len(data), papers=len(paper)))
    return pd.DataFrame(records)


def main():
    out = ROOT / '08_PARTIAL_PCA_CANDIDATE'
    meta = pd.read_csv(out / 'COHORT.csv')
    series = load_series()
    rows = []
    for row in meta.itertuples():
        x, y = series[row.curve_uid]
        base = dict(curve_uid=row.curve_uid, paper_key=row.paper_key,
                    condition=row.condition, group=row.group)
        for eta in np.arange(20, 301, 5):
            value = value_at(x, y, eta)
            if np.isfinite(value):
                rows.append(dict(base, metric='log10_j', low_mV=eta,
                                 high_mV=eta, value=value))
        for low, high in [(20, 50), (50, 100), (100, 150), (150, 200), (200, 250), (250, 300)]:
            left, right = value_at(x, y, low), value_at(x, y, high)
            native = (x >= low) & (x <= high)
            if not np.isfinite([left, right]).all() or native.sum() < 4:
                continue
            a = max(0, np.searchsorted(x, low, side='right') - 1)
            b = min(len(x) - 1, np.searchsorted(x, high, side='left'))
            if np.diff(x[a:b + 1]).max() > 20 + 1e-9:
                continue
            rows.append(dict(base, metric='growth_per_100mV', low_mV=low,
                             high_mV=high, value=100 * (right - left) / (high - low)))
    rows = pd.DataFrame(rows)
    rows.to_csv(TABLE / 'observed_current_growth_records.csv', index=False)
    summary = summarize(rows)
    summary.to_csv(TABLE / 'observed_current_growth_summary.csv', index=False)
    fig, axes = plt.subplots(2, 2, figsize=(9, 6), layout='constrained')
    for col, condition in enumerate(CONDITIONS):
        for group in GROUPS:
            current = summary[(summary.condition == condition) & (summary.group == group)
                              & (summary.metric == 'log10_j')].sort_values('low_mV')
            growth = summary[(summary.condition == condition) & (summary.group == group)
                             & (summary.metric == 'growth_per_100mV')].sort_values('low_mV')
            color = COLORS[group]
            axes[0, col].plot(current.low_mV, 10 ** current['mean'], color=color, label=LABELS[group])
            axes[0, col].fill_between(current.low_mV, 10 ** current.lower95,
                                      10 ** current.upper95, color=color, alpha=.14, linewidth=0)
            mid = (growth.low_mV + growth.high_mV) / 2
            axes[1, col].errorbar(mid, growth['mean'],
                yerr=[growth['mean'] - growth.lower95, growth.upper95 - growth['mean']],
                color=color, marker='o', markersize=3, capsize=2)
        axes[0, col].set(title=condition.capitalize(), yscale='log', xlim=(20, 300),
                         ylabel='Paper-weighted current (mA cm$^{-2}$)')
        axes[0, col].legend(frameon=False, fontsize=7)
        axes[1, col].set(xlim=(20, 300), xlabel=r'$|\eta|$ (mV)',
                         ylabel='Log-current growth (decades / 100 mV)')
        for row in [0, 1]:
            axes[row, col].set_xticks([20, 50, 100, 150, 200, 250, 300])
    save(fig, 'SI_observed_current_growth', folder='SUPPORTING')
    print(summary[(summary.metric == 'growth_per_100mV') | summary.low_mV.eq(50)].to_string(index=False))


if __name__ == '__main__':
    main()
