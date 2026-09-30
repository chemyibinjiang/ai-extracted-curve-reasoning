# Unified Pt/C Kinetic Fitting

Figures 1D and 6 now use one fixed-alpha VHT fitting protocol. The figure
types, panel arrangement and manually edited artwork are retained. Figure
1A-C and Figures 2-5 are unchanged from the
[27 September update](DATA_UPDATE_20260927.md).

## Figure 1

Panel D uses the same four alkaline families, normalized shapes and kinetic
parameters as Figure 6. The 188 associated curves and memberships are unchanged
(B1-B4: 37, 79, 25 and 47). Its schematic ordinate is the absolute T/V ratio;
Figure 6E uses the ratio relative to the common acidic baseline.

## Figure 6

The empirical templates and assignments are unchanged: four templates cover
59/73 acidic and 188/234 alkaline nonlinear curves. The VHT fits use fixed
elementary symmetry factors alphaV = alphaH = 0.5 and minimize pooled voltage
MSE with equal weight per template. All G, GH, GT and GHT comparisons use this
same objective, support, grids and bounds. The effective BV coefficients in
the empirical templates are separate parameters and remain independently fitted.

The main representation remains G in acid and GT in KOH. The shared acidic
T/V baseline is 2.198587079606414. Adsorption-energy coordinates are A1-A4:
50.29, 60.82, 69.63 and 35.39 meV; B1-B4: 69.14, 25.57, 72.20 and 50.64 meV.
The maximum family RMSE is 0.762 mV in acid and 1.442 mV in KOH. Replaying the
kinetic shapes against the associated raw curves gives 48/59 and 165/188
curves with R2 >= 0.99, respectively. These kinetic-transfer counts are distinct
from the empirical-template membership counts above.

Panel F retains equal-family mean and sample SD, restricted to common fitted
support. Individual profiles and crossings are also restricted to fitted
support. Exact coordinates, profiles, crossings, all alternative fits and raw
replays are supplied in [checked numerical outputs](../analysis/effective_bv/published/)
and [Figure 6 artwork tables](../analysis/figure6/expected/).

## SI Comparison

SI Section 8.5, Tables S20-S21 and Figures S14-S15 use the same fitted results.
GH and GT both meet the alkaline reconstruction criteria, but B3 can have
different Volmer/Heyrovsky control profiles. The full GHT model also has an
exact complementary solution at equal symmetry factors, so its current fit
alone does not identify a unique coverage branch. The code checks both the
amplitude-scaled current invariance and the exchanged V/H sensitivities.

## Reproduction

Follow [REPRODUCIBILITY.md](../REPRODUCIBILITY.md). The `families` stage produces
both the main reconstruction and SI comparisons, with no second fitting
objective. The artwork updater replaces data artists inside the finalized
SVGs. See the [verification record](../reproducibility/VERIFICATION_20260930.md)
and [artwork audit](../reproducibility/artwork-effective-bv-20260930.json).
