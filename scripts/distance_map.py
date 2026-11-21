"""Per-pixel distance (m) for the Look Rock view: DA3 depth ordering mapped onto the
NPS chart distances through the 9 labelled ridges (monotone interpolation in log space),
plus a sky mask. Saves out/depth/lookrock_distance_m.npy and lookrock_sky.npy.
"""
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import binary_opening, label, median_filter
from sklearn.isotonic import IsotonicRegression

from pluma.regions_lookrock import LANDMARKS, MILE

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "out/depth"
da3 = np.load(D / "lookrock_da3.npy")
rgb = np.asarray(Image.open(ROOT / "data/frames/lookrock/grsm_20161120_1200.jpg").convert("RGB"), float) / 255
H, W = da3.shape

# --- sky: bluish, smooth, connected to the top edge, above the skyline zone
b_r = rgb[..., 2] - rgb[..., 0]
grad = np.abs(np.gradient(median_filter(rgb.mean(2), 3))[0])
cand = (b_r > 0.18) & (grad < 0.01)
cand[430:] = False
lab, _ = label(binary_opening(cand, iterations=2))
top = set(np.unique(lab[0])) - {0}
sky = np.isin(lab, list(top))
# fill holes column-wise: sky is everything above its lowest contiguous run from the top
for x in range(W):
    col = sky[:, x]
    if col[0]:
        stop = np.argmin(col) if not col.all() else H
        sky[:stop, x] = True
        sky[stop:, x] = False

# --- distance: isotonic map from DA3 value -> log(chart distance) using ridge medians
names = list(LANDMARKS)
xs = np.array([np.median(da3[y0:y1, x0:x1]) for _, (_, (x0, x1, y0, y1)) in LANDMARKS.items()])
ys = np.log(np.array([LANDMARKS[n][0] * MILE for n in names]))
iso = IsotonicRegression(increasing=True, out_of_bounds="clip").fit(xs, ys)
# extend below the nearest ridge: foreground tree tops ~40 m at the lowest DA3 value
x_lo = float(da3[~sky].min())
xs_ext = np.concatenate([[x_lo], np.sort(xs)])
ys_ext = np.concatenate([[np.log(40.0)], iso.predict(np.sort(xs))])
dist = np.exp(np.interp(da3, xs_ext, ys_ext)).astype(np.float32)
dist[sky] = np.inf
np.save(D / "lookrock_distance_m.npy", dist)
np.save(D / "lookrock_sky.npy", sky)
fit_err = np.exp(iso.predict(xs)) / np.exp(ys) - 1
print("ridge fit error after isotonic map:", dict(zip(names, np.round(fit_err, 2))))
print("sky fraction", sky.mean().round(3), "distance range m", np.nanmin(dist[~sky]).round(0), np.nanmax(dist[~sky]).round(0))

import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
v = np.log10(np.where(sky, np.nan, dist))
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
ax[0].imshow(rgb); ax[0].contour(sky, [0.5], colors="cyan", linewidths=0.8); ax[0].axis("off"); ax[0].set_title("sky mask")
im = ax[1].imshow(v, cmap="viridis"); ax[1].axis("off"); ax[1].set_title("log10 distance (m)"); plt.colorbar(im, ax=ax[1])
fig.tight_layout(); fig.savefig(D / "distance_check.png", dpi=90)
