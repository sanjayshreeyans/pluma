"""Demo showcase: clear vs layered-smoke vs heavy-smoke at Look Rock.

Frames hand-picked for the demo (allowed for the showcase). The scored validation
over all November middays is in november_validation.png.
Run: PYTHONPATH=. uv run python scripts/demo_showcase.py
"""
from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from pluma.haze.fit import srgb_to_linear, luminance, beta_anchored
from pluma.regions_lookrock import LANDMARKS, SKY, FOREGROUND, MILE

ROOT = Path(__file__).resolve().parents[1]
FR, OUT = ROOT / "data/frames/lookrock", ROOT / "out/step1"
res = {r["frame"]: r for r in json.loads((OUT / "november_results.json").read_text())["rows"]}

SHOW = [("20161120_1200", "Clear", "#2a7de1"),
        ("20161126_1200", "Smoke layer in valleys", "#e07b00"),
        ("20161108_1200", "Heavy smoke", "#b3261e")]
REF = "20161120_1200"

names = list(LANDMARKS)
dist = np.array([LANDMARKS[n][0] * MILE for n in names])


def mask(shape, b):
    x0, x1, y0, y1 = b
    m = np.zeros(shape, bool); m[y0:y1, x0:x1] = True
    return m


def rgb(k):
    return np.asarray(Image.open(FR / f"grsm_{k}.jpg").convert("RGB"))


ref = luminance(srgb_to_linear(rgb(REF) / 255.0))
sky, fg = mask(ref.shape, SKY), mask(ref.shape, FOREGROUND)
bands = [mask(ref.shape, LANDMARKS[n][1]) for n in names]
beta_ref = res[REF]["site_beta"] * 1e-6

fig = plt.figure(figsize=(15, 8.5))
gs = fig.add_gridspec(2, 3, height_ratios=[1, 1.1], hspace=0.28)
ax_fit = fig.add_subplot(gs[1, :])
for j, (k, title, col) in enumerate(SHOW):
    im = rgb(k)
    a = fig.add_subplot(gs[0, j])
    a.imshow(im[200:750]); a.axis("off")
    r = res[k]
    a.set_title(f"{title} - {k[6:8]} Nov 2016, noon\ncamera {r['cam_beta']:.0f} Mm$^{{-1}}$   |   site {r['site_beta']:.0f} Mm$^{{-1}}$",
                fontsize=10, color=col)
    img = luminance(srgb_to_linear(im / 255.0))
    an = beta_anchored(img, ref, sky, fg, bands, dist, beta_ref)
    dd = np.linspace(0, 66e3, 300)
    J = np.median(an.gain * an.J)
    ax_fit.plot(dist / 1000, an.I, "o", color=col, ms=7)
    # per-band model points (each ridge has its own J), plus a smooth curve for a typical ridge
    ax_fit.plot(dd / 1000, an.A + (J - an.A) * np.exp(-an.beta_per_m * dd), "-", color=col, lw=1.6,
                label=f"{title}: camera {an.beta_Mm:.0f}, site {r['site_beta']:.0f} Mm$^{{-1}}$")
    ax_fit.axhline(an.A, color=col, ls=":", lw=0.8)
for i, n in enumerate(names):
    ax_fit.annotate(n, (dist[i] / 1000, 0.005), fontsize=7, rotation=55, ha="left", color="#555")
ax_fit.set_xlabel("distance to ridge, from NPS landmark chart (km)")
ax_fit.set_ylabel("ridge brightness (linear)")
ax_fit.set_ylim(0, 0.45)
ax_fit.set_title("Ridges fade toward the haze brightness (dotted) with distance. Faster fade = more extinction.", fontsize=10)
ax_fit.legend(fontsize=9, loc="lower right"); ax_fit.grid(alpha=0.3)
fig.suptitle("Look Rock, Great Smoky Mountains - extinction read from a webcam", fontsize=13)
fig.savefig(OUT / "demo_showcase.png", dpi=130, bbox_inches="tight")
print("wrote", OUT / "demo_showcase.png")
