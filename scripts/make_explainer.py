"""Method explainer animation (1280x720, 24 fps) in the site's style, from real Look Rock data.

Speech: measure how faded each ridge is -> plot against distance -> straight line ->
steeper line = dirtier air -> convert to PM2.5.
Data: out/video_handoff/explainer_data.json (29 Nov clear, 8 Nov heavy smoke; each vs the
20 Nov reference). Run: PYTHONPATH=. uv run python scripts/make_explainer.py
"""
import json, subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch
import numpy as np
from PIL import Image

from pluma.regions_lookrock import LANDMARKS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/video_handoff"
for f in (ROOT / "data/fonts").glob("*.ttf"):
    font_manager.fontManager.addfont(str(f))
plt.rcParams.update({"font.family": "Schibsted Grotesk", "font.size": 14})

PAPER, SURFACE, INK, INK2, INK3, RULE = "#f4f5f2", "#ffffff", "#16191c", "#4a5157", "#5d656b", "#d9dcd6"
CLEAR, SMOKE, SKY = "#0a6db6", "#9b3434", "#2b9be6"
D = json.loads((OUT / "explainer_data.json").read_text())
C, S = D["20161129_1200"], D["20161108_1200"]
photo_c = np.asarray(Image.open(ROOT / "data/frames/lookrock/grsm_20161129_1200.jpg").convert("RGB"))[200:720]
photo_s = np.asarray(Image.open(ROOT / "data/frames/lookrock/grsm_20161108_1200.jpg").convert("RGB"))[200:720]

FPS, DUR = 24, 13.0
N = int(FPS * DUR)
FLOOR = 0.006           # below this a ridge has vanished into the haze
ease = lambda x: 0.5 - 0.5 * np.cos(np.pi * np.clip(x, 0, 1))
seg = lambda t, a, b: ease((t - a) / (b - a))

STEPS = [(0.0, "Measure how faded each ridge is"), (2.6, "Plot fading against distance"),
         (5.4, "The points fall on a straight line"), (7.2, "A steeper line means dirtier air"),
         (10.0, "The slope becomes a PM2.5 number")]

W, H = 1280, 720
proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS),
                         "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "slow", "-movflags", "+faststart",
                         str(OUT / "pluma_method_explainer.mp4")], stdin=subprocess.PIPE)
gif_frames = []

for k in range(N):
    t = k / FPS
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor=PAPER)
    # step caption
    si = max(i for i, (a, _) in enumerate(STEPS) if t >= a)
    a0, txt = STEPS[si]
    al = seg(t, a0, a0 + 0.4)
    fig.text(0.045, 0.905, f"{si + 1}", fontsize=15, color=SKY, weight=700, alpha=al)
    fig.text(0.075, 0.9, txt, fontsize=27, color=INK, weight=650, alpha=al)
    fig.text(0.045, 0.06, "Look Rock, Great Smoky Mountains · distances from the National Park Service ridge chart", fontsize=12, color=INK3)

    # sheets
    for x0 in (0.045, 0.52):
        fig.patches.append(FancyBboxPatch((x0, 0.13), 0.435, 0.70, boxstyle="round,pad=0,rounding_size=0.01",
                                          transform=fig.transFigure, fc=SURFACE, ec=RULE, lw=1, zorder=-1))
    # photo (crossfade clear -> smoke)
    mix = seg(t, 7.2, 8.0)
    ax = fig.add_axes([0.06, 0.2, 0.405, 0.56]); ax.axis("off")
    fade = 1 - seg(t, 10.0, 10.6)
    ax.imshow((photo_c * (1 - mix) + photo_s * mix).astype(np.uint8), alpha=fade)
    day = "29 Nov 2016, clear" if mix < 0.5 else "8 Nov 2016, wildfire smoke"
    fig.text(0.06, 0.775, day, fontsize=14, color=CLEAR if mix < 0.5 else SMOKE, weight=600, alpha=fade)
    pts_now = C["pts"] if mix < 0.5 else S["pts"]
    for i, n in enumerate(LANDMARKS):
        mi, (x0, x1, y0, y1) = LANDMARKS[n]
        appear = seg(t, 0.3 + i * 0.22, 0.6 + i * 0.22)
        if appear <= 0: continue
        hl = 2.6 + i * 0.28 <= t < 2.6 + (i + 1) * 0.28 + 0.2
        col = CLEAR if mix < 0.5 else SMOKE
        appear *= fade
        ax.add_patch(plt.Rectangle((x0, y0 - 200), x1 - x0, y1 - y0, fill=False, ec=SKY if not hl else col, lw=2.2 if hl else 1.4, alpha=appear))
        ax.text((x0 + x1) / 2, y0 - 206, f"{mi} mi", color="white", fontsize=10, ha="center", weight=600, alpha=appear,
                bbox=dict(boxstyle="round,pad=0.2", fc=(0.03, 0.05, 0.08, 0.6), ec="none"))

    # chart
    cx = fig.add_axes([0.585, 0.21, 0.37, 0.55], facecolor=SURFACE)
    cx.set_yscale("log"); cx.set_ylim(FLOOR * 0.6, 1.25); cx.set_xlim(0, 70)
    cx.set_yticks([1, 0.1, 0.01]); cx.set_yticklabels(["100%", "10%", "1%"])
    cx.set_xlabel("Distance to the ridge (km)", color=INK2); cx.set_ylabel("Contrast left after the haze", color=INK2)
    for s_ in ["top", "right"]: cx.spines[s_].set_visible(False)
    for s_ in ["left", "bottom"]: cx.spines[s_].set_color(RULE)
    cx.tick_params(colors=INK3, length=0); cx.grid(color=RULE, lw=0.6, alpha=0.7, which="major")
    dd = np.linspace(0, 70, 200)

    def draw_series(sd, col, t_pts, t_line, label_y):
        km = np.array([p["km"] for p in sd["pts"]]); left = np.array([p["left"] for p in sd["pts"]])
        for i, (x, y) in enumerate(zip(km, left)):
            a = seg(t, t_pts + i * 0.28, t_pts + i * 0.28 + 0.3)
            if a <= 0: continue
            if y > FLOOR and x * 1000 < 3.912 / (sd["beta"] * 1e-6):
                cx.plot(x, y, "o", color=col, ms=9 * a + 1, mec=SURFACE, mew=1.5, zorder=4)
            else:
                cx.plot(x, FLOOR * 0.8, "o", mfc=SURFACE, mec=col, ms=7, mew=1.3, alpha=a, zorder=4)
        lp = seg(t, t_line, t_line + 1.1)
        if lp > 0:
            xe = 70 * lp
            yy = np.exp(-sd["beta"] * 1e-6 * dd * 1000)
            m = (dd <= xe) & (yy > FLOOR * 0.6)
            cx.plot(dd[m], yy[m], color=col, lw=2.6, solid_capstyle="round", zorder=3)
        return lp

    lc = draw_series(C, CLEAR, 2.6, 5.4, 0)
    if lc > 0.9:
        cx.text(48, np.exp(-C["beta"] * 48e-3) * 1.35, "Clear day", color=CLEAR, fontsize=13, weight=600)
    if t >= 7.6:
        ls = draw_series(S, SMOKE, 7.6, 8.6, 0)
        if ls > 0.3:
            cx.text(5.5, 0.12, "Smoke day", color=SMOKE, fontsize=13, weight=600)
        if t >= 8.4:
            cx.text(36, FLOOR * 1.25, "lost in the haze", color=SMOKE, fontsize=11, alpha=seg(t, 8.4, 8.9))

    # step 5: slope -> PM2.5 readout
    r = seg(t, 10.0, 10.6)
    if r > 0:
        for j, (sd, col, nm) in enumerate([(C, CLEAR, "Clear day"), (S, SMOKE, "Smoke day")]):
            y = 0.56 - j * 0.16
            fig.patches.append(FancyBboxPatch((0.075, y - 0.06), 0.375, 0.115, boxstyle="round,pad=0,rounding_size=0.008",
                                              transform=fig.transFigure, fc=SURFACE, ec=RULE, lw=1, alpha=r, zorder=5))
            fig.text(0.095, y + 0.012, nm, fontsize=15, color=col, weight=600, alpha=r, zorder=6)
            fig.text(0.095, y - 0.035, f"slope {sd['beta']:.0f} per Mm", fontsize=13, color=INK3, alpha=r, zorder=6)
            fig.text(0.235, y - 0.022, "→", fontsize=24, color=INK3, alpha=r, zorder=6)
            fig.text(0.435, y - 0.03, f"{sd['pm']:.0f} µg/m³", fontsize=30, color=INK, weight=650, alpha=r, ha="right", zorder=6)
            fig.text(0.435, y + 0.025, sd["cat"], fontsize=13, color=col, weight=600, alpha=r, ha="right", zorder=6)

    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    proc.stdin.write(buf.tobytes())
    if k % 2 == 0:
        gif_frames.append(Image.fromarray(buf[..., :3]).resize((960, 540), Image.LANCZOS))
    if abs(t - 12.4) < 0.5 / FPS:
        Image.fromarray(buf[..., :3]).save(OUT / "explainer_final_still.png")
    plt.close(fig)

proc.stdin.close(); proc.wait()
pal = gif_frames[-1].quantize(colors=200, method=Image.Quantize.MEDIANCUT)
q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in gif_frames]
dur = [int(2000 / FPS)] * len(q); dur[-1] = 2500
q[0].save(OUT / "pluma_method_explainer.gif", save_all=True, append_images=q[1:], duration=dur, loop=0, optimize=True)
for f in ["pluma_method_explainer.mp4", "pluma_method_explainer.gif"]:
    print(f, round((OUT / f).stat().st_size / 1e6, 2), "MB")
