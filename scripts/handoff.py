"""Build out/video_handoff/ from the demo outputs. Values copied as computed, not smoothed or adjusted."""
import json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "out/video_handoff"
(H / "frames").mkdir(parents=True, exist_ok=True)
rows = json.loads((ROOT / "out/demo/rows.json").read_text())
headline = json.loads((ROOT / "out/demo/headline.json").read_text())

from pluma.regions_lookrock import LANDMARKS, SKY, FOREGROUND, MILE

out_rows = []
for r in rows:
    name = r["timestamp"][:13].replace("-", "").replace("T", "_") + "00_EST.jpg"
    shutil.copy2(ROOT / "data/frames/lookrock" / r["file"], H / "frames" / name)
    out_rows.append(dict(
        timestamp=r["timestamp"], file=f"frames/{name}", gate=r["gate"], reject_reason=r["reject_reason"],
        camera_extinction_Mm=r.get("cam_beta"), predicted_pm25=r.get("pred_pm25"), category=r.get("category"),
        monitor_pm25=r["monitor_pm25"], monitor_category=r.get("monitor_category"),
        site_extinction_Mm=r["site_beta"], rh_pct=r["rh"], split=r["split"],
        fitted_slope_per_km=r.get("fitted_slope_per_km"), bands=r.get("bands")))
(H / "results.json").write_text(json.dumps(out_rows, indent=1, default=float))

bands = {n: dict(distance_miles=mi, distance_km=round(mi * MILE / 1000, 2),
                 region_px=dict(x0=b[0], x1=b[1], y0=b[2], y1=b[3])) for n, (mi, b) in LANDMARKS.items()}
bands["_sky"] = dict(region_px=dict(x0=SKY[0], x1=SKY[1], y0=SKY[2], y1=SKY[3]))
bands["_foreground_gain"] = dict(region_px=dict(x0=FOREGROUND[0], x1=FOREGROUND[1], y0=FOREGROUND[2], y1=FOREGROUND[3]))
bands["_note"] = "Pixel boxes in 1000x750 frames. Distances from the NPS Look Rock landmark chart."
(H / "bands.json").write_text(json.dumps(bands, indent=1))
(H / "headline.json").write_text(json.dumps(headline, indent=1))

for src, dst in [("out/depth/depth_pro2.png", "depth_pro2.png"), ("out/depth/depth_da3.png", "depth_da3.png"),
                 ("out/depth/lookrock_dp2.npy", "depth_pro2_raw_metres.npy"), ("out/depth/lookrock_da3.npy", "depth_da3_raw.npy"),
                 ("out/depth/depth_side_by_side.png", "depth_side_by_side.png"),
                 ("out/demo/chart_A_extinction.png", "chart_A_extinction.png"), ("out/demo/chart_B_timeseries.png", "chart_B_timeseries.png"),
                 ("out/demo/chart_C_clear_vs_smoke.png", "chart_C_clear_vs_smoke.png"), ("out/arkansas/chart_D_arkansas.png", "chart_D_arkansas.png")]:
    if (ROOT / src).exists():
        shutil.copy2(ROOT / src, H / dst)
print("rows", len(out_rows), "->", H)
