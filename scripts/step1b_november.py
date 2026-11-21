"""Step 1 fix: anchored haze fit on every November 2016 midday frame, scored against
the Look Rock site's own extinction (3.912 / visual range).

Nothing is tuned on the test frames. The only calibration is beta_ref for the
20 Nov reference frame, taken from that hour's site visual range (plan sec 3.3).

Run: PYTHONPATH=. uv run python scripts/step1b_november.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy.stats import spearmanr

from pluma.haze.fit import srgb_to_linear, luminance, beta_anchored, beta_absolute
from pluma.haze.gate import sky_texture, SKY_TEXTURE_MAX
from pluma.regions_lookrock import LANDMARKS, SKY, FOREGROUND, MILE

ROOT = Path(__file__).resolve().parents[1]
FR, META, OUT = ROOT / "data/frames/lookrock", ROOT / "data/nps_meta", ROOT / "out/step1"
REF = "20161120_1200"

names = list(LANDMARKS)
dist = np.array([LANDMARKS[n][0] * MILE for n in names])


def mask(shape, b):
    x0, x1, y0, y1 = b
    m = np.zeros(shape, bool)
    m[y0:y1, x0:x1] = True
    return m


def lum(p):
    return luminance(srgb_to_linear(np.asarray(Image.open(p).convert("RGB"), float) / 255))


def site_values():
    """Map 'YYYYMMDD_HHMM' -> site readings for noon frames from saved NPS metadata."""
    out = {}
    for f in META.glob("r*.json"):
        for r in json.loads(f.read_text())["Results"]:
            a = r["Asset"]
            t = a["LocalTimeString"]
            m, d, rest = t.split("/", 2)
            y, hm, ap = rest.split(" ")[:3]
            hh, mm = map(int, hm.split(":"))
            hh = hh % 12 + (12 if ap == "PM" else 0)
            key = f"{y}{int(m):02d}{int(d):02d}_{hh:02d}{mm:02d}"
            out[key] = {x["Name"]: x["Value"] for x in a["CustomNumberFields"]}
    return out


def shift(a, b):
    """Integer image shift of b relative to a by phase correlation (camera-move check)."""
    A, B = np.fft.fft2(a - a.mean()), np.fft.fft2(b - b.mean())
    R = A * np.conj(B)
    r = np.abs(np.fft.ifft2(R / (np.abs(R) + 1e-9)))
    dy, dx = np.unravel_index(np.argmax(r), r.shape)
    h, w = a.shape
    return (dx if dx < w // 2 else dx - w, dy if dy < h // 2 else dy - h)


site = site_values()
ref = lum(FR / f"grsm_{REF}.jpg")
shape = ref.shape
sky, fg = mask(shape, SKY), mask(shape, FOREGROUND)
bands = [mask(shape, LANDMARKS[n][1]) for n in names]
beta_ref = 3912.0 / site[REF]["VisualRange"] * 1e-6

rows = []
for p in sorted(FR.glob("grsm_2016*.jpg")):
    key = p.stem.replace("grsm_", "")
    s = site.get(key, {})
    vr, rh, pm = s.get("VisualRange"), s.get("RelativeHumidity"), s.get("ParticulateMatter")
    rgb = np.asarray(Image.open(p).convert("RGB"), float) / 255
    img = luminance(srgb_to_linear(rgb))
    tex = sky_texture(rgb)
    dx, dy = shift(ref[300:750], img[300:750])
    an = beta_anchored(img, ref, sky, fg, bands, dist, beta_ref)
    ab = beta_absolute(img, sky, bands, dist)
    rows.append(dict(
        frame=key, site_beta=3912.0 / vr if vr else None, vr=vr, rh=rh, pm=pm,
        cam_beta=an.beta_Mm, cam_lo=an.jackknife_per_m[0] * 1e6, cam_hi=an.jackknife_per_m[1] * 1e6,
        r2=an.r2, A=an.A, gain=an.gain, old_beta=ab.beta_Mm if ab else None, shift=(int(dx), int(dy)),
        is_ref=key == REF, sky_texture=tex, cloud_ok=tex <= SKY_TEXTURE_MAX,
    ))

print(f"{'frame':14s} {'site':>6s} {'camera':>7s} {'jackknife':>13s} {'r2':>5s} {'old':>6s} {'gain':>5s} {'RH':>4s} {'PM':>6s} shift")
for r in rows:
    sb = f"{r['site_beta']:.0f}" if r["site_beta"] else "-"
    ob = f"{r['old_beta']:.0f}" if r["old_beta"] is not None else "-"
    print(f"{r['frame']:14s} {sb:>6s} {r['cam_beta']:7.0f} {r['cam_lo']:6.0f}-{r['cam_hi']:<6.0f} {r['r2']:5.2f} "
          f"{ob:>6s} {r['gain']:5.2f} {r['rh'] or 0:4.0f} {r['pm'] if r['pm'] is not None else float('nan'):6.1f} {r['shift']}"
          + ("  <- reference" if r["is_ref"] else "") + ("" if r["cloud_ok"] else "  CLOUD-GATED"))


def score(sel):
    x = np.array([r["site_beta"] for r in sel])
    y = np.array([r["cam_beta"] for r in sel])
    yo = np.array([r["old_beta"] if r["old_beta"] is not None else np.nan for r in sel])
    le = np.log(y / x)
    return x, y, yo, dict(
        n=len(sel), spearman_fixed=spearmanr(x, y)[0],
        spearman_old=spearmanr(x[~np.isnan(yo)], yo[~np.isnan(yo)])[0],
        median_ratio=float(np.exp(np.median(le))),
        within_factor_1_5=float(np.mean(np.abs(le) < np.log(1.5))),
        within_factor_2=float(np.mean(np.abs(le) < np.log(2))),
    )


all_test = [r for r in rows if not r["is_ref"] and r["site_beta"]]
test = [r for r in all_test if r["cloud_ok"]]
_, _, _, s_all = score(all_test)
x, y, yo, summary = score(test)
summary = dict(gated=summary, ungated=s_all)
print("\n", json.dumps(summary, indent=1))
rho, rho_old = summary["gated"]["spearman_fixed"], summary["gated"]["spearman_old"]

# ---- plot: scatter ----
fig, ax = plt.subplots(1, 2, figsize=(13, 5.6))
a = ax[0]
for r in test:
    a.errorbar(r["site_beta"], r["cam_beta"],
               yerr=[[max(r["cam_beta"] - r["cam_lo"], 0)], [max(r["cam_hi"] - r["cam_beta"], 0)]],
               fmt="o", color="#2a7de1" if r["r2"] > 0.8 else "#b0b0b0", ms=6, capsize=2, lw=0.8)
    a.annotate(r["frame"][6:8], (r["site_beta"], r["cam_beta"]), fontsize=7, xytext=(4, 2), textcoords="offset points")
a.plot(x[~np.isnan(yo)], yo[~np.isnan(yo)], "x", color="#e07b00", label="old method (sky band A)")
lim = [10, 3000]
a.plot(lim, lim, "k--", lw=0.8, label="1:1")
a.fill_between(lim, [l / 1.5 for l in lim], [l * 1.5 for l in lim], color="k", alpha=0.06, label="within ×1.5")
a.set_xscale("log"); a.set_yscale("log"); a.set_xlim(lim); a.set_ylim(lim)
a.set_xlabel("site extinction from visual range, 3.912/VR (Mm$^{-1}$)")
a.set_ylabel("camera extinction (Mm$^{-1}$)")
for r in all_test:
    if not r["cloud_ok"]:
        a.plot(r["site_beta"], r["cam_beta"], "^", color="#c9a0dc", ms=6)
        a.annotate(r["frame"][6:8], (r["site_beta"], r["cam_beta"]), fontsize=7, color="#9a6bb5",
                   xytext=(4, 2), textcoords="offset points")
a.plot([], [], "^", color="#c9a0dc", label="cloud-gated (not scored)")
a.set_title(f"Nov 2016 middays, n={len(test)} scored (ref 20 Nov and {len(all_test)-len(test)} cloudy excluded)\n"
            f"Spearman: fixed {rho:.2f}, old {rho_old:.2f}.  Grey = fit r$^2$ ≤ 0.8", fontsize=9)
a.legend(fontsize=7, loc="upper left"); a.grid(alpha=0.3, which="both")

# ---- plot: time series ----
a = ax[1]
dates = [int(r["frame"][6:8]) for r in rows]
a.plot(dates, [r["site_beta"] or np.nan for r in rows], "s-", color="k", label="site (3.912/VR)")
a.plot(dates, [r["cam_beta"] if r["cloud_ok"] else np.nan for r in rows], "o-", color="#2a7de1",
       label="camera (fixed fit)")
a.plot([d for d, r in zip(dates, rows) if not r["cloud_ok"]], [r["cam_beta"] for r in rows if not r["cloud_ok"]],
       "^", color="#c9a0dc", label="camera, cloud-gated")
a.set_yscale("log"); a.set_xlabel("November 2016, 12:00 EST"); a.set_ylabel("extinction (Mm$^{-1}$)")
a.set_title("Day by day", fontsize=9); a.legend(fontsize=8); a.grid(alpha=0.3, which="both")
fig.tight_layout(); fig.savefig(OUT / "november_validation.png", dpi=130)

(OUT / "november_results.json").write_text(json.dumps(dict(rows=rows, summary=summary), indent=1, default=float))
print(f"wrote {OUT/'november_validation.png'}")
