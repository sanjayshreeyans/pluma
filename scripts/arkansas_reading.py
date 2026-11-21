"""Single-frame PM2.5 reading for an Arkansas road camera with the Look Rock November
calibration unchanged (absolute form, no reference frame).

Depth bands: DA3 depth quintiles inside the landscape region. Scale: power law through
anchors = USGS-profile ridge distances along the view heading (map) + one estimated
near distance. RH from the nearest METAR. Output JSON + overlay PNGs for the site.
Usage: arkansas_reading.py CONFIG.json
"""
import json, sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.stats import theilslopes

from pluma.haze.fit import srgb_to_linear, luminance
from pluma.haze.gate import sky_texture
from pluma.convert import pm25, category, fit_alpha_g, pm_range

ROOT = Path(__file__).resolve().parents[1]
cfg = json.loads(Path(sys.argv[1]).read_text())
rgb8 = np.asarray(Image.open(ROOT / cfg["frame"]).convert("RGB"))
img = luminance(srgb_to_linear(rgb8 / 255.0))
da3 = np.load(ROOT / cfg["da3"])
H, W = img.shape

land = np.zeros((H, W), bool)
x0, x1, y0, y1 = cfg["land"]; land[y0:y1, x0:x1] = True
for bx0, bx1, by0, by1 in cfg.get("exclude", []):
    land[by0:by1, bx0:bx1] = False
sky = np.zeros((H, W), bool)
x0, x1, y0, y1 = cfg["sky"]; sky[y0:y1, x0:x1] = True

NB = 5
qs = np.quantile(da3[land], np.linspace(0, 1, NB + 1))
bands = [land & (da3 >= qs[i]) & (da3 <= qs[i + 1]) for i in range(NB)]
band_da3 = np.array([np.median(da3[b]) for b in bands])

anc = cfg["anchors"]  # list of [band_index, km, source]
b, ln_a = np.polyfit(np.log([band_da3[i] for i, _, _ in anc]), np.log([km for _, km, _ in anc]), 1)
dist_km = np.exp(ln_a) * band_da3 ** b

A = np.median(img[sky])
I = np.array([np.median(img[m]) for m in bands])
ok = (A - I) > 0
y = np.log(A - I[ok]); d = dist_km[ok] * 1000
slope, icpt, lo, hi = theilslopes(y, d)
beta, beta_lo, beta_hi = -slope * 1e6, max(-hi * 1e6, 0.0), -lo * 1e6
r2 = float(np.corrcoef(d, y)[0, 1] ** 2) if ok.sum() > 2 else float("nan")

h = json.loads((ROOT / "out/demo/headline.json").read_text())
alpha, g = h["alpha"], h["g_fixed"]
rows = json.loads((ROOT / "out/demo/rows.json").read_text())
tr = [r for r in rows if r["gate"] == "pass" and r["split"] == "train" and r["monitor_pm25"] is not None]
_, _, q = fit_alpha_g([r["cam_beta"] for r in tr], [r["rh"] for r in tr], [r["monitor_pm25"] for r in tr], fix_g=g)
RH = cfg["rh"]
pm = float(pm25(beta, RH, alpha, g))
pm_lo = float(pm_range(pm25(beta_lo, RH, alpha, g), q)[0])
pm_hi = float(pm_range(pm25(beta_hi, RH, alpha, g), q)[1])
tex = sky_texture(rgb8 / 255.0, slice(cfg["sky"][2], cfg["sky"][3]))

res = dict(camera=cfg["camera"], frame=cfg["frame"], taken=cfg["taken"], heading=cfg["heading"],
           extinction_Mm=beta, extinction_ci=[beta_lo, beta_hi], fit_r2=r2, visual_range_km=3912 / beta if beta > 0 else None,
           pm25=pm, pm25_range=[pm_lo, pm_hi], category=category(pm),
           category_range=[category(pm_lo), category(pm_hi)],
           bands=[dict(km=float(k), brightness=float(i), used=bool(o)) for k, i, o in zip(dist_km, I, ok)],
           sky_brightness=float(A), rh=RH, rh_source=cfg["rh_source"], alpha=alpha, g=g,
           anchors=[dict(band=i, km=km, source=s) for i, km, s in anc], sky_texture=tex, cloud_gate_pass=tex <= 12.0,
           nearest_monitor=cfg["nearest_monitor"])
print(json.dumps(res, indent=1, default=float))
out = ROOT / cfg["out"]
out.mkdir(parents=True, exist_ok=True)
(out / "reading.json").write_text(json.dumps(res, indent=1, default=float))
Image.fromarray(rgb8).save(out / "frame.jpg", quality=90)

# depth map in the site ramp: per-pixel distance from DA3 through the fitted power law
from matplotlib.colors import LinearSegmentedColormap
ramp = LinearSegmentedColormap.from_list("site", ["#fff8e8", "#d9f2c4", "#5fc2b0", "#2f6f8f", "#1d2b4a", "#0b0f17"])
dmap = np.exp(ln_a) * np.clip(da3, 1e-6, None) ** b
ld = np.log10(dmap)
lo_, hi_ = np.percentile(ld[land], [2, 98])
x = np.clip((ld - lo_) / (hi_ - lo_ + 1e-9), 0, 1)
hz = cfg.get("horizon_row")
if hz:
    x[:hz] = 1.0            # sky above the horizon: infinitely far
Image.fromarray((ramp(x)[..., :3] * 255).astype(np.uint8)).save(out / "depth.jpg", quality=90)
res_scale = dict(power_law_a=float(np.exp(ln_a)), power_law_b=float(b))
r2 = json.loads((out / "reading.json").read_text()); r2["scale"] = res_scale
(out / "reading.json").write_text(json.dumps(r2, indent=1, default=float))
