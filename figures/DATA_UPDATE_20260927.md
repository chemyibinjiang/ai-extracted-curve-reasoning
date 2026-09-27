# Figure Data Update

The manuscript figures retain the finalized composition. The September 27
analysis updates the data in Figures 1D and 4-6; Figure 1A-C and Figures 2-3 are unchanged. SVGs remain
editable, and PNGs are exported at 3,000 pixels wide.

## Figure 1

Panel D illustrates the four alkaline families used in Figure 6. The raw and
normalized plots contain the same 188 curves (B1-B4: 37, 79, 25 and 47 members).
The normalized points, VHT shape curves and kinetic parameter coordinates are
taken from the same analysis as Figure 6B and E. Labels 1-4 correspond to B1-B4.
The ordinate remains the absolute T/V ratio in this schematic, whereas Figure 6E
expresses T/V relative to the acidic value. These selected alkaline responses
illustrate the workflow; they do not represent all 348 acidic and alkaline curves.

Panel C retains its schematic plot and additive-voltage expression. BV denotes
the effective BV form with independently fitted anodic and cathodic coefficients;
the expression does not impose a fixed coefficient sum. No quantitative fit
statistics are presented in this panel. The frames, axes, arrows and layout are
preserved throughout Figure 1.

## Figure 4

Panel A shows observed local slopes and is unchanged. The same 3,033 curves from
473 papers were refitted with effective BV and BV+jR, allowing independent
anodic and cathodic coefficients. At R2 >= 0.99, the accepted counts are 1,588
(52.4%) and 2,361 (77.8%). The violin plots include all curves. The three
histograms use the 2,361 accepted BV+jR fits with equal weight per curve;
their medians are 77.6 mV/dec, 0.428 ohm cm2 and 1.87 mA/cm2. The slope coordinate
is the effective cathodic asymptote, b_BV = ln(10)RT/(F alpha_c), not a local
derivative or an elementary-step assignment. The axis ranges are retained;
149 slope values and 36 resistance values lie beyond their displayed ranges,
but remain in the histogram denominators and median calculations.

The three example panels keep the same measured points. Their BV/BV+jR R2
values are 0.9615/0.9996 (Pt/C), 0.9982/0.9982 (N-Ni), and 0.9706/0.9706 (WO3).

## Figure 5

Panel A, EIS measurements, NiFeP and KSCN measured curves, and all conceptual
schematics are unchanged. Updated artists show the cycle-dependent BV+jR fits,
the fitted-resistance/EIS relationship, the NiMo model fits and calculated
coverage, and the independent NiFeP resistances versus inverse layer count.
The cycle-resistance relationship has R2 = 0.9857. The inverse-layer coefficient
is 17.772 ohm cm2 layer.

NiMo voltage RMSE is 2.096 mV (BV), 0.427 mV (BV+jR), and 0.661 mV (VHT).
The added jR term reduces the empirical-fit error by approximately fivefold;
BV already exceeds R2 = 0.99. The independent VHT fit has no added resistance
term. See [the Figure 5 caption](Figure5_caption.md) for the source and methods.

## Figure 6

Four templates cover 59/73 acidic and 188/234 alkaline nonlinear curves.
The family memberships are A1-A4: 15, 12, 13, 19; B1-B4: 37, 79, 25, 47.
Family labels refer to this updated library, not to the former five-family
alkaline assignment. Raw and normalized curves use these memberships throughout.

Panel D retains the two-dimensional Q-versus-b_BV display. It is a projection
of the effective-BV shape space: alpha_a is fitted independently and is supplied
with alpha_c in `analysis/figure6/expected/PARAMETER_COORDINATES.csv`.
Panel E and F use the acid DeltaG-only and alkaline DeltaG-plus-T/V VHT models.
Panel E plots T/V relative to the shared acidic value, 2.2584675346.
The adsorption-energy coordinates are A1-A4: 50.21, 60.91, 69.45, 34.64 meV;
B1-B4: 69.20, 25.35, 72.22, 50.60 meV.

The mean and sample SD in F assign equal weight to each family and are drawn
only where all four families have fitted support. Individual curves and their
dominant-control crossings are also restricted to fitted support. The alkaline
mean crosses at 31.03 and 154.76 mV. There are 11 displayed dominant-control
crossings in total, including the mean crossings.

## Reproduction

Run `analysis/effective_bv/run.py` followed by `analysis/effective_bv/artwork.py`
as described in [REPRODUCIBILITY.md](../REPRODUCIBILITY.md). The updater changes
data artists inside the finalized SVGs rather than substituting diagnostic plots.
`reproducibility/artwork-effective-bv-20260927.json` records input and output
hashes and preservation checks; `scripts/validate_figures.py` audits the
published files and the Figure 6 numerical tables.
