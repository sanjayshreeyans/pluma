"""Demo step 1: every November 2016 hourly frame (10:00-16:00 EST), gated, fitted,
calibrated on the first half of days, scored on the second half.

Reference for each hour = 20 Nov 2016 at the same hour (clear day), beta_ref from
that hour's site visual range. PM2.5 reference = NPS on-site TEOM (archive metadata).
Run: PYTHONPATH=. uv run python scripts/demo_step1.py [--no-window]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy.stats import spearmanr

from pluma.haze.fit import srgb_to_linear, luminance, beta_anchored, beta_windowed
from pluma.haze.gate import sky_texture, SKY_TEXTURE_MAX
from pluma.lookrock import site_values, NAMES, DIST, _mask
from pluma.regions_lookrock import LANDMARKS, SKY, FOREGROUND
from pluma.convert import fit_alpha_g, pm25, category, CATEGORIES

ROOT = Path(__file__).resolve().parents[1]
FR = ROOT / "data/frames/lookrock"
OUT = ROOT / "out/demo"; OUT.mkdir(parents=True, exist_ok=True)
USE_WINDOW = "--window" in sys.argv   # windowed fit tested and reverted: did not help
G_FIXED = 0.4          # plan sec 3.4 starting value; not fitted (too few humid hours)
LAT, LON = 35.6335, -83.9416
HEADING, HALF_FOV = 100.0, 22.0   # approx. view centre (east-southeast) and half field of view
REF_DAY = "20161120"
SPLIT_DAY = 19         # train: 8-18 Nov, test: 19-29 Nov
NOTE = "PM2.5 reference: NPS on-site TEOM at Look Rock (NPS AirWebCams archive), not an EPA file; TEOMs can read low in heavy smoke."


def sun_pos(y, mo, d, hh_est):
    """Approximate solar elevation/azimuth (deg) for EST clock hour."""
    n = (np.datetime64(f"{y}-{mo:02d}-{d:02d}") - np.datetime64(f"{y}-01-01")).astype(int) + 1
    decl = 23.44 * math.sin(math.radians(360 / 365 * (284 + n)))
    b = math.radians(360 / 365 * (n - 81))
    eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)
    solar_time = hh_est + (4 * (LON - (-75)) + eot) / 60
    H = math.radians(15 * (solar_time - 12))
    la, de = math.radians(LAT), math.radians(decl)
    el = math.asin(math.sin(la) * math.sin(de) + math.cos(la) * math.cos(de) * math.cos(H))
    az = math.degrees(math.atan2(math.sin(H), math.cos(H) * math.sin(la) - math.tan(de) * math.cos(la))) + 180
    return math.degrees(el), az


def lum_rgb(p):
    rgb = np.asarray(Image.open(p).convert("RGB"), float) / 255
    return rgb, luminance(srgb_to_linear(rgb))


site = site_values(sorted((ROOT / "data/nps_meta").glob("r*.json")))
shape = (750, 1000)
sky, fg = _mask(shape, SKY), _mask(shape, FOREGROUND)
bands = [_mask(shape, LANDMARKS[n][1]) for n in NAMES]

refs = {}
for hh in range(10, 17):
    p = FR / f"grsm_{REF_DAY}_{hh:02d}00.jpg"
    vr = site.get(f"{REF_DAY}_{hh:02d}00", {}).get("VisualRange")
    if p.exists() and vr:
        refs[hh] = (lum_rgb(p)[1], 3912.0 / vr * 1e-6)

rows = []
for p in sorted(FR.glob("grsm_2016*_??00.jpg")):
    key = p.stem.replace("grsm_", "")
    y, mo, d, hh = int(key[:4]), int(key[4:6]), int(key[6:8]), int(key[9:11])
    if not 10 <= hh <= 16:
        continue
    s = site.get(key, {})
    rh, pm, vr = s.get("RelativeHumidity"), s.get("ParticulateMatter"), s.get("VisualRange")
    el, az = sun_pos(y, mo, d, hh)
    rgb, img = lum_rgb(p)
    if img.shape != shape:
        continue
    tex = sky_texture(rgb)
    reason = None
    if key.startswith(REF_DAY):
        reason = "reference day"
    elif el < 15:
        reason = f"sun low ({el:.0f} deg)"
    elif abs((az - HEADING + 180) % 360 - 180) < HALF_FOV + 15:
        reason = "sun in view"
    elif rh is None:
        reason = "no humidity reading"
    elif rh > 85:
        reason = f"RH {rh:.0f}% > 85"
    elif tex > SKY_TEXTURE_MAX:
        reason = f"cloud (sky texture {tex:.1f})"
    elif hh not in refs:
        reason = "no reference for hour"
    row = dict(timestamp=f"{y}-{mo:02d}-{d:02d}T{hh:02d}:00-05:00", file=p.name, key=key,
               gate="pass" if reason is None else "reject", reject_reason=reason,
               sun_elev=round(el, 1), rh=rh, monitor_pm25=pm, site_beta=(3912.0 / vr if vr else None),
               split="train" if d < SPLIT_DAY else "test")
    if hh in refs:
        ref, bref = refs[hh]
        if USE_WINDOW:
            res, keep = beta_windowed(img, ref, sky, fg, bands, DIST, bref)
        else:
            res, keep = beta_anchored(img, ref, sky, fg, bands, DIST, bref), np.ones(len(DIST), bool)
        full = beta_anchored(img, ref, sky, fg, bands, DIST, bref)
        row.update(cam_beta=res.beta_Mm, fit_r2=res.r2, A=res.A, gain=res.gain,
                   bands=[dict(name=n, distance_km=round(DIST[i] / 1000, 2), I=float(full.I[i]),
                               signal=float((res.A - full.I[i]) / res.A), kept=bool(keep[i]))
                          for i, n in enumerate(NAMES)],
                   fitted_slope_per_km=-res.beta_per_m * 1000)
    rows.append(row)

ok = [r for r in rows if r["gate"] == "pass"]
# camera vs site extinction (no PM involved)
cs = [r for r in ok if r["site_beta"]]
rho_ext = spearmanr([r["cam_beta"] for r in cs], [r["site_beta"] for r in cs])[0]

# calibrate alpha on train half, score on test half
tr = [r for r in ok if r["split"] == "train" and r["monitor_pm25"] is not None]
te = [r for r in ok if r["split"] == "test" and r["monitor_pm25"] is not None]
alpha, g, q = fit_alpha_g([r["cam_beta"] for r in tr], [r["rh"] for r in tr], [r["monitor_pm25"] for r in tr], fix_g=G_FIXED)
for r in rows:
    if "cam_beta" in r and r["rh"] is not None:
        r["pred_pm25"] = float(pm25(r["cam_beta"], r["rh"], alpha, g))
        r["category"] = category(r["pred_pm25"])
    if r["monitor_pm25"] is not None:
        r["monitor_category"] = category(r["monitor_pm25"])

cat_idx = {n: i for i, (_, n) in enumerate(CATEGORIES)}


def score(rs):
    pr = np.array([r["pred_pm25"] for r in rs]); ob = np.array([r["monitor_pm25"] for r in rs])
    ci = np.array([cat_idx[r["category"]] for r in rs]); co = np.array([cat_idx[r["monitor_category"]] for r in rs])
    return dict(n=len(rs), spearman=float(spearmanr(pr, ob)[0]), mean_error=float(np.mean(pr - ob)),
                mean_abs_error=float(np.mean(np.abs(pr - ob))), category_match=float(np.mean(ci == co)),
                within_one_category=float(np.mean(np.abs(ci - co) <= 1)))


headline = dict(
    method="windowed" if USE_WINDOW else "all bands",
    frames_total=len(rows), frames_passed_gates=len(ok),
    camera_vs_site_extinction=dict(n=len(cs), spearman=float(rho_ext)),
    alpha=alpha, g_fixed=g, train_days="8-18 Nov 2016", test_days="19-29 Nov 2016",
    train=score(tr), test=score(te), reference_note=NOTE,
)
print(json.dumps(headline, indent=1))
tag = "_window" if USE_WINDOW else ""
(OUT / f"headline{tag}.json").write_text(json.dumps(headline, indent=1))
(OUT / f"rows{tag}.json").write_text(json.dumps(rows, indent=1, default=float))
if USE_WINDOW:
    sys.exit()

# ---------------- Chart A ----------------
fig, ax = plt.subplots(figsize=(6.4, 6))
for sp, col in [("train", "#7aa7e0"), ("test", "#e07b00")]:
    xs = [r["site_beta"] for r in cs if r["split"] == sp]; ys = [r["cam_beta"] for r in cs if r["split"] == sp]
    ax.scatter(xs, ys, s=18, color=col, alpha=0.8, label=f"{sp} days")
ax.plot([10, 3000], [10, 3000], "k--", lw=0.8, label="1:1")
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(10, 3000); ax.set_ylim(10, 3000)
ax.set_xlabel("site extinction, 3.912 / visual range (Mm⁻¹)"); ax.set_ylabel("camera extinction (Mm⁻¹)")
ax.set_title(f"A. Camera vs site extinction, Look Rock, Nov 2016\nSpearman ρ = {rho_ext:.2f}, n = {len(cs)} hourly frames", fontsize=10)
ax.grid(alpha=0.3, which="both"); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(OUT / "chart_A_extinction.png", dpi=140); plt.close(fig)

# ---------------- Chart B ----------------
import datetime as dt
fig, ax = plt.subplots(figsize=(13, 4.8))
t_all = [dt.datetime.fromisoformat(r["timestamp"][:16]) for r in rows if r["monitor_pm25"] is not None]
ax.plot(t_all, [r["monitor_pm25"] for r in rows if r["monitor_pm25"] is not None], "-", color="k", lw=1, label="NPS on-site monitor (TEOM)")
for sp, col in [("train", "#7aa7e0"), ("test", "#e07b00")]:
    rs = [r for r in ok if r["split"] == sp and "pred_pm25" in r]
    ax.plot([dt.datetime.fromisoformat(r["timestamp"][:16]) for r in rs], [r["pred_pm25"] for r in rs], "o", ms=4, color=col,
            label=f"camera, {sp} half")
b = dt.datetime(2016, 11, SPLIT_DAY)
ax.axvline(b, color="#999", ls="--"); ax.text(b, ax.get_ylim()[1] * 0.95, "  train | test →", fontsize=9, color="#555", va="top")
ax.axvspan(dt.datetime(2016, 11, 26, 9), dt.datetime(2016, 11, 26, 17), color="#e07b00", alpha=0.12)
ax.text(dt.datetime(2016, 11, 26, 9), ax.get_ylim()[1] * 0.8, "26 Nov\nvalley smoke", fontsize=8, color="#a05500")
for e, name in CATEGORIES[:3]:
    ax.axhline(e, color="#ddd", lw=0.7, zorder=0)
t = headline["test"]
ax.set_ylabel("PM2.5 (µg/m³)")
ax.set_title(f"B. PM2.5 from the camera vs on-site monitor, Nov 2016 (10:00-16:00).  Test half: ρ = {t['spearman']:.2f}, "
             f"mean error {t['mean_error']:+.1f}, category {t['category_match']:.0%}, within one {t['within_one_category']:.0%}, n = {t['n']}",
             fontsize=9)
ax.legend(fontsize=8, loc="upper right"); ax.grid(alpha=0.25)
fig.text(0.5, 0.01, NOTE + f"  alpha fitted on train half ({alpha:.2f} m²/g), humidity exponent fixed at {g}.", ha="center", fontsize=7.5, style="italic")
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(OUT / "chart_B_timeseries.png", dpi=140); plt.close(fig)

# ---------------- Chart C ----------------
byk = {r["key"]: r for r in rows}
pair = [("20161120_1200", "Clear day, 20 Nov 2016 12:00", "#2a7de1"), ("20161126_1200", "Valley smoke, 26 Nov 2016 12:00", "#e07b00")]
fig = plt.figure(figsize=(13, 7.5)); gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.1])
axf = fig.add_subplot(gs[1, :])
ref12 = refs[12][0]
for j, (k, title, col) in enumerate(pair):
    rgb, img = lum_rgb(FR / f"grsm_{k}.jpg")
    a = fig.add_subplot(gs[0, j]); a.imshow((rgb[200:750] * 255).astype(np.uint8)); a.axis("off")
    res, keep = beta_anchored(img, ref12, sky, fg, bands, DIST, refs[12][1]), np.ones(len(DIST), bool)
    full = beta_anchored(img, ref12, sky, fg, bands, DIST, refs[12][1])
    r = byk[k]
    pmp = pm25(res.beta_Mm, r["rh"], alpha, g)
    a.set_title(f"{title}\ncamera: {res.beta_Mm:.0f} Mm⁻¹ → PM2.5 {pmp:.1f} ({category(pmp)})   |   "
                f"monitor: {r['monitor_pm25']:.1f}  ·  site ext. {r['site_beta']:.0f} Mm⁻¹", fontsize=9, color=col)
    axf.plot(DIST[keep] / 1000, full.I[keep], "o", color=col, ms=7)
    axf.plot(DIST[~keep] / 1000, full.I[~keep], "o", mfc="none", color=col, ms=7)
    dd = np.linspace(0, 66e3, 300); J = np.median(res.gain * res.J)
    axf.plot(dd / 1000, res.A + (J - res.A) * np.exp(-res.beta_per_m * dd), "-", color=col, lw=1.6,
             label=f"{title}: fitted extinction {res.beta_Mm:.0f} Mm⁻¹")
for i, n in enumerate(NAMES):
    axf.annotate(n, (DIST[i] / 1000, 0.005), fontsize=7, rotation=55, ha="left", color="#555")
axf.set_xlabel("distance to ridge, NPS landmark chart (km)"); axf.set_ylabel("ridge brightness (linear)")
axf.set_ylim(0, 0.45); axf.grid(alpha=0.3); axf.legend(fontsize=8, loc="lower right")
axf.set_title("C. Per-ridge brightness and fit. all 9 chart ridges used (windowed band selection was tested and reverted)", fontsize=9)
fig.text(0.5, 0.005, NOTE, ha="center", fontsize=7.5, style="italic")
fig.tight_layout(rect=(0, 0.02, 1, 1)); fig.savefig(OUT / "chart_C_clear_vs_smoke.png", dpi=140); plt.close(fig)
print("charts written to", OUT)
