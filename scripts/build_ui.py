"""Build out/video_handoff/pluma_demo.html: one self-contained page (images embedded), dark theme."""
import base64, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "out/video_handoff"
h = json.loads((H / "headline.json").read_text())
ark = json.loads((H / "arkansas_result.json").read_text())
dc = json.loads((H / "depth_compare.json").read_text())


def img(name, alt):
    b = base64.b64encode((H / name).read_bytes()).decode()
    return f'<img src="data:image/png;base64,{b}" alt="{alt}">'


t, e = h["test"], h["camera_vs_site_extinction"]
da3_rho = dc["DA3-SMALL"]["spearman_vs_chart"]
html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pluma</title>
<style>
:root{{--bg:#0e1116;--panel:#161b22;--ink:#e6edf3;--mute:#8b949e;--line:#30363d;--accent:#f0883e;--good:#3fb950;--warn:#d29922}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif}}
.wrap{{max-width:1180px;margin:0 auto;padding:32px 20px 48px}}
header h1{{font-size:44px;letter-spacing:-.02em;margin:0}} header p{{color:var(--mute);font-size:19px;margin:4px 0 0}}
section{{margin-top:44px}} h2{{font-size:13px;text-transform:uppercase;letter-spacing:.14em;color:var(--accent);margin:0 0 14px}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}}
.card img{{width:100%;border-radius:6px;background:#fff;display:block}}
.grid{{display:grid;grid-template-columns:2fr 1fr;gap:16px;align-items:start}}
@media (max-width:800px){{.grid{{grid-template-columns:1fr}}}}
.stat{{display:flex;justify-content:space-between;border-bottom:1px solid var(--line);padding:7px 0}} .stat b{{font-variant-numeric:tabular-nums}}
.note{{color:var(--mute);font-size:13px}} .tag{{display:inline-block;border:1px solid var(--warn);color:var(--warn);border-radius:99px;padding:1px 10px;font-size:12px}}
video{{width:100%;border-radius:8px;background:#000;aspect-ratio:16/9}}
footer{{margin-top:48px;border-top:1px solid var(--line);padding-top:16px;color:var(--mute);font-size:13px}}
</style></head><body><div class="wrap">
<header><h1>Pluma</h1><p>Existing cameras as air sensors</p></header>

<section><h2>1 · Ground truth: Look Rock, Great Smoky Mountains</h2>
<div class="card"><video src="demo.mp4" controls playsinline></video><p class="note">Video slot: place <code>demo.mp4</code> in this folder.</p></div>
<div class="grid"><div class="card">{img("chart_A_extinction.png", "Camera vs site extinction")}</div>
<div class="card"><div class="stat"><span>Camera vs site extinction, rank ρ</span><b>{e['spearman']:.2f}</b></div>
<div class="stat"><span>Frames (passed gates)</span><b>n = {e['n']}</b></div>
<p class="note">Hourly frames 10:00–16:00, Nov 2016. Gates: sun, clouds, humidity ≥ 85%. No PM2.5 used.</p></div></div>
<div class="grid"><div class="card">{img("chart_B_timeseries.png", "PM2.5 time series")}</div>
<div class="card"><h2 style="margin-bottom:6px">Test half (19–29 Nov)</h2>
<div class="stat"><span>Rank ρ</span><b>{t['spearman']:.2f}</b></div>
<div class="stat"><span>Mean error</span><b>{t['mean_error']:+.1f} µg/m³</b></div>
<div class="stat"><span>Mean abs. error</span><b>{t['mean_abs_error']:.1f} µg/m³</b></div>
<div class="stat"><span>Category match</span><b>{t['category_match']:.0%}</b></div>
<div class="stat"><span>Within one category</span><b>{t['within_one_category']:.0%}</b></div>
<div class="stat"><span>n</span><b>{t['n']}</b></div>
<p class="note">alpha = {h['alpha']:.2f} m²/g fitted on 8–18 Nov only. Rank on the test half is moderate (ρ {t['spearman']:.2f}).</p></div></div>
<div class="card">{img("chart_C_clear_vs_smoke.png", "Clear vs smoke day")}
<p class="note">26 Nov: the camera's extinction matches the site (111 vs 100 Mm⁻¹), but its PM2.5 is higher than the tower-top monitor (16.8 vs 4.7). The smoke lay in the valleys below the monitor.</p></div>
</section>

<section><h2>2 · Depth</h2>
<div class="card">{img("depth_side_by_side.png", "Depth Pro 2 vs DA3")}
<p class="note">Depth Pro 2 (B): sharp near field, but every ridge beyond ~1 km is returned as infinitely far. DA3-SMALL: keeps ridge order (ρ = {da3_rho:.2f} vs NPS chart), raw metres invalid; scale set from map anchors. Depth Pro 2 weights are research-only.</p></div>
</section>

<section><h2>3 · Arkansas</h2>
<div class="card">{img("chart_D_arkansas.png", "Arkansas camera reading")}
<p><span class="tag">single frame · preliminary · no local monitor</span></p>
<p>Reading: <b>{ark['category']}</b>, PM2.5 ≈ {ark['pm25']:.0f} µg/m³ (range {ark['pm25_range'][0]:.0f}–{ark['pm25_range'][1]:.0f}). Extinction {ark['beta_Mm']:.0f} Mm⁻¹.</p>
<p class="note">ARDOT camera 9004 (Hwy 16 eastbound, probably Edwards Junction): nearest regulatory PM2.5 monitor is Springdale, 77 km away. The Tunnel Tower camera (ID 304, I-49) is 46 km from it. Most of this view is a nearby tree slope, so the reading rests mainly on one distant band.</p></div>
</section>

<footer>Reference: NPS on-site monitor (TEOM) at Look Rock, read from the NPS AirWebCams archive. Not an EPA file; TEOMs can read low in heavy smoke.
Calibration is per season: a June 2016 test did not transfer. Deployment on ARDOT cameras needs ARDOT permission.</footer>
</div></body></html>"""
(H / "pluma_demo.html").write_text(html)
print("wrote", H / "pluma_demo.html", len(html) // 1024, "KB")
