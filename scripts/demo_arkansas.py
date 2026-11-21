"""Chart D: ARDOT camera 9004 (Hwy 16, eastbound, 2,215 ft; probably Edwards Junction) single frame.

No clear reference frame -> absolute form (sec 3.1). Depth bands from DA3 ordering,
scale anchored by two skyline ridges from USGS 3DEP elevations along the view
(5.5 km, 14 km) plus the roadside tree slope (~0.1 km, estimated, not map-measured).
PM2.5 uses the November Look Rock alpha unchanged. RH unknown -> assumed 50%.
Preliminary: one frame, no local monitor to check against.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy.stats import theilslopes

from pluma.haze.fit import srgb_to_linear, luminance
from pluma.convert import pm25, category, fit_alpha_g, pm_range

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/arkansas"
rgb8 = np.asarray(Image.open(ROOT / "data/frames/ardot/ardot_9004_crop.png").convert("RGB"))
img = luminance(srgb_to_linear(rgb8 / 255.0))
da3 = np.load(OUT / "ardot_da3.npy")
H, W = img.shape

# landscape region: right half (valley view), below the sky, excluding logo and road
land = np.zeros((H, W), bool); land[30:250, 300:W] = True
land[0:50, 425:530] = False                       # ARDOT logo
sky = np.zeros((H, W), bool); sky[2:14, 300:425] = True

# DA3 depth quintiles inside the landscape region -> 5 bands
v = da3[land]
qs = np.quantile(v, [0, .2, .4, .6, .8, 1.0])
bands = [land & (da3 >= qs[i]) & (da3 <= qs[i + 1]) for i in range(5)]
band_da3 = np.array([np.median(da3[b]) for b in bands])

# anchors: (DA3 value, true distance km)
anchors = [(np.median(da3[bands[0]]), 0.1),      # nearest quintile = roadside tree slope, estimated
           (np.median(da3[bands[3]]), 5.5),      # USGS skyline ridge at 5.5 km (heading 100 deg)
           (np.median(da3[bands[4]]), 14.0)]     # USGS skyline ridge at 14 km
ax_, ay_ = np.log([a[0] for a in anchors]), np.log([a[1] for a in anchors])
b, ln_a = np.polyfit(ax_, ay_, 1)
dist_km = np.exp(ln_a) * band_da3 ** b

A = np.median(img[sky])
I = np.array([np.median(img[m]) for m in bands])
ok = (A - I) > 0
y = np.log(A - I[ok]); d = dist_km[ok] * 1000
slope, icpt, lo, hi = theilslopes(y, d)
beta, beta_lo, beta_hi = -slope * 1e6, -hi * 1e6, -lo * 1e6
r2 = np.corrcoef(d, y)[0, 1] ** 2

# November Look Rock calibration, unchanged
h = json.loads((ROOT / "out/demo/headline.json").read_text())
alpha, g = h["alpha"], h["g_fixed"]
rows = json.loads((ROOT / "out/demo/rows.json").read_text())
tr = [r for r in rows if r["gate"] == "pass" and r["split"] == "train" and r["monitor_pm25"] is not None]
_, _, q = fit_alpha_g([r["cam_beta"] for r in tr], [r["rh"] for r in tr], [r["monitor_pm25"] for r in tr], fix_g=g)
RH = 50.0
pm = float(pm25(beta, RH, alpha, g))
pm_lo = float(pm_range(pm25(max(beta_lo, 0), RH, alpha, g), q)[0])
pm_hi = float(pm_range(pm25(beta_hi, RH, alpha, g), q)[1])
res = dict(beta_Mm=beta, beta_ci=[beta_lo, beta_hi], fit_r2=r2, pm25=pm, pm25_range=[pm_lo, pm_hi],
           category=category(pm), category_range=[category(pm_lo), category(pm_hi)],
           band_distances_km=dist_km.tolist(), band_I=I.tolist(), A=A, rh_assumed=RH, alpha=alpha, g=g,
           anchors=dict(near_km=0.1, near_source="estimated roadside slope", ridges_km=[5.5, 14.0],
                        ridges_source="USGS 3DEP point elevations along heading 100 deg from 35.8482,-93.3616"))
print(json.dumps(res, indent=1))
(OUT / "arkansas_result.json").write_text(json.dumps(res, indent=1, default=float))

fig = plt.figure(figsize=(14, 5.6)); gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1.15, 1])
a = fig.add_subplot(gs[0]); a.imshow(rgb8); a.set_title("ARDOT camera 9004, Hwy 16 eastbound (saved frame)", fontsize=9); a.axis("off")
a = fig.add_subplot(gs[1]); a.imshow(rgb8)
cols = plt.cm.viridis(np.linspace(0, 1, 5))
ov = np.zeros((H, W, 4))
for i, m in enumerate(bands):
    ov[m] = (*cols[i][:3], 0.55)
ov[sky] = (0, 1, 1, 0.6)
a.imshow(ov); a.axis("off")
a.set_title("DA3 depth bands (5) + sky band (cyan)\n" + ", ".join(f"{x:.1f}" for x in dist_km) + " km", fontsize=9)
a = fig.add_subplot(gs[2])
a.plot(dist_km, np.log(np.maximum(A - I, 1e-4)), "o", color="#e07b00")
xx = np.linspace(0, dist_km.max() * 1.05, 50)
a.plot(xx, icpt + slope * xx * 1000, "-", color="#e07b00")
a.set_xlabel("band distance (km, DA3 + map anchors)"); a.set_ylabel("ln(A - I)")
a.set_title(f"Absolute fit: extinction {beta:.0f} Mm⁻¹ (CI {beta_lo:.0f}-{beta_hi:.0f}), r²={r2:.2f}\n"
            f"PM2.5 ≈ {pm:.0f} µg/m³, range {pm_lo:.0f}-{pm_hi:.0f}  →  {category(pm)}", fontsize=9)
a.grid(alpha=0.3)
fig.suptitle("D. Arkansas: single frame, preliminary, no local monitor to check against", fontsize=12, color="#b3261e")
fig.text(0.5, 0.01, "Calibration: November Look Rock alpha unchanged. RH assumed 50% (no reading). Ridge anchors from USGS elevations; near anchor estimated. "
         "Nearest regulatory monitor: Springdale, 77 km. ARDOT permission needed for any automated use.", ha="center", fontsize=7.5, style="italic")
fig.tight_layout(rect=(0, 0.04, 1, 0.95)); fig.savefig(OUT / "chart_D_arkansas.png", dpi=140)
print("wrote", OUT / "chart_D_arkansas.png")
