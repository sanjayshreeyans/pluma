"""Predicted PM2.5 for every saved frame of an Arkansas camera (no ground truth).

Per camera: DA3 depth on the first frame -> 5 depth bands + distance scale (power law
through terrain-ridge anchors). Per frame: absolute haze fit (sky band for A), the
November Look Rock calibration unchanged, and the same refusal rules as Look Rock:
no reading if broken cloud, haze below the clean-air floor, or a poor fit.
Writes site/arkansas/<cam>/series.json, frames, depth.jpg, distance.png.
Usage: arkansas_series.py data/cameras/<cam>.json
"""
import json, shutil, sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.stats import theilslopes
from matplotlib.colors import LinearSegmentedColormap

from pluma.haze.fit import srgb_to_linear, luminance
from pluma.haze.gate import sky_texture
from pluma.convert import pm25, category, fit_alpha_g, pm_range, BETA_AIR

ROOT = Path(__file__).resolve().parents[1]
cfg = json.loads(Path(sys.argv[1]).read_text())
out = ROOT / cfg["out"]; (out / "frames").mkdir(parents=True, exist_ok=True)
da3 = np.load(ROOT / cfg["da3"])
H, W = da3.shape

land = np.zeros((H, W), bool); x0, x1, y0, y1 = cfg["land"]; land[y0:y1, x0:x1] = True
for bx0, bx1, by0, by1 in cfg.get("exclude", []):
    land[by0:by1, bx0:bx1] = False
sky = np.zeros((H, W), bool); x0, x1, y0, y1 = cfg["sky"]; sky[y0:y1, x0:x1] = True

qs = np.quantile(da3[land], np.linspace(0, 1, 6))
bands = [land & (da3 >= qs[i]) & (da3 <= qs[i + 1]) for i in range(5)]
band_da3 = np.array([np.median(da3[b]) for b in bands])
anc = cfg["anchors"]
b_pow, ln_a = np.polyfit(np.log([band_da3[i] for i, _, _ in anc]), np.log([km for _, km, _ in anc]), 1)
dist_km = np.exp(ln_a) * band_da3 ** b_pow
dmap_m = np.exp(ln_a) * np.clip(da3, 1e-6, None) ** b_pow * 1000

# distance PNG for the browser sight map (same encoding as Look Rock), sky = 0
LO, HI = np.log10(30), np.log10(70000)
v = np.clip((np.log10(dmap_m) - LO) / (HI - LO), 0, 1) * 254 + 1
hz = cfg.get("horizon_row")
skymask = np.zeros((H, W), bool)
if hz: skymask[:hz] = True
v[skymask] = 0
Image.fromarray(v.astype(np.uint8)).save(out / "distance.png")
ramp = LinearSegmentedColormap.from_list("site", ["#fff8e8", "#d9f2c4", "#5fc2b0", "#2f6f8f", "#1d2b4a", "#0b0f17"])
ld = np.log10(dmap_m); lo_, hi_ = np.percentile(ld[land], [2, 98])
x = np.clip((ld - lo_) / (hi_ - lo_ + 1e-9), 0, 1); x[skymask] = 1
Image.fromarray((ramp(x)[..., :3] * 255).astype(np.uint8)).save(out / "depth.jpg", quality=90)

h = json.loads((ROOT / "out/demo/headline.json").read_text())
alpha, g = h["alpha"], h["g_fixed"]
rows = json.loads((ROOT / "out/demo/rows.json").read_text())
tr = [r for r in rows if r["gate"] == "pass" and r["split"] == "train" and r["monitor_pm25"] is not None]
_, _, q = fit_alpha_g([r["cam_beta"] for r in tr], [r["rh"] for r in tr], [r["monitor_pm25"] for r in tr], fix_g=g)

series = []
for f in cfg["frames"]:
    rgb8 = np.asarray(Image.open(ROOT / f["file"]).convert("RGB"))
    if rgb8.shape[:2] != (H, W):
        rgb8 = np.asarray(Image.fromarray(rgb8).resize((W, H)))
    img = luminance(srgb_to_linear(rgb8 / 255.0))
    A = np.median(img[sky]); I = np.array([np.median(img[m]) for m in bands])
    ok = (A - I) > 0
    beta = beta_lo = beta_hi = r2 = None
    if ok.sum() >= 3:
        yv = np.log(A - I[ok]); dv = dist_km[ok] * 1000
        sl, ic, lo, hi = theilslopes(yv, dv)
        beta, beta_lo, beta_hi = -sl * 1e6, max(-hi * 1e6, 0.0), -lo * 1e6
        r2 = float(np.corrcoef(dv, yv)[0, 1] ** 2)
    # horizon-strip evenness: spread of 16 column-chunk medians / mean. Threshold 0.20 = 95th
    # percentile of Look Rock frames that passed the gates (set on Look Rock, not on Arkansas).
    strip = img[sky].reshape(cfg["sky"][3] - cfg["sky"][2], cfg["sky"][1] - cfg["sky"][0])
    ch = np.array([np.median(c) for c in np.array_split(strip, 16, axis=1)])
    tex = float(ch.std() / ch.mean())
    reasons = []
    if tex > 0.20: reasons.append(f"the sky along the horizon is uneven (cloud or glare, spread {tex:.2f})")
    if beta is None: reasons.append("too few ridges darker than the sky")
    elif beta < BETA_AIR: reasons.append(f"the haze came out below the clean-air floor ({beta:.1f} vs {BETA_AIR:.0f} Mm⁻¹)")
    if r2 is not None and r2 < 0.7: reasons.append(f"the ridges don't line up on one haze curve (fit {r2:.2f})")
    name = Path(f["file"]).name.replace(".png", ".jpg")
    Image.fromarray(rgb8).save(out / "frames" / name, quality=90)
    e = dict(file=f"frames/{name}", taken=f["taken"], rh=f["rh"], rh_source=f["rh_source"], horizon_spread=tex,
             extinction_Mm=beta, extinction_ci=[beta_lo, beta_hi], fit_r2=r2, status="reading" if not reasons else "no reading",
             reasons=reasons)
    if beta is not None:
        pm = float(pm25(beta, f["rh"], alpha, g))
        e.update(pm25=pm, category=category(pm),
                 pm25_range=[float(pm_range(pm25(beta_lo, f["rh"], alpha, g), q)[0]), float(pm_range(pm25(beta_hi, f["rh"], alpha, g), q)[1])],
                 visual_range_km=3912 / beta if beta > 0 else None)
    series.append(e)
    print(f["taken"], e["status"], f"ext {beta:.1f}" if beta is not None else "", f"PM {e.get('pm25', float('nan')):.1f}", "|", "; ".join(reasons))

meta = dict(camera=cfg["camera"], short=cfg["short"], lat=cfg["lat"], lon=cfg["lon"], elevation_ft=cfg["elevation_ft"], heading=cfg["heading"], nearest_monitor=cfg["nearest_monitor"],
            bands_km=dist_km.tolist(), anchors=[dict(band=i, km=km, source=s) for i, km, s in anc],
            scale=dict(a=float(np.exp(ln_a)), b=float(b_pow)), alpha=alpha, g=g,
            distance_encoding=dict(log10_min=LO, log10_max=HI, sky=0), size=[W, H], series=series)
(out / "series.json").write_text(json.dumps(meta, indent=1, default=float))
