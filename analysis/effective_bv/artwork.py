"""Update data artists in the manually finalized manuscript SVGs.

The compressed templates preserve the edited fonts, frames, positions and plot
types. This module changes data geometry, numerical labels and family membership,
not the overall figure composition. Inkscape is needed only for export.
"""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

from lxml import etree as E
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "analysis/common"))
import effective_bv as bv

S = "{http://www.w3.org/2000/svg}"
X = "{http://www.w3.org/1999/xlink}href"
COLORS = ["#177db0", "#d34259", "#168f78", "#8662af"]
STEP = {"V": COLORS[0], "H": COLORS[2], "T": COLORS[1]}
MAIN = {"acid": "DeltaG_only", "KOH": "DeltaG_T"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return pd.read_csv(path, float_precision="round_trip")


def byid(root, name):
    found = [n for n in root.iter() if n.get("id") == name]
    assert len(found) == 1, (name, len(found))
    return found[0]


def txt(node):
    return "".join(node.itertext()).strip()


def leaf_text(node, value):
    texts = list(node.iter(S + "text"))
    assert len(texts) == 1 and len(texts[0]) == 0, node.get("id")
    texts[0].text = str(value)
    return texts[0]


def glyph_replace(node, old, new):
    """Change a same-width numeric string without disturbing math-text glyphs."""
    spans = [s for s in node.iter(S + "tspan") if s.text]
    value = "".join(s.text for s in spans)
    assert len(old) == len(new) and value.count(old) == 1, (old, new, value)
    first = value.index(old)
    at = 0
    for span in spans:
        end = at + len(span.text)
        if first < end and first + len(old) > at:
            chars = list(span.text)
            for j in range(len(chars)):
                if first <= at+j < first+len(old):
                    chars[j] = new[at+j-first]
            span.text = "".join(chars)
        at = end


def path_string(x, y, closed=False):
    assert len(x) == len(y) and len(x) > 0
    assert np.isfinite(x).all() and np.isfinite(y).all()
    return "M " + " L ".join(f"{a:.7g} {b:.7g}" for a, b in zip(x, y)) + (" Z" if closed else "")


class Axis:
    """Map current data to the original axis coordinates, using its tick marks."""
    def __init__(self, root, name, logx=False, logy=False):
        self.root, self.node = root, byid(root, name)
        self.logx, self.logy = logx, logy
        self.maps = []
        for axis, log in [("x", logx), ("y", logy)]:
            values, positions = [], []
            for n in self.node.iter(S + "g"):
                if not re.search(r"(?:^|[-_])" + axis + r"tick_\d+$", n.get("id", "")):
                    continue
                use = next(n.iter(S + "use"), None)
                text = next(n.iter(S + "text"), None)
                if use is None or text is None:
                    continue
                label = re.sub(r"\s+", "", txt(text)).replace("\u2212", "-")
                try:
                    if label in ['BV','BV+jR']:
                        value = ['BV','BV+jR'].index(label)
                    elif log:
                        value = float(label[2:]) if label.startswith("10") and len(label) > 2 else np.log10(float(label))
                    else:
                        value = float(label)
                except ValueError:
                    continue
                values.append(value)
                positions.append(float(use.get(axis)))
            assert len(values) >= 2, (name, axis, values)
            coef = np.polyfit(values, positions, 1)
            assert np.max(np.abs(np.polyval(coef, values)-positions)) < .002, (name, axis)
            self.maps.append(coef)
        clips = [n.get("clip-path") for n in self.node.iter() if n.get("clip-path")]
        assert clips, name
        clip = byid(root, re.search(r"url\(#([^)]*)\)", clips[0])[1])
        rect = next(clip.iter(S+"rect"))
        self.bounds = tuple(float(rect.get(k)) for k in ("x", "y", "width", "height"))
        self.clip = clips[0]
        self.artists = E.Element(S+"g", id="updated-data-"+name)
        self.artists.set("clip-path", self.clip)
        self.node.append(self.artists)

    def xy(self, x, y):
        x, y = np.atleast_1d(x).astype(float), np.atleast_1d(y).astype(float)
        if self.logx:
            x = np.log10(x)
        if self.logy:
            y = np.log10(y)
        return np.polyval(self.maps[0], x), np.polyval(self.maps[1], y)

    def remove(self, predicate):
        for child in list(self.node):
            if predicate(child.get("id", "")):
                self.node.remove(child)

    def line(self, x, y, color, width=1.5, dash=None, alpha=1, name=None):
        x, y = self.xy(x, y)
        a = {"d": path_string(x, y), "fill": "none", "stroke": color,
             "stroke-width": str(width), "stroke-linejoin": "round"}
        if dash:
            a["stroke-dasharray"] = dash
        if alpha != 1:
            a["opacity"] = str(alpha)
        if name:
            a["id"] = name
        return E.SubElement(self.artists, S+"path", a)

    def polygon(self, x, y, color, alpha=1, stroke="none", width=.5):
        x, y = self.xy(x, y)
        return E.SubElement(self.artists, S+"path", {"d": path_string(x, y, True),
            "fill": color, "fill-opacity": str(alpha), "stroke": stroke, "stroke-width": str(width)})

    def scatter(self, x, y, color, size=1.5, fill="white", alpha=1, square=False, width=.6):
        x, y = self.xy(x, y)
        group = E.SubElement(self.artists, S+"g", {"stroke": color, "fill": fill,
            "stroke-width": str(width), "opacity": str(alpha)})
        for a, b in zip(x, y):
            attrs = {"x": str(a-size), "y": str(b-size), "width": str(2*size), "height": str(2*size)} if square else {"cx": str(a), "cy": str(b), "r": str(size)}
            E.SubElement(group, S+("rect" if square else "circle"), attrs)

    def text(self, x, y, value, color="black", size=13, dx=0, dy=0, anchor="start"):
        x, y = self.xy(x, y)
        t = E.SubElement(self.node, S+"text", {"x": str(x[0]+dx), "y": str(y[0]+dy),
            "style": f"font-family:Arial;font-weight:700;font-size:{size}px;fill:{color};text-anchor:{anchor}"})
        t.text = value
        return t

    def replace_line(self, identity, x, y):
        group = byid(self.root, identity)
        paths = [n for n in group.iter(S+"path") if n.get("clip-path")]
        assert len(paths) == 1, identity
        x, y = self.xy(x, y)
        paths[0].set("d", path_string(x, y))

    def move_marker(self, identity, x, y):
        group = byid(self.root, identity)
        use = list(group.iter(S+"use"))
        assert len(use) == 1, identity
        x, y = self.xy(x, y)
        use[0].set("x", str(x[0]))
        use[0].set("y", str(y[0]))


def figure1(root, data):
    """Use the same alkaline members, normalization and VHT model as Figure 6."""
    points = read(data/'figure6/KOH/POINT_PREDICTIONS.csv')
    points = points[points.adequate].copy()
    replay = read(data/'figure6/RAW_VHT_REPLAY.csv')
    replay = replay[replay.condition.eq('KOH') & replay.model.eq(MAIN['KOH'])]
    amplitudes = replay.set_index('curve_uid').amplitude_multiplier
    points['scaled_j'] = points.x/points.curve_uid.map(amplitudes)
    assert np.isfinite(points.scaled_j).all() and (points.scaled_j > 0).all()
    curves = read(data/'figure6/TEMPLATE_RECONSTRUCTION.csv')
    curves = curves[curves.condition.eq('KOH') & curves.model.eq(MAIN['KOH'])]
    parameters = read(data/'figure6/KINETIC_PARAMETERS.csv')
    parameters = parameters[parameters.condition.eq('KOH') & parameters.model.eq(MAIN['KOH'])]
    families = sorted(parameters.family)
    assert families == ['B1', 'B2', 'B3', 'B4']
    members = points.groupby('family').curve_uid.nunique().to_dict()
    assert sum(members.values()) == points.curve_uid.nunique() == 188
    for stage, column in [('raw', 'j_mA_cm2'), ('scaled', 'scaled_j')]:
        layer = byid(root, 'D-'+stage+'-data')
        # Retain the hand-edited placement and the existing plotting bounds.
        box = next(layer.iter(S+'clipPath')).find(S+'rect')
        left, top, width, height = (float(box.get(k)) for k in ['x', 'y', 'width', 'height'])
        for child in list(layer):
            layer.remove(child)
        layer.set('data-curves', str(points.curve_uid.nunique()))
        layer.set('data-points', str(len(points)))
        layer.set('data-filter', 'effective_BV_template_R2 >= 0.99')
        layer.set('data-condition', 'KOH')
        layer.set('data-families', ','.join(families))
        defs = E.SubElement(layer, S+'defs')
        clip_id = 'D-current-'+stage+'-clip'
        clip = E.SubElement(defs, S+'clipPath', id=clip_id)
        E.SubElement(clip, S+'rect', x=str(left), y=str(top), width=str(width), height=str(height))
        artists = E.SubElement(layer, S+'g', {'clip-path': 'url(#'+clip_id+')'})
        def xy(eta, j):
            return left+np.asarray(eta)*width/300, top+height-(np.log10(j)+1.5)*height/4.5
        for i, family in enumerate(families):
            own = points[points.family.eq(family)]
            if stage == 'raw':
                for index, (uid, curve) in enumerate(own.groupby('curve_uid')):
                    curve = curve.sort_values('fit_point_index')
                    x, y = xy(curve.eta_mV, curve[column])
                    E.SubElement(artists, S+'path', {'id': f'D-current-raw-{family}-{index}',
                        'data-curve-uid': uid, 'data-family': family, 'd': path_string(x, y),
                        'fill': 'none', 'stroke': COLORS[i], 'stroke-width': '1.05', 'stroke-opacity': '.36'})
            else:
                scatter = E.SubElement(artists, S+'g', {'id': 'D-current-points-'+family,
                    'fill': 'none', 'stroke': COLORS[i], 'stroke-width': '.45', 'stroke-opacity': '.18'})
                x, y = xy(own.eta_mV, own[column])
                for a, b in zip(x, y):
                    E.SubElement(scatter, S+'circle', cx=f'{a:.7g}', cy=f'{b:.7g}', r='1.414214')
                grid = curves[curves.family.eq(family)].sort_values('vht_eta_mV')
                x, y = xy(grid.vht_eta_mV, grid.x)
                E.SubElement(artists, S+'path', {'id': 'D-current-shape-'+family,
                    'data-family': family, 'd': path_string(x, y), 'fill': 'none',
                    'stroke': COLORS[i], 'stroke-width': '2.6'})
    legend = byid(root, 'D-family-legend')
    fifth = byid(root, 'D-legend-B5')
    legend.remove(fifth.getprevious())
    legend.remove(fifth)
    # Center four entries in the original five-entry span without scaling text.
    for child in legend:
        child.set('transform', 'translate(30,0)')
    kinetic = byid(root, 'D-kinetic-data')
    for name in ['D-kinetic-point-B5', 'D-kinetic-family-B5']:
        kinetic.remove(byid(root, name))
    for row in parameters.itertuples():
        x = 1350+(row.DeltaG_eff_meV-10)*388/75
        y = 460-np.log10(row.kT_over_kV/2)*220
        assert 1350 < x < 1748 and 230 < y < 460
        point = byid(root, 'D-kinetic-point-'+row.family)
        point.set('x', str(x-5)); point.set('y', str(y-5))
        point.set('data-DeltaG-eff-meV', str(row.DeltaG_eff_meV))
        point.set('data-kT-over-kV', str(row.kT_over_kV))
        label = byid(root, 'D-kinetic-family-'+row.family)
        label.set('x', str(x+12)); label.set('y', str(y-10))
    desc = root.find(S+'desc')
    if desc is None:
        desc = E.Element(S+'desc'); root.insert(0, desc)
    desc.text = ('Figure 1. Extraction, empirical response analysis and kinetic reconstruction. '
        'Panels A-C retain the finalized schematic artwork. BV in C denotes the effective '
        'BV form with independently fitted anodic and cathodic coefficients; the displayed '
        'additive-voltage expression does not impose a fixed coefficient sum. '
        'Panel D illustrates the four alkaline families B1-B4 from Figure 6, with 188 '
        'member curves, the same current-amplitude normalization, VHT reconstruction and '
        'DeltaG/T-to-V coordinates. Numbers 1-4 correspond to B1-B4. '
        'These are selected responses from the 348-curve acidic and alkaline population, '
        'not an assignment of all 348 curves to four families.')
    return {'condition': 'KOH', 'families': families, 'members': members,
        'curves': int(points.curve_uid.nunique()), 'points': len(points),
        'normalization': 'j / (beta * amplitude_multiplier), identical to Figure 6B',
        'shape_lines': 'VHT reconstruction, identical to Figure 6B',
        'parameters': parameters[['family', 'DeltaG_eff_meV', 'kT_over_kV']].to_dict('records'),
        'unchanged_panels': ['A', 'B', 'C']}


def figure4(root, data):
    fits = read(data/"figure4/FITS.csv")
    checks = {}
    for name, key, start, bandwidth in [("R2", "r2", 8, .012), ("RMSE", "rmse", 49, .18)]:
        ax = Axis(root, "fit_"+name+"_axes_1", logy=(name == "RMSE"))
        ax.remove(lambda n: n.startswith("fit_"+name+"_FillBetween") or n in {f"fit_{name}_line2d_{i}" for i in range(start, start+6)})
        for center, model, color in [(0, "BV", "#1464ee"), (1, "BV+jR", "#ed2338")]:
            v = fits.loc[fits.model.eq(model), key].to_numpy()
            z = np.log10(v) if name == "RMSE" else v
            grid = np.linspace(-2, 3, 500) if name == "RMSE" else np.linspace(.8, 1, 500)
            density = gaussian_kde(z, bw_method=bandwidth/np.std(z, ddof=1))(grid)
            w = .36*density/density.max()
            ys = 10**grid if name == "RMSE" else grid
            ax.polygon(np.r_[center-w, (center+w)[::-1]], np.r_[ys, ys[::-1]], color, .42, color, .45)
            q05, q25, median, q75, q95 = np.quantile(v, [.05, .25, .5, .75, .95])
            ax.line([center]*2, [q05,q95], "black", 1.1)
            ax.line([center]*2, [q25,q75], "black", 4)
            ax.line([center-.16,center+.16], [median]*2, "black", 1.8)
        if name == "R2":
            glyph_replace(byid(root,"fit_R2_text_9"), "42", str(int(((fits.model=="BV")&(fits.r2<.8)).sum())))
    for model, patch, textid, countid, y0, y1 in [
        ("BV",4,7,8,37.728,59.652),("BV+jR",6,9,10,89.928,111.852)]:
        count = int(((fits.model==model)&(fits.r2>=.99)).sum())
        percent = 100*count/3033
        p = next(byid(root,f"fit_fraction_patch_{patch}").iter(S+"path"))
        x0,x1 = 52.488,52.488+227.448*percent/100
        p.set("d",path_string([x0,x1,x1,x0],[y1,y1,y0,y0],True))
        t = leaf_text(byid(root,f"fit_fraction_text_{textid}"),f"{percent:.1f}%")
        t.set("x",str((x0+x1)/2))
        leaf_text(byid(root,f"fit_fraction_text_{countid}"),f"{count:,} curves")
        checks[model] = {"accepted":count,"percent":percent}
    accepted = fits[fits.model.eq("BV+jR")&fits.r2.ge(.99)]
    bins = read(data/"figure4/PARAMETER_HISTOGRAMS.csv")
    for i,col,color,last in [(1,"b_mV_dec","#087fea",42),(2,"R","#e32649",52),(3,"j0","#168568",46)]:
        ax = Axis(root,f"parameter{i}_axes_1",logx=i==3)
        ax.remove(lambda n: n in {f"parameter{i}_patch_{j}" for j in range(3,last+1)} or n.startswith(f"parameter{i}_line2d_"))
        g = bins[bins.parameter.eq(col)]
        for r in g.itertuples():
            ax.polygon([r.left,r.right,r.right,r.left],[0,0,r.percent,r.percent],color,stroke="white",width=.4)
        median = float(accepted[col].median())
        x,y,w,h = ax.bounds
        ymax = (y-ax.maps[1][1])/ax.maps[1][0]
        assert g.percent.max() < ymax, (col,g.percent.max(),ymax)
        ax.line([median]*2,[0,ymax],"black",1.2,"4,3")
        for t in ax.node.iter(S+"text"):
            if (t.text or "").startswith("Median ="):
                t.text = f"Median = {median:.3g}"
        checks[col] = {"median":median,"histogram_count":int(g['count'].sum()),"denominator":len(accepted)}
    examples = read(data/"figure4/EXAMPLE_CURVES.csv")
    for index,label in [(1,"20 wt% Pt/C"),(2,"N-Ni"),(4,"WO3")]:
        ax = Axis(root,f"case{index}_axes_1")
        group = examples[examples.display_label.eq(label)]
        own = fits[fits.curve_uid.eq(group.curve_uid.iloc[0])].set_index("model")
        j = np.geomspace(max(.001,group.j.min()*.2),group.j.max(),350)
        for model,line,textid,old in [("BV+jR",8,11,{1:"0.9996",2:"0.9982",4:"0.9639"}[index]),
                                     ("BV",9,10,{1:"0.9342",2:"0.9982",4:"0.9639"}[index])]:
            ax.replace_line(f"case{index}_line2d_{line}",bv.predict(j,own.loc[model]),j)
            glyph_replace(byid(root,f"case{index}_text_{textid}"),old,f"{own.loc[model,'r2']:.4f}")
    root.find(S+"desc").text = "Figure 4. Effective BV and BV+jR fitted to 3,033 curves from 473 papers. Independently fitted anodic and cathodic coefficients; no voltage offset. Panel A contains unchanged observed local slopes. Panel B uses all curves for fit statistics and 2,361 adequate BV+jR fits for parameter distributions. Manually finalized plot types and composition retained."
    return checks


def move_annotation(root, identity, ax, x, y, dx, dy):
    node = byid(root,identity)
    text = next(node.iter(S+"text"))
    assert len(text) == 0
    xx,yy = ax.xy(x,y)
    text.set("x",str(xx[0]+dx));text.set("y",str(yy[0]+dy))
    text.attrib.pop("transform",None)


def figure5(root, data):
    results = json.loads((data/"figure5/RESULTS.json").read_text())
    fits = read(data/"figure5/B_FITS.csv")
    points = read(data/"figure5/B_PREDICTIONS.csv")
    ax = Axis(root,"B_experiment_axes_1")
    for cycle in range(1,6):
        p = points[(points.cycle==cycle)&points.model.eq("BV+jR")]
        fit = fits[(fits.cycle==cycle)&fits.model.eq("BV+jR")].iloc[0]
        j = np.linspace(p.j_mA_cm2.min(),p.j_mA_cm2.max(),300)
        ax.replace_line(f"B_experiment_line2d_{8+2*(cycle-1)}",bv.predict(j,fit),j)
    ax = Axis(root,"B_consequence_axes_1")
    cycles = read(data/"figure5/B_CYCLE_R.csv")
    x = np.linspace(cycles.Rs_EIS_ohm.min()-.3,cycles.Rs_EIS_ohm.max()+.3,120)
    ax.replace_line("B_consequence_resistance_linear_fit",x,results['B']['trend_slope']*x+results['B']['trend_intercept'])
    for r in cycles.itertuples():
        ax.move_marker(f"B_consequence_line2d_{8+r.cycle}",r.Rs_EIS_ohm,r.R_BVjR_ohm_cm2)
        move_annotation(root,f"B_consequence_text_{10+r.cycle}",ax,r.Rs_EIS_ohm,r.R_BVjR_ohm_cm2,6,-5 if r.cycle==5 else 10)
    nimo = data/"figure5/nimo"
    lines,coverage = read(nimo/"C_NIMO_FIT_LINES.csv"),read(nimo/"C_NIMO_PREDICTED_COVERAGE.csv")
    report = json.loads((nimo/"C_NIMO_REPORT.json").read_text())
    metrics = {r['model']:r['RMSE_mV'] for r in report['metrics']}
    ax = Axis(root,"nimo_svg667_axes_1")
    for model,line in [("BV",11),("BV+jR",12)]:
        ax.replace_line(f"nimo_svg667_line2d_{line}",lines[model+"_eta_mV"],lines.j_mA_cm2)
    for t in ax.node.iter(S+"text"):
        if (t.text or "").startswith("BV:"):
            t.text = f"BV: {metrics['BV']:.2f} mV"
        elif (t.text or "").startswith("BV + jR:"):
            t.text = f"BV + jR: {metrics['BV+jR']:.2f} mV"
    glyph_replace(byid(root,'nimo_svg667_text_14'),'1.25',f"{report['empirical_fits']['BV+jR']['R']:.2f}")
    ax = Axis(root,"nimo_svg733_axes_1")
    ax.replace_line("nimo_svg733_line2d_8",lines.VHT_eta_mV,lines.j_mA_cm2)
    for t in ax.node.iter(S+'text'):
        if (t.text or '').endswith(' mV'):
            t.text = f"{metrics['VHT']:.2f} mV"
    ax = Axis(root,"nimo_svg733_axes_2")
    ax.replace_line("nimo_svg733_line2d_19",coverage.eta_mV,coverage.theta)
    ax.replace_line("nimo_svg733_line2d_20",coverage.eta_mV,coverage.theta_mirror)
    layerfits = read(data/"figure5/D_NIFEP_FITS.csv")
    ax = Axis(root,"D_consequences_axes_1")
    x = np.linspace(0,1/12,100)
    ax.replace_line("D_consequences_line2d_8",x,results['D_NiFeP']['inverse_layer_slope']*x)
    for i,r in enumerate(layerfits.sort_values('layers').itertuples()):
        ax.move_marker(f"D_consequences_line2d_{9+i}",1/r.layers,r.independent_R)
        move_annotation(root,f"D_consequences_text_{10+i}",ax,1/r.layers,r.independent_R,5,-5)
    root.find(S+"desc").text = "Figure 5. Electrical compensation, cycle-dependent CV/EIS, surface kinetics and current rescaling. All BV and BV+jR fits use independent effective coefficients. NiMo voltage RMSE: BV 2.096, BV+jR 0.427, resistance-free VHT 0.661 mV, fitted to the same 40 points. Both coverage solutions are calculated, not measured. Original composition and experimental observations retained."
    return {"nimo_metrics":report['metrics'],"cycle_trend_r2":results['B']['trend_r2'],
            "NiFeP_inverse_layer_slope":results['D_NiFeP']['inverse_layer_slope']}


def crossings(frame, condition, family, mean=False):
    suffix = "_mean" if mean else ""
    rows = frame.sort_values("eta_mV").to_dict("records")
    out = []
    for p,q in zip(rows,rows[1:]):
        for a,b in itertools.combinations("TVH",2):
            d0,d1 = p['X_'+a+suffix]-p['X_'+b+suffix],q['X_'+a+suffix]-q['X_'+b+suffix]
            if d0*d1>0 or d0==d1:
                continue
            f = d0/(d0-d1)
            v = {s:p['X_'+s+suffix]+f*(q['X_'+s+suffix]-p['X_'+s+suffix]) for s in 'VHT'}
            if v[a] >= max(v.values())-1e-10:
                out.append(dict(condition=condition,family=family,pair=f"X_{a}=X_{b}",
                    eta_mV=p['eta_mV']+f*(q['eta_mV']-p['eta_mV']),control=v[a],
                    within_fitted_support=True,dominant_control_crossing=True))
    return out


def control_artists(ax, frame, condition, family, mean=False):
    x = frame.eta_mV.to_numpy()
    for s in "VHT":
        y = frame['X_'+s+('_mean' if mean else '')].to_numpy()
        if mean:
            sd = frame['X_'+s+'_sd'].to_numpy()
            ax.polygon(np.r_[x,x[::-1]],np.r_[y-sd,(y+sd)[::-1]],STEP[s],.14)
        ax.line(x,y,STEP[s],2.4 if mean else 1.9,'8,4' if s=='H' else None)
    found = crossings(frame,condition,family,mean)
    for r in found:
        ax.line([r['eta_mV']]*2,[0,r['control']],"black",.8,"1,1.5")
        ax.scatter([r['eta_mV']],[r['control']],"black",3.2,width=1.1)
    return found


def figure6(root,data,output):
    for n in root.iter('{http://purl.org/dc/elements/1.1/}description'):
        n.text = 'Figure 6. Effective-BV templates: four acidic and four alkaline families, covering 59/73 and 188/234 nonlinear curves. VHT reconstruction uses DeltaG variation in acid and DeltaG plus T/V variation in KOH. Original manually finalized composition retained; data updated 2026-09-27.'
    templates = {c:read(data/f"figure6/{c}/TEMPLATES.csv") for c in MAIN}
    replay = read(data/"figure6/RAW_VHT_REPLAY.csv")
    reconstruction = read(data/"figure6/TEMPLATE_RECONSTRUCTION.csv")
    parameters = read(data/"figure6/KINETIC_PARAMETERS.csv")
    parameters = pd.concat([parameters[parameters.condition.eq(c)&parameters.model.eq(m)] for c,m in MAIN.items()])
    for c,model in MAIN.items():
        points = read(data/f"figure6/{c}/POINT_PREDICTIONS.csv")
        points = points[points.adequate].copy()
        amps = replay[replay.condition.eq(c)&replay.model.eq(model)].set_index('curve_uid').amplitude_multiplier
        points['vht_x'] = points.x/points.curve_uid.map(amps)
        assert points.vht_x.notna().all()
        for stage in ['raw','vht']:
            ax = Axis(root,f"axes-{c}-{stage}",logy=True)
            ax.remove(lambda n:n.startswith(('raw-curve-','points-','vht-model-')))
            for i,r in enumerate(templates[c].itertuples()):
                g = points[points.family.eq(r.family)]
                column = 'j_mA_cm2' if stage=='raw' else 'vht_x'
                if stage=='raw':
                    for _,curve in g.groupby('curve_uid'):
                        curve = curve.sort_values('fit_point_index')
                        ax.line(curve.eta_mV,curve[column],COLORS[i],.45,alpha=.40)
                ax.scatter(g.eta_mV,g[column],COLORS[i],1.32,fill='none',width=.45,alpha=.30)
                if stage=='vht':
                    grid = reconstruction[reconstruction.condition.eq(c)&reconstruction.model.eq(model)&reconstruction.family.eq(r.family)]
                    ax.line(grid.vht_eta_mV,grid.x,COLORS[i],2.0)
        legend = byid(root,'legend-families-'+c)
        children = list(legend)
        assert len(children)==(12 if c=='acid' else 15)
        for i,n in enumerate(templates[c].n_curves):
            leaf_text(children[3*i+2],f"(n={n})")
        if c=='KOH':
            for child in children[12:]:
                legend.remove(child)
            legend.set('transform','translate(46.635625,0)')
    coverage = Axis(root,'axes-coverage')
    coverage.remove(lambda n:n.startswith('coverage-') and n!='coverage-target' or n in ['patch_17','patch_18','text_58','text_59'])
    coverage_records = []
    for c,offset,color,den,count in [('acid',-.2,COLORS[0],73,59),('KOH',.2,'#c38218',234,188)]:
        scan = read(data/f'figure6/{c}/COVERAGE_SCAN.csv')
        for r in scan.itertuples():
            k = int(r.K)
            y = 100*r.covered/den
            coverage.polygon([k+offset-.18,k+offset+.18,k+offset+.18,k+offset-.18],[0,0,y,y],color,
                1 if k==4 else .42,'black' if k==4 else 'none',1.1)
            coverage_records.append(dict(condition=c,K=k,coverage_percent=y,selected=k==4,denominator=den))
        x,y = 4+offset,100*count/den
        tx = 2.9 if c=='acid' else 5.5
        coverage.line([tx,x],[105,y+2],'black',.75)
        coverage.text(tx,109,f'{count}/{den}',size=11.5,anchor='middle')
    empirical,kinetic = Axis(root,'axes-empirical',logx=True),Axis(root,'axes-kinetic')
    for ax in [empirical,kinetic]:
        ax.remove(lambda n:n.startswith('PathCollection_') or re.fullmatch(r'text_(6[89]|7[0-6]|8[5-9]|9[0-3])',n) is not None)
    reference = parameters[parameters.condition.eq('acid')].kT_over_kV.iloc[0]
    coords = []
    for c in MAIN:
        for i,r in enumerate(templates[c].itertuples()):
            p = parameters[parameters.condition.eq(c)&parameters.family.eq(r.family)].iloc[0]
            color = COLORS[i]
            empirical.scatter([r.Q_mV],[r.b_mV_dec],'white',3.28,color,square=c=='KOH',width=.5)
            empirical.text(r.Q_mV,r.b_mV_dec,r.family,color,13,dx=0 if c=='acid' else 6,dy=16 if c=='acid' else -7,anchor='middle' if c=='acid' else 'start')
            y = np.log10(p.kT_over_kV/reference)
            kinetic.scatter([p.DeltaG_eff_meV],[y],'white',3.28,color,square=c=='KOH',width=.5)
            kinetic.text(p.DeltaG_eff_meV,y,r.family,color,13,dx=5,dy=-6)
            coords.append(dict(condition=c,family=r.family,source_family=r.family,Q_mV=r.Q_mV,
                b_BV_mV_dec=r.b_mV_dec,alpha_c=r.alpha_c,alpha_a=r.alpha_a,
                DeltaG_eff_meV=p.DeltaG_eff_meV,kT_over_kV=p.kT_over_kV,
                acid_reference_kT_over_kV=reference,log10_relative_TV=y))
    means,controls = read(data/'figure6/RATE_CONTROL_MEAN_SD.csv'),read(data/'figure6/RATE_CONTROL.csv')
    all_crossings = []
    for c in MAIN:
        ax = Axis(root,'axes-control-'+c)
        ax.remove(lambda n:n.startswith(('band-','control-'+c+'-','crossing-')))
        selected = means[means.condition.eq(c)&means.all_families_supported]
        all_crossings.extend(control_artists(ax,selected,c,'mean',True))
    # Four alkaline families occupy the same four-column grid as the acid row.
    # Copying its axis furniture preserves label sizes (no horizontal stretching).
    for i in range(1,6):
        old = byid(root,f'axes-family-control-KOH-K{i}')
        title = byid(root,f'family-title-KOH-K{i}')
        if i==5:
            old.getparent().remove(old);title.getparent().remove(title)
            continue
        template = copy.deepcopy(byid(root,f'axes-family-control-acid-A{i}'))
        idmap = {n.get('id'):'koh4-'+n.get('id') for n in template.iter() if n.get('id')}
        for n in template.iter():
            if n.get('id'):
                n.set('id',idmap[n.get('id')])
            for key,value in list(n.attrib.items()):
                if key==X and value[1:] in idmap:
                    n.set(key,'#'+idmap[value[1:]])
                if 'url(#' in value:
                    n.set(key,re.sub(r'url\(#([^)]*)\)',lambda m:'url(#'+idmap.get(m[1],m[1])+')',value))
        template.set('id',f'axes-family-control-KOH-B{i}')
        template.set('transform','translate(0,242.4)')
        for tick in template.iter(S+'g'):
            if re.search(r'xtick_\d+$',tick.get('id','')):
                t = next(tick.iter(S+'text'),None)
                if t is not None and t.text in ['100','200']:
                    t.text = {'100':'150','200':'300'}[t.text]
        parent=old.getparent();parent.replace(old,template)
        t = next(title.iter(S+'text'))
        top = next(byid(root,f'family-title-acid-A{i}').iter(S+'text'))
        t.set('x',top.get('x'));t.attrib.pop('transform',None)
    for c in MAIN:
        for i in range(1,5):
            family = ('A' if c=='acid' else 'B')+str(i)
            ax = Axis(root,f'axes-family-control-{c}-{family}')
            ax.remove(lambda n:'family-control-' in n and not n.startswith('updated-data-') or 'family-crossing-' in n)
            g = controls[controls.condition.eq(c)&controls.family.eq(family)&controls.inside_fitted_support]
            all_crossings.extend(control_artists(ax,g,c,family))
    # Add explicit denominators to the audit tables, retaining the original CSV schema.
    for c in MAIN:
        own = controls[controls.condition.eq(c)]
        mask = means.condition.eq(c)
        means.loc[mask,'n_families'] = 4
        means.loc[mask,'n_families_supported'] = means.loc[mask,'eta_mV'].map(own.groupby('eta_mV').inside_fitted_support.sum())
    means[['n_families','n_families_supported']] = means[['n_families','n_families_supported']].astype(int)
    tables = {'COVERAGE_BARS':pd.DataFrame(coverage_records),'PARAMETER_COORDINATES':pd.DataFrame(coords),
        'RATE_CONTROL_MEAN_SD':means,'RATE_CONTROL_FAMILY_GRID':controls,'CONTROL_CROSSINGS':pd.DataFrame(all_crossings),
        'MEAN_CONTROL_CROSSINGS':pd.DataFrame([r for r in all_crossings if r['family']=='mean'])}
    tables_dir=output/'figure6_tables';tables_dir.mkdir(exist_ok=True)
    for name,frame in tables.items():
        frame.to_csv(tables_dir/(name+'.csv'),index=False,lineterminator='\n')
    return {'families':{'acid':4,'KOH':4},'members':{'acid':59,'KOH':188},
            'crossings':all_crossings,'acid_TV_reference':reference}


def protected_checks(before,after,figure):
    names = {1:['svg1','D-frame','D-panel-title','D-raw-title','D-scaled-title','D-kinetic-title',
                'D-raw-axes','D-scaled-axes','D-kinetic-axes','D-amplitude-shape-equation','D-stage-connectors'],
             4:['frame_A','svg84','frame_B','B-bottom-titles-compact'],
             5:['svg171','svg261','B_experiment_axes_2','D_measured_axes_1','D_measured_axes_2','D_consequences_axes_2'],
             6:['frame-A','frame-B','frame-C','frame-D','frame-E','frame-F','heading-A','heading-B','heading-C','heading-D','heading-E','heading-F']}[figure]
    for name in names:
        assert E.tostring(byid(before,name))==E.tostring(byid(after,name)),(figure,name)
    assert before.get('viewBox')==after.get('viewBox')
    return names


def run(data,baseline,output,inkscape):
    assert baseline != output, 'Use a separate review output; do not overwrite the baseline.'
    output.mkdir(parents=True,exist_ok=True)
    archive=HERE/'artwork_templates.zip'
    if not archive.exists():
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for i in [1,4,5,6]:
                z.write(baseline/f'Figure{i}.svg',f'Figure{i}.svg')
    checks={'template_archive_sha256':sha(archive),'data_directory':str(data),
            'plot_types_unchanged':True,'preserved_elements':{},'figures':{},'inputs':{}}
    with zipfile.ZipFile(archive) as z:
        for i,func in [(1,figure1),(4,figure4),(5,figure5),(6,figure6)]:
            root=E.fromstring(z.read(f'Figure{i}.svg'));before=copy.deepcopy(root)
            checks['figures'][str(i)] = func(root,data,output) if i==6 else func(root,data)
            checks['preserved_elements'][str(i)]=protected_checks(before,root,i)
            E.ElementTree(root).write(str(output/f'Figure{i}.svg'),encoding='utf-8',xml_declaration=True)
            if i==1:
                detail=copy.deepcopy(root)
                for identity in ['svg1','rect1']:
                    node=byid(detail,identity);node.getparent().remove(node)
                detail.set('id','Figure1D-effective-bv-20260927')
                detail.set('viewBox','0 1208.226 1800 560')
                detail.set('width','180mm');detail.set('height','56mm')
                (output/'panels').mkdir(exist_ok=True)
                E.ElementTree(detail).write(str(output/'panels/Figure1D.svg'),encoding='utf-8',xml_declaration=True)
    for i in [2,3]:
        for ext in ['svg','png']:
            shutil.copy2(baseline/f'Figure{i}.{ext}',output/f'Figure{i}.{ext}')
    for name in ['Figure1','Figure4','Figure5','Figure6','panels/Figure1D']:
        subprocess.run([inkscape,str(output/f'{name}.svg'),'--export-type=png','--export-background=white',
            '--export-width=3000',f'--export-filename={output/f"{name}.png"}'],check=True,capture_output=True)
    for p in sorted(data.rglob('*.csv')):
        if any(part in ['figure4','figure5','figure6'] for part in p.parts):
            checks['inputs'][p.relative_to(data).as_posix()]=sha(p)
    checks['outputs']={f'Figure{i}.{ext}':sha(output/f'Figure{i}.{ext}') for i in range(1,7) for ext in ['svg','png']}
    checks['standalone_outputs']={f'panels/Figure1D.{ext}':sha(output/f'panels/Figure1D.{ext}') for ext in ['svg','png']}
    (output/'ARTWORK_CHECKS.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    markup='<!doctype html><meta charset="utf-8"><title>Updated manuscript figures</title><style>body{font:16px Arial;max-width:1800px;margin:24px auto;padding:0 24px}img{width:100%;display:block}section{border-top:1px solid #aaa;margin-top:24px}a{color:#005ba8}</style><h1>Figures 1-6 | Updated analysis</h1><p>Manually finalized composition retained. Figures 1D and 4-6 use the effective-BV reanalysis of 27 September 2026.</p>'
    markup += '<nav>'+' | '.join(f'<a href="#Figure{i}">Figure {i}</a>' for i in range(1,7))+'</nav>'
    for i in range(1,7):
        markup += f'<section id="Figure{i}"><h2>Figure {i}</h2><p><a href="Figure{i}.svg">SVG</a> | <a href="Figure{i}.png">PNG</a></p><img src="Figure{i}.png?v={sha(output/f"Figure{i}.png")[:12]}" alt="Figure {i}"></section>'
    (output/'index.html').write_text(markup,encoding='utf-8')
    print(json.dumps({k:v for k,v in checks.items() if k in ['preserved_elements','figures']},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,default=ROOT/'build/effective-bv-20260927')
    p.add_argument('--baseline',type=Path,default=ROOT/'figures/manuscript')
    p.add_argument('--output',type=Path,default=ROOT/'build/manuscript-figures-effective-bv-20260927')
    p.add_argument('--inkscape',default=shutil.which('inkscape') or 'C:/Program Files/Inkscape/bin/inkscape.com')
    a=p.parse_args();run(a.data.resolve(),a.baseline.resolve(),a.output.resolve(),a.inkscape)
