"""Side-by-side: source, Depth Pro 2 (B), DA3-SMALL on the clear Look Rock frame, with
per-ridge depth vs NPS chart distance. Run after depth_dp2.py and depth_da3.py.
Depth Pro 2 weights: research-only (Apple ML Research Model License)."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy.stats import spearmanr

from pluma.regions_lookrock import LANDMARKS, MILE

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "out/depth"
src = np.asarray(Image.open(ROOT / "data/frames/lookrock/grsm_20161120_1200.jpg").convert("RGB"))
names = list(LANDMARKS)
chart_km = np.array([LANDMARKS[n][0] * MILE / 1000 for n in names])
ANCHORS = ["Happy Valley Ridge", "Rich Mtn", "Clingmans Dome"]

models = {}
for key, f, label in [("dp2", "lookrock_dp2.npy", "Depth Pro 2 (B)"), ("da3", "lookrock_da3.npy", "DA3-SMALL")]:
    if (D / f).exists():
        models[key] = (np.load(D / f), label)

report = {}
for key, (dep, label) in models.items():
    med = []
    for n in names:
        x0, x1, y0, y1 = LANDMARKS[n][1]
        v = dep[y0:y1, x0:x1]
        v = v[np.isfinite(v)]
        med.append(float(np.median(v)) / 1000 if v.size else np.inf)
    med = np.array(med)
    fin = np.isfinite(med) & (med > 0)
    rho = spearmanr(med[fin], chart_km[fin])[0] if fin.sum() > 2 else float("nan")
    raw_err = (med - chart_km) / chart_km
    ia = [names.index(a) for a in ANCHORS]
    ok = all(np.isfinite(med[i]) and med[i] > 0 for i in ia)
    fit_err = [None] * len(names); ab = None
    if ok:
        b, ln_a = np.polyfit(np.log(med[ia]), np.log(chart_km[ia]), 1)
        pred = np.exp(ln_a) * med ** b
        fit_err = list((pred - chart_km) / chart_km)
        ab = (float(np.exp(ln_a)), float(b))
    order = np.argsort(chart_km)
    sep = None
    for i in order[1:]:
        j = order[list(order).index(i) - 1]
        if fin[i] and fin[j] and med[i] > med[j]:
            sep = chart_km[i]
    sky = dep[:250]
    report[label] = dict(
        per_ridge=[dict(ridge=n, chart_km=round(float(c), 1), model_km=(round(float(m), 2) if np.isfinite(m) else "inf"),
                        raw_error=(round(float(e), 2) if np.isfinite(e) else None),
                        error_after_anchor_fit=(round(float(fe), 2) if fe is not None and np.isfinite(fe) else None))
                   for n, c, m, e, fe in zip(names, chart_km, med, raw_err, fit_err)],
        spearman_vs_chart=float(rho), anchor_fit_a_b=ab, anchors=ANCHORS,
        farthest_chart_km_still_ordered_after_nearer_neighbour=sep,
        sky_top250rows=dict(inf_fraction=float(np.mean(~np.isfinite(sky))),
                            median_finite_km=(float(np.median(sky[np.isfinite(sky)])) / 1000 if np.isfinite(sky).any() else None)),
    )
print(json.dumps(report, indent=1))
(D / "depth_compare.json").write_text(json.dumps(report, indent=1))


def colour(dep):
    v = dep.copy().astype(float)
    finite = np.isfinite(v)
    top = np.nanpercentile(v[finite], 99.5) if finite.any() else 1
    v[~finite] = top
    lv = np.log10(np.clip(v, 1e-3, None))
    lo, hi = np.percentile(lv, 1), np.log10(top)
    return np.clip((lv - lo) / (hi - lo + 1e-9), 0, 1)


fig, axs = plt.subplots(1, 1 + len(models), figsize=(6 * (1 + len(models)), 5.2))
axs = np.atleast_1d(axs)
axs[0].imshow(src); axs[0].set_title("Look Rock, 20 Nov 2016 12:00 (clear reference)", fontsize=10)
for ax, (key, (dep, label)) in zip(axs[1:], models.items()):
    ax.imshow(colour(dep), cmap="magma_r")
    r = report[label]
    ax.set_title(f"{label}: log depth (near = light, far = dark; black = infinite)\nSpearman vs NPS chart = {r['spearman_vs_chart']:.2f}", fontsize=10)
    plt.imsave(D / ("depth_pro2.png" if key == "dp2" else "depth_da3.png"), colour(dep), cmap="magma_r")
for ax in axs:
    for n in names:
        mi, (x0, x1, y0, y1) = LANDMARKS[n]
        ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec="cyan", lw=0.8))
        ax.text(x0, y0 - 4, f"{mi} mi", color="cyan", fontsize=7)
    ax.axis("off")
fig.text(0.5, 0.01, "Depth Pro 2 weights: Apple ML Research Model License, research-only (non-commercial). Boxes: NPS chart ridges, distances in miles.",
         ha="center", fontsize=8, style="italic")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(D / "depth_side_by_side.png", dpi=130)
print("wrote", D / "depth_side_by_side.png")
