"""Generate the updated analysis summary without modifying manuscript artwork."""
import html
import json
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "analysis/common"))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde
import effective_bv as bv

BLUE, RED, GREEN, GOLD = "#087fbc", "#ec3d60", "#07967f", "#c68a18"


def read(path):
    return pd.read_csv(path, float_precision="round_trip")


def save(fig, path):
    for suffix in ("png", "svg"):
        fig.savefig(path.with_suffix("."+suffix), dpi=190, facecolor="white")
    plt.close(fig)


def population(output, assets):
    frame = read(output / "figure4/FITS.csv")
    fig, axes = plt.subplots(2, 3, figsize=(11, 6.4), layout="constrained")
    for ax, key, title in [(axes[0,0], "r2", "Goodness of fit"), (axes[0,1], "rmse", "Voltage error")]:
        groups = [frame.loc[frame.model.eq(m), key].to_numpy() for m in ("BV", "BV+jR")]
        transformed = [np.log10(v) for v in groups] if key == "rmse" else groups
        if key == "r2":
            grid = np.linspace(.8, 1, 401)
            for center, values, color in zip([1,2],groups,[BLUE,RED]):
                density = gaussian_kde(values, bw_method=.006/np.std(values, ddof=1))(grid)
                width = .36*density/density.max()
                ax.fill_betweenx(grid,center-width,center+width,color=color,alpha=.5)
                q1,median,q3 = np.quantile(values,[.25,.5,.75])
                ax.plot([center,center],[q1,q3],c="black",lw=3)
                ax.plot([center-.12,center+.12],[median,median],c="black",lw=1.2)
            ax.text(.5,.02,f"Below 0.8: BV {sum(groups[0]<.8)}, BV + jR {sum(groups[1]<.8)}",
                    ha="center",transform=ax.transAxes,fontsize=8)
        else:
            violins = ax.violinplot(transformed, showmedians=True)
            for body, color in zip(violins["bodies"], [BLUE, RED]):
                body.set_facecolor(color)
                body.set_alpha(.55)
        ax.set_xticks([1,2], ["BV", "BV + jR"])
        ax.set_title(title)
        if key == "r2":
            ax.set(ylim=(.8,1.005), ylabel=r"$R^2$")
        else:
            ax.set(ylabel="Voltage RMSE (mV)")
            ax.set_yticks([-2,-1,0,1,2,3], ["0.01","0.1","1","10","100","1000"])
    g = frame.groupby("model").r2.apply(lambda v: 100*v.ge(.99).mean())
    axes[0,2].barh([1,0], [g["BV"],g["BV+jR"]], color=[BLUE,RED], height=.42)
    axes[0,2].set(yticks=[1,0], yticklabels=["BV", "BV + jR"], xlim=(0,100), xlabel="Curves (%)",
                   title=r"$R^2 \geq 0.99$ | 3,033 curves")
    for y, value in [(1,g["BV"]),(0,g["BV+jR"])]:
        axes[0,2].text(value+2,y,f"{value:.1f}%", va="center", fontsize=10)
    accepted = frame[frame.model.eq("BV+jR") & frame.r2.ge(.99)]
    for ax, col, bins, title, label, color in [
        (axes[1,0],"b_mV_dec",np.arange(20,225,5),"Effective cathodic slope",r"$b_c$ (mV dec$^{-1}$)",BLUE),
        (axes[1,1],"R",np.linspace(0,5,51),"Apparent resistance",r"$R_{app}$ ($\Omega$ cm$^2$)",RED),
        (axes[1,2],"j0",np.logspace(-8,3,45),"Current scale",r"$j_0$ (mA cm$^{-2}$)",GREEN)]:
        values = accepted[col].to_numpy()
        ax.hist(values,bins=bins,weights=np.full(len(values),100/len(values)),color=color)
        ax.axvline(np.median(values),color="black",lw=.8,ls="--")
        ax.set(title=title,xlabel=label,ylabel="Curves (%)")
        ax.text(.04 if col == "j0" else .97,.97,f"Median = {np.median(values):.3g}",
                ha="left" if col == "j0" else "right",va="top",transform=ax.transAxes)
        if col == "j0":
            ax.set_xscale("log")
        else:
            ax.set_xlim(bins[0],bins[-1])
    save(fig,assets/"population")
    examples = read(output / "figure4/EXAMPLE_CURVES.csv")
    fits = frame.set_index(["curve_uid","model"])
    fig, axes = plt.subplots(1,3,figsize=(11,3),layout="constrained")
    for ax,label in zip(axes,["20 wt% Pt/C","N-Ni","WO3"]):
        g = examples[examples.display_label.eq(label)]
        uid = g.curve_uid.iloc[0]
        ax.plot(g.eta_mV,g.j,"o",mfc="white",mec="black",ms=3,label="Data",zorder=3)
        current = np.geomspace(g.j.min(),g.j.max(),250)
        for model,color,style in [("BV",BLUE,"--"),("BV+jR",RED,"-")]:
            ax.plot(bv.predict(current,fits.loc[(uid,model)]),current,style,c=color,lw=1.7,label=model)
        ax.set(title=g.display_label.iloc[0],xlabel=r"$|\eta|$ (mV)",ylabel=r"$|j|$ (mA cm$^{-2}$)")
        ax.legend(frameon=False,fontsize=8)
    save(fig,assets/"population_examples")


def examples(output,assets):
    results = json.loads((output/"figure5/RESULTS.json").read_text())
    cycles = read(output/"figure5/B_CYCLE_R.csv")
    layer = read(output/"figure5/D_NIFEP_PREDICTIONS.csv")
    layerfits = read(output/"figure5/D_NIFEP_FITS.csv")
    fig,axes = plt.subplots(1,3,figsize=(11,3.1),layout="constrained")
    axes[0].plot(cycles.Rs_EIS_ohm,cycles.R_BVjR_ohm_cm2,"o",color=BLUE)
    x = np.linspace(cycles.Rs_EIS_ohm.min(),cycles.Rs_EIS_ohm.max(),100)
    axes[0].plot(x,results["B"]["trend_slope"]*x+results["B"]["trend_intercept"],color=RED,lw=1.6)
    for r in cycles.itertuples():
        axes[0].annotate(str(r.cycle),(r.Rs_EIS_ohm,r.R_BVjR_ohm_cm2),xytext=(5,2),textcoords="offset points")
    axes[0].set(title="Cycle-dependent resistance",xlabel=r"EIS $R_s$ ($\Omega$)",ylabel=r"Fitted $R_{app}$ ($\Omega$ cm$^2$)")
    shared = results["D_NiFeP"]["shared"]
    for (n,g),color in zip(layer.groupby("layers"),[BLUE,RED,GREEN]):
        q = g.j_mA_cm2.to_numpy()/n
        axes[1].plot(g.eta_mV,q,"o",mfc="none",mec=color,ms=3,label=f"{n} layers")
    q = np.geomspace((layer.j_mA_cm2/layer.layers).min(),(layer.j_mA_cm2/layer.layers).max(),200)
    axes[1].plot(bv.predict(q,shared),q,color="black",lw=1.7,label="Shared fit")
    axes[1].set(title="NiFeP current normalization",xlabel=r"$|\eta|$ (mV)",ylabel=r"$|j| / N$ (mA cm$^{-2}$)")
    axes[1].legend(frameon=False,fontsize=8)
    x = np.linspace(0,1/12,100)
    axes[2].plot(1/layerfits.layers,layerfits.independent_R,"o",color=BLUE,label="Independent fits")
    axes[2].plot(x,results["D_NiFeP"]["inverse_layer_slope"]*x,color=RED,lw=1.7)
    axes[2].set(title="NiFeP inverse-layer trend",xlabel="1 / Number of layers",ylabel=r"$R_{app}$ ($\Omega$ cm$^2$)")
    axes[2].legend(frameon=False,fontsize=8)
    save(fig,assets/"example_trends")


def families(output,assets):
    fig,axes = plt.subplots(2,4,figsize=(11,5.6),layout="constrained")
    for row,condition in enumerate(("acid","KOH")):
        templates = read(output/f"figure6/{condition}/TEMPLATES.csv")
        points = read(output/f"figure6/{condition}/POINT_PREDICTIONS.csv")
        for ax,t in zip(axes[row],templates.itertuples()):
            g = points[points.family.eq(t.family)&points.adequate]
            ax.plot(g.eta_mV,g.x,"o",ms=1.4,color=".65",alpha=.3)
            x = np.geomspace(t.x_min,t.x_max,250)
            y = bv.predict(x,dict(log_j0=0.,fraction=t.fraction,coefficient_sum=t.coefficient_sum,R=t.Q_mV))
            ax.plot(y,x,c=BLUE if condition=="acid" else GREEN,lw=1.8)
            ax.set(yscale="log",title=f"{t.family} (n={t.n_curves})",xlabel=r"$|\eta|$ (mV)",ylabel="Rescaled current")
    save(fig,assets/"templates")
    control = read(output/"figure6/RATE_CONTROL.csv")
    means = read(output/"figure6/RATE_CONTROL_MEAN_SD.csv")
    fig,axes = plt.subplots(2,5,figsize=(12,4.8),layout="constrained")
    for row,condition in enumerate(("acid","KOH")):
        m = means[means.condition.eq(condition)&means.all_families_supported]
        for step,color,label,style in [("V",BLUE,"Volmer","-"),("H",GREEN,"Heyrovsky","--"),("T",RED,"Tafel","-")]:
            axes[row,0].plot(m.eta_mV,m[f"X_{step}_mean"],color=color,ls=style,label=label,lw=1.7)
            axes[row,0].fill_between(m.eta_mV,m[f"X_{step}_mean"]-m[f"X_{step}_sd"],
                                    m[f"X_{step}_mean"]+m[f"X_{step}_sd"],color=color,alpha=.13)
        axes[row,0].set_title(("Acid" if condition=="acid" else "KOH")+" | Mean +/- SD")
        g = control[control.condition.eq(condition)&control.inside_fitted_support]
        for ax,(family,own) in zip(axes[row,1:],g.groupby("family")):
            for step,color,style in [("V",BLUE,"-"),("H",GREEN,"--"),("T",RED,"-")]:
                ax.plot(own.eta_mV,own[f"X_{step}"],c=color,ls=style,lw=1.5)
            ax.set_title(family)
        for ax in axes[row]:
            ax.set(ylim=(0,1),xlim=(0,200 if condition=="acid" else 300),yticks=[0,.5,1],xlabel=r"$|\eta|$ (mV)")
        axes[row,0].set_ylabel("Degree of rate control")
    axes[0,0].legend(frameon=False,fontsize=7,loc="upper right")
    save(fig,assets/"rate_control")


def run(output):
    plt.rcParams.update({"font.family":"Arial","font.size":9,"axes.titleweight":"bold",
        "axes.labelweight":"bold","axes.spines.top":False,"axes.spines.right":False,"svg.fonttype":"none"})
    assets = output/"assets"
    assets.mkdir(exist_ok=True)
    population(output,assets)
    examples(output,assets)
    families(output,assets)
    pop = read(output/"figure4/MODEL_SUMMARY.csv")
    kin = read(output/"figure6/KINETIC_SUMMARY.csv")
    nimo = read(output/"figure5/nimo/C_NIMO_METRICS.csv")
    nifep = read(output/"figure5/D_NIFEP_MODEL_COMPARISON.csv")
    nifep_display = nifep[['scope','layers','model','n','rmse_mV','r2','Rapp_geometric_ohm_cm2']].rename(
        columns={'scope':'Fit', 'layers':'Layers', 'model':'Model', 'n':'Points',
                 'rmse_mV':'RMSE (mV)', 'r2':'R2', 'Rapp_geometric_ohm_cm2':'Rapp (ohm cm2)'})
    empirical = json.loads((output/"figure6/EMPIRICAL_SUMMARY.json").read_text())
    mainkin = kin[(kin.condition.eq("acid")&kin.model.eq("DeltaG_only"))|
                  (kin.condition.eq("KOH")&kin.model.eq("DeltaG_T"))]
    trends = json.loads((output/"figure5/RESULTS.json").read_text())
    md = """# Effective BV: updated analysis for Figures 4-6

All empirical fits use independently fitted effective anodic and cathodic
coefficients. No fixed coefficient-sum comparison is part of this analysis.

## Figure 4

The complete 3,033-curve cohort (473 papers; 80,399 points) was reoptimized for
both BV and BV+jR. Accepted counts are 1,588 (52.4%) and 2,361 (77.8%). Parameter
distributions, example predictions, and model local-slope decompositions were
recomputed. The observed, model-independent local slopes do not change.

## Figure 5

Cycle-dependent BV+jR fits and their EIS trend, shared and independent NiFeP
layer fits, and the NiMo BV/BV+jR/VHT comparison were reoptimized. NiMo VHT
coverage, symmetry, five-fold validation and fitting-window controls were
recomputed. Compensation accounting and the independent KSCN kinetic model
are unchanged; their numerical results were recalculated.

NiMo BV already exceeds R2 = 0.99 after freeing the coefficients. The BV+jR
advantage is the approximately fivefold reduction in voltage RMSE, also
retained in held-out prediction, not a pass/fail distinction at R2 = 0.99.

## Figure 6

The variable-coefficient template search already completed in this round
supplies four acid and four alkaline templates, covering 59/73 and 188/234
nonlinear curves. All current amplitudes and memberships were rechecked against
the exact inverse equation. The finite-grid search was not rerun a second time.
VHT models were optimized from 12 starts per condition and sharing scheme,
retaining previously optimized solutions when no new start improved them.
Acid is reconstructed with DeltaG alone; KOH with DeltaG plus T/V. Raw-curve
kinetic replay, coverage and rate control were recalculated.

## Files and scope

This report contains current-model diagnostic plots. The manuscript artwork is
under figures/manuscript/ and is updated separately with artwork.py, preserving
the finalized plot types and layout. Generating this report does not edit Word
documents or manuscript SVGs. Numerical results are in figure4/, figure5/, and
figure6/.

The theoretical form is motivated by Prats and Chan (2021),
https://doi.org/10.1039/D1CP04134G. Its use here is empirical comparison of
polarization curves. The added linear-in-current term is part of this analysis.
Numerical bounds: coefficient sum [0.001, 2], cathodic fraction [0.01, 0.99],
j0 [1e-12, 1e8] mA cm^-2, R [0, 100] ohm cm^2. No voltage offset is fitted.
"""
    (output/"SUMMARY.md").write_text(md,encoding="utf-8")
    def table(frame):
        return '<div class="scroll">'+frame.to_html(index=False,border=0,na_rep="",float_format=lambda x:f"{x:.4g}")+"</div>"
    markup = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Effective BV | Figures 4-6 reanalysis</title><style>
body{{font:16px/1.5 Arial,sans-serif;color:#161616;margin:0;background:#fff}}main{{max-width:1180px;margin:auto;padding:26px 22px}}
h1{{font-size:27px;margin:0 0 8px}}h2{{font-size:21px;margin-top:34px;border-bottom:1px solid #bbb;padding-bottom:7px}}
img{{display:block;width:100%;height:auto;margin:18px 0}}table{{border-collapse:collapse;font-size:14px;white-space:nowrap}}
td,th{{padding:7px 13px;border-bottom:1px solid #ddd;text-align:left}}th{{font-weight:bold}}.scroll{{overflow-x:auto}}a{{color:#0871a5}}
.lead{{border-left:4px solid #07967f;padding-left:14px}}details{{margin:20px 0}}code{{font-size:14px}}
</style><main><h1>Effective BV: Figures 4-6</h1>
<p class="lead">Independent effective coefficients; one empirical fitting form. Full-cohort fits and affected examples have been reoptimized.</p>
<p>j = j<sub>0</sub>[exp(&alpha;<sub>c</sub>F&eta;<sub>*</sub>/RT) &minus; exp(&minus;&alpha;<sub>a</sub>F&eta;<sub>*</sub>/RT)],
&eta;<sub>*</sub> = |&eta;| &minus; jR<sub>app</sub>. Current denotes the positive cathodic magnitude.</p>
<h2>Figure 4 | Describing the polarization curves</h2>{table(pop)}
<img src="assets/population.png" alt="Population fit metrics and parameter distributions">
<img src="assets/population_examples.png" alt="Refitted PtC, N-Ni and WO3 examples">
<p><a href="figure4/EXAMPLE_METRICS.csv">Example metrics</a> &middot; <a href="figure4/PARAMETER_SUMMARY.csv">Parameter summary</a> &middot;
<a href="figure4/FITS.csv">All 6,066 fitted models</a></p>
<h2>Figure 5 | Origins of the additional response</h2>{table(nimo[["model","n","free_parameters","RMSE_mV","R2"]])}
<img src="figure5/nimo/Figure5C_NiMo_comparison.png" alt="NiMo empirical and VHT refits with predicted coverage">
<p>NiMo BV now also exceeds R<sup>2</sup> = 0.99. Adding jR reduces voltage RMSE from 2.10 to 0.43 mV;
held-out RMSE is 2.14 versus 0.44 mV. The comparison is an error reduction, not a pass/fail distinction.</p>
<img src="assets/example_trends.png" alt="Cycle resistance and NiFeP current scaling">
<h3>NiFeP layer-number comparison</h3>
{table(nifep_display)}
<p>Both models use the same 61 retained points. Shared fits use current divided by layer number;
their single parameter set describes all three curves. Geometric R<sub>app</sub> equals the
layer-normalized resistance coefficient divided by N, so no single geometric value is listed for the shared fit.</p>
<p><a href="figure5/D_NIFEP_MODEL_COMPARISON.csv">NiFeP model metrics and parameters</a> &middot;
<a href="figure5/D_NIFEP_PREDICTIONS.csv">NiFeP observed and predicted points</a></p>
<p>The cycle-dependent resistance trend has R<sup>2</sup> = {trends['B']['trend_r2']:.4f}.
The NiFeP inverse-layer coefficient is {trends['D_NiFeP']['inverse_layer_slope']:.3f} &Omega; cm<sup>2</sup> layer.
Compensation accounting and KSCN predictions were recalculated without changing their models.</p>
<p><a href="figure5/RESULTS.json">All example results</a> &middot; <a href="figure5/nimo/C_NIMO_REPORT.json">NiMo controls and fit provenance</a></p>
<h2>Figure 6 | Shared response shapes and kinetic reconstruction</h2>
{table(pd.DataFrame(empirical)[['condition','total','insufficient','linear','nonlinear','families','covered']])}
<img src="assets/templates.png" alt="Four acidic and four alkaline templates with their members">
<p>Four templates cover 59/73 acidic and 188/234 alkaline nonlinear responses. Current amplitudes have been reoptimized;
the template library comes from the completed variable-coefficient finite-grid search.</p>
{table(mainkin[['condition','model','pooled_rmse_mV','worst_rmse_mV','cap','raw_members','raw_pass']])}
<p>Adsorption-energy variation reconstructs the acid families. The alkaline families additionally vary T/V.</p>
<img src="assets/rate_control.png" alt="Recomputed rate control of the main acid and alkaline VHT models">
<details><summary>Additional VHT sharing models and optimization records</summary>{table(kin)}
<p><code>selected_stage=seed</code> retains a previously optimized solution after the new search failed to improve it;
it is not a newly converged optimization. All retained predictions and raw-curve replays were independently recalculated.</p></details>
<p><a href="figure6/KINETIC_PARAMETERS.csv">VHT parameters</a> &middot; <a href="figure6/RAW_VHT_REPLAY.csv">Raw-curve replay</a> &middot;
<a href="figure6/RATE_CONTROL.csv">Rate control and coverage</a></p>
<h2>Scope</h2><p>These are numerical diagnostics, not replacement publication layouts.
The manuscript figures are updated separately, preserving their finalized plot types:
<a href="../../figures/manuscript/Figure4.svg">Figure 4</a>,
<a href="../../figures/manuscript/Figure5.svg">Figure 5</a>,
<a href="../../figures/manuscript/Figure6.svg">Figure 6</a>.
Generating this report does not edit the manuscript or its artwork.</p>
<p>Effective-BV form: <a href="https://doi.org/10.1039/D1CP04134G">Prats and Chan, PCCP (2021)</a>.
For numerical bounds and execution details, see <a href="SUMMARY.md">the summary</a>.</p></main></html>"""
    (output/"index.html").write_text(markup,encoding="utf-8")
    print(output/"index.html")
