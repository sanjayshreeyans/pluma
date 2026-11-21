"""Animated GIF (1280x720): photo | live sight map | numbers, with a timeline.

Sight map: for every pixel, the share of light that survives the path to the camera,
t = exp(-beta * d), using that frame's fitted camera extinction (beta) and the per-pixel
distance (DA3 ordering pinned to the NPS chart ridges; approximate). The dashed line
is the camera's visual range (t = 2%, 3.912 / beta). Values from out/demo/rows.json,
nothing smoothed. Run: PYTHONPATH=. uv run python scripts/make_gif.py
"""
import datetime as dt
import io
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch
import numpy as np
from PIL import Image

from pluma.regions_lookrock import LANDMARKS, MILE

ROOT = Path(__file__).resolve().parents[1]
FR, OUT = ROOT / "data/frames/lookrock", ROOT / "out/video_handoff"
rows = [r for r in json.loads((ROOT / "out/demo/rows.json").read_text())
        if r["gate"] == "pass" and r.get("pred_pm25") is not None and r["monitor_pm25"] is not None]
rows.sort(key=lambda r: r["timestamp"])
t_ax = [dt.datetime.fromisoformat(r["timestamp"][:16]) for r in rows]
pred = np.array([r["pred_pm25"] for r in rows]); mon = np.array([r["monitor_pm25"] for r in rows])
SPLIT = dt.datetime(2016, 11, 19)

dist = np.load(ROOT / "out/depth/lookrock_distance_m.npy")[200:720]
sky = np.load(ROOT / "out/depth/lookrock_sky.npy")[200:720]

# ---------- style ----------
BG, PANEL, LINE = "#0b0f17", "#131a27", "#243047"
INK, MUTE, FAINT = "#eef2f7", "#8a96a8", "#4a5568"
CAM, MON = "#ff9a4d", "#5fb3ff"
F, FB = "Avenir Next", "Avenir Next Demi Bold"
SIGHT = LinearSegmentedColormap.from_list("sight", ["#0b0f17", "#1d2b4a", "#2f6f8f", "#5fc2b0", "#d9f2c4", "#fff8e8"])
CATS = [(0, 9, "Good", "#3fb950"), (9, 35.4, "Moderate", "#e3b341"), (35.4, 55.4, "USG", "#f0883e"),
        (55.4, 125.4, "Unhealthy", "#f85149"), (125.4, 225.4, "Very unh.", "#a371f7")]
CAT_COL = {"Good": "#3fb950", "Moderate": "#e3b341", "Unhealthy for sensitive groups": "#f0883e",
           "Unhealthy": "#f85149", "Very unhealthy": "#a371f7", "Hazardous": "#b62324"}
plt.rcParams.update({"font.family": F, "text.color": INK, "axes.labelcolor": MUTE,
                     "xtick.color": MUTE, "ytick.color": MUTE, "axes.edgecolor": LINE})


def scale_x(pm):
    """Piecewise-linear AQI scale: each category gets equal width."""
    for k, (lo, hi, _, _) in enumerate(CATS):
        if pm <= hi:
            return (k + (pm - lo) / (hi - lo)) / len(CATS)
    return 1.0


def panel(fig, x, y, w, h):
    fig.patches.append(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.012",
                                      transform=fig.transFigure, fc=PANEL, ec=LINE, lw=0.8, zorder=-1))


LABEL_RIDGES = ["Happy Valley Ridge", "Rich Mtn", "Thunderhead Mtn", "Clingmans Dome"]

frames = []
for i, r in enumerate(rows):
    beta = r["cam_beta"] * 1e-6
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor=BG)

    # header
    fig.text(0.035, 0.935, "P L U M A", fontsize=11, color=CAM, family=FB)
    fig.text(0.035, 0.885, "Look Rock, Great Smoky Mountains", fontsize=20, color=INK, family=FB)
    fig.text(0.965, 0.905, t_ax[i].strftime("%a %d %b %Y  ·  %H:%M EST"), fontsize=15, color=INK, ha="right")
    pill = "UNSEEN DAY" if r["split"] == "test" else "CALIBRATION DAY"
    fig.text(0.965, 0.865, pill, fontsize=9, color=CAM if r["split"] == "test" else MUTE, ha="right", family=FB,
             bbox=dict(boxstyle="round,pad=0.35", fc=BG, ec=CAM if r["split"] == "test" else FAINT, lw=0.8))

    # photo
    panel(fig, 0.025, 0.39, 0.36, 0.44)
    ax = fig.add_axes([0.035, 0.405, 0.34, 0.37])
    ax.imshow(np.asarray(Image.open(FR / r["file"]).convert("RGB"))[200:720]); ax.axis("off")
    fig.text(0.035, 0.795, "WHAT THE CAMERA SEES", fontsize=9, color=MUTE, family=FB)

    # live sight map
    panel(fig, 0.395, 0.39, 0.36, 0.44)
    ax = fig.add_axes([0.405, 0.405, 0.34, 0.37])
    tmap = np.exp(-beta * dist)
    ax.imshow(np.where(sky, np.nan, tmap), cmap=SIGHT, vmin=0, vmax=1, interpolation="bilinear")
    ax.imshow(np.where(sky, 1.0, np.nan), cmap=LinearSegmentedColormap.from_list("s", [BG, BG]), alpha=1)
    vr = 3.912 / beta
    if np.nanmax(np.where(sky, 0, dist)) > vr:
        ax.contour(np.where(sky, np.nan, dist), [vr], colors=[CAM], linewidths=1.3, linestyles="--")
    for n in LABEL_RIDGES:
        mi, (x0, x1, y0, y1) = LANDMARKS[n]
        tt = np.exp(-beta * mi * MILE)
        ax.text((x0 + x1) / 2, y0 - 200 - 6, f"{mi} mi · {tt:.0%}", fontsize=8, color=INK, ha="center",
                family=FB, bbox=dict(boxstyle="round,pad=0.2", fc=BG, ec="none", alpha=0.65))
    ax.axis("off")
    fig.text(0.405, 0.795, "SIGHT MAP · light surviving the haze", fontsize=9, color=MUTE, family=FB)
    fig.text(0.745, 0.795, f"visual range {vr/1000:.0f} km", fontsize=9, color=CAM, ha="right", family=FB)

    # numbers card
    panel(fig, 0.765, 0.39, 0.21, 0.44)
    fig.text(0.78, 0.795, "PM2.5  µg/m³", fontsize=9, color=MUTE, family=FB)
    fig.text(0.78, 0.74, "Camera", fontsize=12, color=CAM)
    fig.text(0.962, 0.72, f"{r['pred_pm25']:.1f}", fontsize=34, color=CAM, ha="right", family=FB)
    fig.text(0.78, 0.655, "Monitor", fontsize=12, color=MON)
    fig.text(0.962, 0.635, f"{r['monitor_pm25']:.1f}", fontsize=34, color=MON, ha="right", family=FB)
    d = r["pred_pm25"] - r["monitor_pm25"]
    fig.text(0.78, 0.585, f"difference  {d:+.1f}", fontsize=11, color=INK)
    # AQI scale bar
    bx = fig.add_axes([0.78, 0.50, 0.18, 0.05]); bx.set_xlim(0, 1); bx.set_ylim(0, 1); bx.axis("off")
    for k, (_, _, nm, col) in enumerate(CATS):
        bx.add_patch(plt.Rectangle((k / 5 + 0.004, 0.38), 1 / 5 - 0.008, 0.24, color=col, alpha=0.85))
    bx.plot(scale_x(r["pred_pm25"]), 0.82, "v", color=CAM, ms=9, clip_on=False)
    bx.plot(scale_x(r["monitor_pm25"]), 0.18, "^", color=MON, ms=9, clip_on=False)
    c1, c2 = r["category"], r["monitor_category"]
    fig.text(0.78, 0.47, c1.replace("Unhealthy for sensitive groups", "USG"), fontsize=10, color=CAT_COL[c1], family=FB)
    fig.text(0.962, 0.47, c2.replace("Unhealthy for sensitive groups", "USG"), fontsize=10, color=CAT_COL[c2], ha="right", family=FB)
    fig.text(0.871, 0.47, "=" if c1 == c2 else "≠", fontsize=11, color=INK if c1 == c2 else MUTE, ha="center")
    sv = 3912.0 / r["site_beta"] if r["site_beta"] else None
    fig.text(0.78, 0.415, "Visibility", fontsize=9, color=MUTE, family=FB)
    fig.text(0.962, 0.415, f"cam {vr/1000:.0f} km · site {sv:.0f} km" if sv else f"cam {vr/1000:.0f} km",
             fontsize=10, color=INK, ha="right")

    # timeline
    panel(fig, 0.025, 0.07, 0.95, 0.295)
    ax = fig.add_axes([0.06, 0.105, 0.9, 0.215], facecolor=PANEL)
    for lo, hi, nm, col in CATS[:4]:
        if hi < max(pred.max(), mon.max()):
            ax.axhline(hi, color=col, lw=0.8, alpha=0.35, ls=(0, (2, 3)))
            ax.text(t_ax[-1] + dt.timedelta(hours=5), hi, nm, color=col, fontsize=7, va="bottom", ha="right", alpha=0.8)
    ax.plot(t_ax, mon, color=MON, lw=1, alpha=0.18); ax.plot(t_ax, pred, color=CAM, lw=1, alpha=0.18)
    for arr, col in [(mon, MON), (pred, CAM)]:
        ax.plot(t_ax[:i + 1], arr[:i + 1], color=col, lw=5, alpha=0.15, solid_capstyle="round")
        ax.plot(t_ax[:i + 1], arr[:i + 1], color=col, lw=1.8, solid_capstyle="round")
    ax.plot([t_ax[i]] * 2, [mon[i], pred[i]], color=INK, lw=1)
    ax.plot(t_ax[i], mon[i], "o", color=MON, ms=7, mec=BG, mew=1.5)
    ax.plot(t_ax[i], pred[i], "o", color=CAM, ms=7, mec=BG, mew=1.5)
    ax.axvline(SPLIT, color=FAINT, ls=(0, (3, 3)), lw=1)
    top = max(pred.max(), mon.max())
    ax.text(SPLIT, top * 0.92, "  calibrated  |  unseen  ", color=MUTE, fontsize=8, ha="center",
            bbox=dict(boxstyle="round,pad=0.25", fc=PANEL, ec="none"))
    ax.set_ylim(0, top * 1.05)
    ax.set_xlim(t_ax[0] - dt.timedelta(hours=6), t_ax[-1] + dt.timedelta(hours=6))
    for s in ["top", "right"]: ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]: ax.spines[s].set_color(LINE)
    ax.tick_params(labelsize=8, length=0)
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.text(0.0, 1.03, "— camera", color=CAM, fontsize=9, transform=ax.transAxes, family=FB)
    ax.text(0.09, 1.03, "— NPS on-site monitor", color=MON, fontsize=9, transform=ax.transAxes, family=FB)

    fig.text(0.035, 0.025, "Reference: NPS on-site TEOM (not an EPA file; can read low in heavy smoke). Calibration fitted 8–18 Nov only. "
             "Sight map distances approximate (DA3 pinned to NPS chart ridges). Values as measured.", fontsize=7.5, color=FAINT)

    buf = io.BytesIO(); fig.savefig(buf, format="png", facecolor=BG); plt.close(fig)
    frames.append(Image.open(buf).convert("RGB"))

# shared palette from a mix of frames (clear + smoky) for stable colours
mix = Image.new("RGB", (frames[0].width, frames[0].height * 3))
for k, idx in enumerate([0, len(frames) // 2, len(frames) - 1]):
    mix.paste(frames[idx], (0, k * frames[0].height))
pal = mix.quantize(colors=240, method=Image.Quantize.MEDIANCUT)
q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
dur = [520] * len(q); dur[-1] = 3000
q[0].save(OUT / "pluma_ground_truth.gif", save_all=True, append_images=q[1:], duration=dur, loop=0, optimize=True)
for key, name in [("20161126_1200", "gif_still_26nov.png"), ("20161108_1200", "gif_still_08nov.png"), ("20161129_1200", "gif_still_29nov.png")]:
    k = [j for j, r in enumerate(rows) if r["key"] == key]
    if k:
        frames[k[0]].save(OUT / name)
print("frames", len(q), "->", OUT / "pluma_ground_truth.gif", round((OUT / "pluma_ground_truth.gif").stat().st_size / 1e6, 1), "MB")
