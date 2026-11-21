# Pluma: existing cameras as air sensors

Pluma reads haze from outdoor webcams and turns it into PM2.5. Distant ridges fade toward the sky colour as particles fill the air. How fast they fade with distance gives the extinction (Koschmieder), and a calibration turns extinction into µg/m³.

**Live site:** https://sanjayshreeyans.github.io/pluma/

## Results (as measured)

Look Rock, Great Smoky Mountains, November 2016. The camera sits next to a National Park Service monitor.

| Measure | Value |
|---|---|
| Camera haze vs the park's haze instrument (rank correlation) | **0.79**, n = 77 daytime hours |
| PM2.5 on unseen days (19–29 Nov), rank correlation | 0.51, n = 29 |
| Right air-quality category / within one category | 55% / **90%** |

Limits:
- The calibration is per region and season. A June 2016 test did not transfer.
- The PM2.5 reference is the NPS on-site TEOM, read from the NPS AirWebCams archive. It is not an EPA file, and TEOMs can read low in heavy smoke.

Arkansas, single frames with no local monitor to check against (calibration unchanged):

| Camera | Reading | Nearest PM2.5 monitor |
|---|---|---|
| ARDOT Tunnel Tower, I-49 (21 Nov 2026, 14:09 CST) | Good, 2.9 µg/m³ (range 0–18) | Springdale, 46 km |
| ARDOT camera 9004, Hwy 16 Edwards Junction (saved frame) | Good, 4.7 µg/m³ (range 0–61) | Springdale, 77 km |

## Videos

- `out/video_handoff/pluma_lookrock_viewer_20s.mp4`: the Look Rock viewer, hour by hour
- `out/video_handoff/pluma_method_explainer.mp4`: how the method works
- `out/video_handoff/pluma_arkansas_reading.mp4` (and a `_6s` cut): Arkansas monitor map and readings
- `out/video_handoff/script.md`: voiceover script with sources for every number

## Layout

| Path | What |
|---|---|
| `site/` | The static website, published to GitHub Pages |
| `pluma/` | Haze fit, gates, conversion, NPS archive client |
| `scripts/` | Every analysis, figure, recording and export step |
| `data/` | NPS frames and metadata, ARDOT frames, camera configs, EPA monitor list |
| `out/` | Charts, results JSON, video handoff bundle |
| `camera-pm25-plan.md` | The original method and build plan |

Run with [uv](https://docs.astral.sh/uv/):

```bash
PYTHONPATH=. uv run python scripts/demo_step1.py
```

To preview the site locally:

```bash
cd site && python3 -m http.server 8420
```

## Sources and licences

- **Look Rock images and sensor data:** National Park Service AirWebCams archive (public domain).
- **Ridge distances:** NPS Look Rock landmark chart. Arkansas distances come from AWS Terrain Tiles.
- **PM2.5 monitor list:** EPA AirData (daily 88101, 2025).
- **Humidity:** aviationweather.gov METAR (KFYV).
- **Depth:** Depth Anything 3 (DA3-Small). The Depth Pro 2 depth map was made with Apple's research-only weights, which are not included here.
- **ARDOT camera frames are © Arkansas Department of Transportation.** IDrive Arkansas's terms restrict embedding and republishing. They are included here at the project owner's decision, for a non-commercial research demo. Any automated or commercial use needs ARDOT's written permission.
