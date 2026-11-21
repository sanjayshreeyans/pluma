# Pluma video handoff

All values are as computed. Nothing is smoothed or adjusted.

| File | Format | Contents |
|---|---|---|
| `frames/` | JPEG, 1000x750 | All 191 Look Rock frames from Nov 2016, on the hour 10:00–16:00 EST, named `YYYYMMDD_HH00_EST.jpg` (NPS AirWebCams archive, public domain) |
| `results.json` | JSON list, one row per frame | timestamp, file, gate (pass/reject), reject_reason, camera_extinction_Mm (Mm⁻¹), predicted_pm25 (µg/m³), category, monitor_pm25, monitor_category, site_extinction_Mm (3.912/visual range), rh_pct, split (train = 8–18 Nov, test = 19–29 Nov), fitted_slope_per_km, bands (per band: name, distance_km, I = linear brightness, signal = (A−I)/A, kept) |
| `bands.json` | JSON | pixel box (x0,x1,y0,y1) and NPS chart distance (miles, km) for each ridge band, plus the sky and foreground-gain boxes |
| `headline.json` | JSON | step 1 headline numbers (camera vs site extinction; train and test scores) |
| `chart_A_extinction.png` | PNG | camera extinction vs site extinction |
| `chart_B_timeseries.png` | PNG | Nov 2016 PM2.5: camera vs on-site monitor, train/test boundary, 26 Nov marked |
| `chart_C_clear_vs_smoke.png` | PNG | 20 Nov (clear) beside 26 Nov (valley smoke), per-ridge fit |
| `chart_D_arkansas.png` | PNG | ARDOT camera 9004: single frame, preliminary, no local monitor |
| `depth_side_by_side.png` | PNG | source, Depth Pro 2 (B), DA3-SMALL on the clear Look Rock frame |
| `depth_pro2.png`, `depth_da3.png` | PNG | colour depth maps (log depth; near = light, far = dark; black = infinite) |
| `depth_pro2_raw_metres.npy` | NumPy float32 [750,1000] | Depth Pro 2 depth in metres; `inf` = infinitely far |
| `depth_da3_raw.npy` | NumPy float32 [750,1000] | DA3 raw depth (its metric scale is not valid here) |
| `arkansas_depth_da3_raw.npy`, `arkansas_result.json` | NumPy / JSON | Arkansas depth and reading |
| `depth_compare.json` | JSON | per-ridge model distance vs NPS chart |

Notes:
- PM2.5 reference: the NPS on-site TEOM at Look Rock, read from NPS archive metadata. This is not an EPA file. TEOMs can read low in heavy smoke.
- Calibration (alpha) was fitted on the train half and is valid for one season only. A June 2016 test failed to transfer.
- Depth Pro 2 weights are research-only (Apple ML Research Model License, non-commercial).
- ARDOT images are copyrighted. Get permission from ARDOT before any automated or public use.

## Video assets (website recording and method explainer)

| File | Format | Contents |
|---|---|---|
| `pluma_lookrock_viewer.mp4` | H.264, 1600 px wide, 48 s, 3.6 MB | The website's Look Rock viewer stepping through all 77 hours from 8 Nov 10:00, at the site's play speed |
| `pluma_lookrock_viewer_20s.mp4` | H.264, 1600 px wide, 20 s, 2.3 MB | Same recording, faster cut for the final render |
| `pluma_lookrock_viewer.gif` | GIF, 900 px wide, 2.7 MB | Same recording as a GIF |
| `pluma_method_explainer.mp4` / `.gif` | H.264 1280x720, 13 s, 0.35 MB / GIF 960 px | Method explainer for the "faded vs distance, straight line, steeper = dirtier, PM2.5" lines. Real data: 29 Nov (clear, slope 31, 4 µg/m³) vs 8 Nov (smoke, slope 579, 117 µg/m³), each measured against the 20 Nov reference |
| `site_capture/still_*.png` | PNG, 2x | Website stills: lead numbers, Arkansas readings, depth comparison, 26 Nov viewer |
| `site_capture/frames/` | PNG, 2160x1492 | The 77 raw viewer captures |

Explainer note: ridges beyond that hour's visual range (contrast below 2%) are drawn as "lost in the haze"; their measured values are noise.
