"""Build step 1: Look Rock clear frame vs 26 Nov 2016 frame, haze fit with NPS chart distances.

Run: uv run python scripts/step1_lookrock_fit.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from pluma.haze.fit import srgb_to_linear, luminance, beta_absolute, beta_differential
from pluma.regions_lookrock import LANDMARKS, SKY, MILE

ROOT = Path(__file__).resolve().parents[1]
FR = ROOT / "data/frames/lookrock"
META = ROOT / "data/nps_meta"
OUT = ROOT / "out/step1"
OUT.mkdir(parents=True, exist_ok=True)

FRAMES = {
    # label: (file, NPS asset id, metadata file, role)
    "20 Nov 2016 12:00 (clear ref)": ("grsm_20161120_1200.jpg", "a46cc552-14bc-4a0c-9ccf-f4a352662b96", "r20.json", "ref"),
    "26 Nov 2016 12:00 (requested)": ("grsm_20161126_1200.jpg", "47b7e83c-3b3a-45cd-9e03-d9bc1076a948", "r26.json", "test"),
    "14 Nov 2016 12:30 (extra, smoky)": ("grsm_20161114_1230.jpg", "302750ae-c8fc-40f8-b892-0eb41e9adae9", "r14.json", "test"),
}


def nps_meta(meta_file: str, asset_id: str) -> dict:
    j = json.loads((META / meta_file).read_text())
    for r in j["Results"]:
        a = r["Asset"]
        if a["AssetID"] == asset_id:
            vals = {f["Name"]: f["Value"] for f in a["CustomNumberFields"]}
            vals["time"] = a["LocalTimeString"]
            return vals
    raise KeyError(asset_id)


def load_lum(path: Path) -> np.ndarray:
    rgb = np.asarray(Image.open(path).convert("RGB"), float) / 255.0
    return luminance(srgb_to_linear(rgb))


def box_mask(shape, box):
    x0, x1, y0, y1 = box
    m = np.zeros(shape, bool)
    m[y0:y1, x0:x1] = True
    return m


names = list(LANDMARKS)
dist_m = np.array([LANDMARKS[n][0] * MILE for n in names])

imgs = {k: load_lum(FR / v[0]) for k, v in FRAMES.items()}
shape = next(iter(imgs.values())).shape
sky = box_mask(shape, SKY)
bands = [box_mask(shape, LANDMARKS[n][1]) for n in names]

results = {}
ref_key = next(k for k, v in FRAMES.items() if v[3] == "ref")

# NPS visual range -> extinction (Koschmieder 3.912/VR). Units assumed km.
meta = {k: nps_meta(v[2], v[1]) for k, v in FRAMES.items()}
for k in meta:
    vr = meta[k].get("VisualRange")
    meta[k]["beta_from_VR_Mm"] = 3912.0 / vr if vr else None

beta_ref = meta[ref_key]["beta_from_VR_Mm"] * 1e-6  # per m

print(f"{'landmark':20s} {'mi':>4s} " + " ".join(f"{k[:6]:>16s}" for k in FRAMES))
for i, n in enumerate(names):
    row = [np.median(imgs[k][bands[i]]) for k in FRAMES]
    print(f"{n:20s} {LANDMARKS[n][0]:4d} " + " ".join(f"{v:16.4f}" for v in row))
print(f"{'SKY A':20s} {'':4s} " + " ".join(f"{np.median(imgs[k][sky]):16.4f}" for k in FRAMES))
print()

for k in FRAMES:
    ab = beta_absolute(imgs[k], sky, bands, dist_m)
    entry = {
        "nps": {x: meta[k].get(x) for x in ("time", "ParticulateMatter", "VisualRange", "RelativeHumidity", "beta_from_VR_Mm")},
        "absolute": None, "differential": None,
    }
    if ab:
        entry["absolute"] = dict(beta_Mm=ab.beta_Mm, ci_Mm=[c * 1e6 for c in ab.ci_per_m], r2=ab.r2,
                                 n_bands=int(len(ab.d_m)), A=ab.sky)
    if FRAMES[k][3] == "test":
        df = beta_differential(imgs[k], imgs[ref_key], sky, bands, dist_m, beta_ref)
        if df:
            entry["differential"] = dict(beta_Mm=df.beta_Mm, ci_Mm=[c * 1e6 for c in df.ci_per_m], r2=df.r2,
                                         n_bands=int(len(df.d_m)), beta_ref_Mm=beta_ref * 1e6,
                                         used=[names[i] for i in range(len(names)) if dist_m[i] in df.d_m])
        entry["_df"] = df
    entry["_ab"] = ab
    results[k] = entry

# ---------- report ----------
for k, e in results.items():
    n = e["nps"]
    print(f"== {k}")
    print(f"   NPS site: PM={n['ParticulateMatter']:.1f}  VR={n['VisualRange']:.1f}  RH={n['RelativeHumidity']:.0f}%  "
          f"-> beta(VR)={n['beta_from_VR_Mm']:.0f} Mm^-1")
    if e["absolute"]:
        a = e["absolute"]
        print(f"   absolute fit:     beta={a['beta_Mm']:7.1f} Mm^-1  CI[{a['ci_Mm'][0]:.1f},{a['ci_Mm'][1]:.1f}]  r2={a['r2']:.2f}  bands={a['n_bands']}")
    else:
        print("   absolute fit:     no reading (<2 bands darker than sky)")
    if FRAMES[k][3] == "test":
        if e["differential"]:
            d = e["differential"]
            print(f"   differential fit: beta={d['beta_Mm']:7.1f} Mm^-1  CI[{d['ci_Mm'][0]:.1f},{d['ci_Mm'][1]:.1f}]  r2={d['r2']:.2f}  bands={d['n_bands']}")
        else:
            print("   differential fit: no reading (<3 usable bands)")

# ---------- plot ----------
colors = {list(FRAMES)[0]: "#2a7de1", list(FRAMES)[1]: "#e07b00", list(FRAMES)[2]: "#b3261e"}
fig = plt.figure(figsize=(15, 10))
gs = fig.add_gridspec(2, 3, height_ratios=[1, 1.05])

for j, k in enumerate(FRAMES):
    ax = fig.add_subplot(gs[0, j])
    im = Image.open(FR / FRAMES[k][0]).convert("RGB")
    ax.imshow(np.asarray(im)[280:600])
    x0, x1, y0, y1 = SKY
    ax.add_patch(plt.Rectangle((x0, y0 - 280), x1 - x0, y1 - y0, fill=False, ec="cyan", lw=1))
    for n in names:
        mi, (x0, x1, y0, y1) = LANDMARKS[n]
        ax.add_patch(plt.Rectangle((x0, y0 - 280), x1 - x0, y1 - y0, fill=False, ec="yellow", lw=1))
        ax.text(x0, y0 - 283, f"{mi}", color="yellow", fontsize=7)
    nps = results[k]["nps"]
    ax.set_title(f"{k}\nNPS: PM {nps['ParticulateMatter']:.1f}, VR {nps['VisualRange']:.0f}, RH {nps['RelativeHumidity']:.0f}%", fontsize=9)
    ax.axis("off")

# absolute
ax = fig.add_subplot(gs[1, 0:2])
for k, e in results.items():
    ab = e["_ab"]
    A = np.median(imgs[k][sky])
    I = np.array([np.median(imgs[k][b]) for b in bands])
    ok = (A - I) > 0
    ax.plot(dist_m[ok] / 1000, np.log(A - I[ok]), "o", color=colors[k], label=None)
    ax.plot(dist_m[~ok] / 1000, np.full((~ok).sum(), -7.5), "x", color=colors[k])
    if ab and len(ab.d_m) > 2:
        xx = np.linspace(0, 66, 50)
        ax.plot(xx, ab.intercept - ab.beta_per_m * xx * 1000, "-", color=colors[k],
                label=f"{k}: beta={ab.beta_Mm:.0f} Mm$^{{-1}}$ (r$^2$={ab.r2:.2f}, n={len(ab.d_m)})")
for i, n in enumerate(names):
    ax.annotate(n, (dist_m[i] / 1000, -7.3), fontsize=6, rotation=60, ha="left")
ax.set_xlabel("distance from NPS landmark chart (km)")
ax.set_ylabel("ln(A - I)   [linear luminance]")
ax.set_ylim(-8, -0.5)
ax.set_title("Absolute fit (sec 3.1): slope = -beta.  x at bottom = band brighter than sky (vanished)", fontsize=9)
ax.legend(fontsize=7, loc="upper right")
ax.grid(alpha=0.3)

# differential
ax = fig.add_subplot(gs[1, 2])
for k, e in results.items():
    if FRAMES[k][3] != "test":
        continue
    df = e["_df"]
    A, Ar = np.median(imgs[k][sky]), np.median(imgs[ref_key][sky])
    I = np.array([np.median(imgs[k][b]) for b in bands])
    Ir = np.array([np.median(imgs[ref_key][b]) for b in bands])
    cur, base = A - I, Ar - Ir
    ok = (cur > 0) & (base > 0)
    ax.plot(dist_m[ok] / 1000, np.log(cur[ok]) - np.log(base[ok]), "o", color=colors[k])
    if df:
        xx = np.linspace(0, 66, 50)
        slope = beta_ref - df.beta_per_m
        ax.plot(xx, df.intercept + slope * xx * 1000, "-", color=colors[k],
                label=f"{k[:6]}: beta={df.beta_Mm:.0f} (r$^2$={df.r2:.2f}, n={len(df.d_m)})")
ax.set_xlabel("distance (km)")
ax.set_ylabel("dy = ln(A-I) - ln(A_ref - I_ref)")
ax.set_title(f"Differential fit vs 20 Nov (sec 3.3)\nbeta_ref = {beta_ref*1e6:.0f} Mm$^{{-1}}$ from NPS VR", fontsize=9)
ax.legend(fontsize=7)
ax.grid(alpha=0.3)

fig.suptitle("Pluma step 1 - Look Rock, GRSM. Camera haze fit with NPS chart distances", fontsize=12)
fig.tight_layout()
fig.savefig(OUT / "lookrock_fit.png", dpi=130)

clean = {k: {kk: vv for kk, vv in e.items() if not kk.startswith("_")} for k, e in results.items()}
(OUT / "step1_results.json").write_text(json.dumps(clean, indent=2, default=float))
print(f"\nwrote {OUT/'lookrock_fit.png'}")
