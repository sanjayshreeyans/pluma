# Camera haze to PM2.5: method and build plan

Status: design, not yet tested on real data. The physics is established. The accuracy numbers are estimates until the validation step is run.

## 1. The claim

A fixed outdoor camera with a view of several kilometres can estimate how much light the air removes per kilometre. That value, called extinction, rises with fine particle pollution (PM2.5). One camera gives one reading for the area it looks across.

## 2. Why it works

Particles in the air do two things to the light from a distant object:

- They scatter some of the object's light out of the path, so the object looks dimmer.
- They scatter sunlight into the path, so a pale veil is added.

Both effects grow with distance. This is why far ridges look paler and bluer than near ones. In the ARDOT 9004 image, the near wooded slope is dark and saturated and the far ridgelines fade toward the sky colour. That fading is the measurement.

Airports have used the same physics for decades to report visibility.

## 3. Equations

### 3.1 Haze model (Koschmieder)

```
I(d) = J * t(d) + A * (1 - t(d))
t(d) = exp(-beta * d)
```

- `I(d)`: brightness the camera sees for an object at distance `d`
- `J`: the object's own brightness with no air in the way
- `A`: brightness of the sky at the horizon
- `t(d)`: fraction of light that survives the path
- `beta`: extinction, in 1/m. Often written in Mm^-1 (1 Mm^-1 = 1e-6 per metre)

Rearranged:

```
A - I(d) = (A - J) * exp(-beta * d)
ln(A - I(d)) = ln(A - J) - beta * d
```

So for dark objects of similar type (forested ridges), a plot of `ln(A - I)` against distance is a straight line with slope `-beta`.

### 3.2 Two-ridge form

For two similar ridges at distances `d1 < d2`:

```
beta = ln[(A - I1) / (A - I2)] / (d2 - d1)
```

Camera gain multiplies `A`, `I1` and `I2` equally, so it cancels.

Worked example: `A = 200`, `J = 50`, ridges at 1 km and 10 km, true `beta = 58 Mm^-1`.

```
A - I1 = 150 * exp(-0.058) = 141.6
A - I2 = 150 * exp(-0.58)  =  84.0
beta   = ln(141.6 / 84.0) / 9000 m = 5.8e-5 per m = 58 Mm^-1
```

### 3.3 Differential form (preferred)

The absolute form assumes every ridge has the same `J`. To remove that assumption, compare each region with the same region in a clear reference frame taken at the same time of day:

```
dy_i = ln(A - I_i) - ln(A_ref - I_i_ref)
dy_i = c - (beta - beta_ref) * d_i
```

`c` is one constant for the whole frame (overall lighting change). The slope of `dy_i` against `d_i` gives `beta - beta_ref`. Each region's own `J` cancels.

`beta_ref` comes from the monitor reading on the reference day, or is assumed close to clean air (about 15 to 25 Mm^-1).

### 3.4 Extinction to PM2.5

```
beta = beta_air + alpha * f(RH) * PM2.5
PM2.5 [ug/m3] = (beta [Mm^-1] - beta_air) / (alpha * f(RH))
```

- `beta_air`: scattering by clean air, about 11 Mm^-1 at 2,200 ft
- `alpha`: light removed per unit of particle mass, about 4 m2/g (range roughly 3 to 6 by particle type)
- `f(RH)`: humidity growth factor. Start with `f = (1 - RH)^(-g)`, `g` about 0.3 to 0.5, and fit `g` locally

Check: `beta = 58` gives `(58 - 11) / 4 = 11.8 ug/m3` in dry air.

In practice, fit `alpha` and `g` once per region against the nearest monitor. This one calibration is shared by every camera in the region.

### 3.5 Which distances carry the signal

A region is useful when `beta * d` is between about 0.1 and 2.5. Below that the change is too small. Above it the object has vanished into the haze.

| PM2.5 (ug/m3) | beta (Mm^-1) | Best distance, about 1/beta |
|---|---|---|
| 10 | 51 | 20 km |
| 35 | 151 | 7 km |
| 150 | 611 | 1.6 km |

A scene with ridges at several distances covers the whole range. Far ridges measure clean days and near ridges measure smoke days.

### 3.6 Expected precision

```
error in beta = error in ln-ratio / (d2 - d1)
```

| Distance span | PM2.5 error at 10% ratio error |
|---|---|
| 1 km | about 25 ug/m3 |
| 5 km | about 5 ug/m3 |
| 10 km | about 2.5 ug/m3 |

The 10% ratio error is an assumption. Measuring it is part of validation. The mass conversion adds roughly 30% on top.

## 4. Pipeline

### 4.1 One-time setup per camera

1. Record latitude, longitude, elevation and heading.
2. Mask out overlays (logo, text), the road, and anything that moves.
3. Mark regions: a sky band just above the horizon, and three or more bands at different distances (near slope, mid ridge, far ridges).
4. Assign a distance to each band:
   - Manual: measure each ridge on a map or in Google Earth. Enough for the demo.
   - Automatic: render the skyline from a terrain model (USGS 3DEP) at the camera position and match ridgelines.
   - Depth Anything 3: use for near and mid-field ordering and to split the image into depth bands. Pin its scale with the map distances. Its accuracy beyond 2 km is untested here.

### 4.2 Every frame

1. Capture every 5 to 10 minutes and record your own timestamp.
2. Gate. Keep the frame only if:
   - sun elevation is above about 15 degrees
   - the sun is not in or near the view (an eastbound camera needs midday and afternoon)
   - humidity is below 85% and there is no rain or fog (National Weather Service data, or the camera's own road weather station)
   - the image is sharp (lens not wet or dirty)
3. Convert pixel values from sRGB to linear light. Use the green channel or luminance.
4. `A` = median of the sky band. Reject the frame if the band is very uneven (broken cloud).
5. `I_i` = median of each distance band.
6. Fit the slope from section 3.3 with a robust fit (Theil-Sen or RANSAC).
7. Quality score from the straightness of the fit. A poor fit means no reading.
8. Convert to PM2.5 with section 3.4.

### 4.3 Reporting

- Take the median over 30 to 60 minutes.
- Report an air quality category, a range, and the area covered ("the 10 km east of camera 9004").
- Report "no reading" at night, in fog and in rain.

### 4.4 Reference frames

For each hour of the day, keep the clearest frame from the last 2 to 4 weeks. A rolling window is needed because foliage changes with season, which changes `J`.

## 5. Core code

```python
import numpy as np
from scipy.stats import theilslopes

def srgb_to_linear(x):                      # x in 0..1
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)

def band_median(img_lin, mask):
    return np.median(img_lin[mask])

def beta_differential(img, ref, sky, bands, dist_m, beta_ref):
    """img, ref: linear luminance arrays. sky: bool mask.
    bands: list of bool masks. dist_m: distance of each band in metres."""
    A, A_ref = band_median(img, sky), band_median(ref, sky)
    dy = []
    for m in bands:
        cur, base = A - band_median(img, m), A_ref - band_median(ref, m)
        if cur <= 0 or base <= 0:           # band vanished or brighter than sky
            dy.append(np.nan)
        else:
            dy.append(np.log(cur) - np.log(base))
    dy, d = np.array(dy), np.array(dist_m, float)
    ok = ~np.isnan(dy)
    if ok.sum() < 3:
        return None
    slope, _, lo, hi = theilslopes(dy[ok], d[ok])
    return beta_ref - slope, (beta_ref - hi, beta_ref - lo)   # per metre

def pm25(beta_per_m, rh, alpha=4.0, g=0.4, beta_air=11.0):
    f = (1.0 - min(rh, 0.85)) ** (-g)
    return max(0.0, (beta_per_m * 1e6 - beta_air) / (alpha * f))
```

Run with `uv run --with numpy --with scipy --with pillow python script.py`.

## 6. Validation

1. Pair each camera with the nearest monitor or PurpleAir sensor.
2. Collect at least two weeks of daytime frames, including some hazy days.
3. Compare hourly camera PM2.5 with the monitor: rank correlation, mean error, and how often the category matches.
4. Fit `alpha` and `g` on one camera. Test on a different camera without changing them. This is the transfer result.

## 7. Confidence

| Claim | Confidence |
|---|---|
| The haze equations are correct | High. Standard atmospheric optics |
| Heavy smoke is detected on a long-view camera | High. The contrast change is large |
| Day-to-day changes are tracked when the span is 5 km or more | Moderate. Expected, not yet shown here |
| Readings are accurate below 15 ug/m3 | Low. No published evidence on unseen cameras |
| It works on a new camera with no calibration | Unknown. This is the experiment |
| Depth Anything 3 gives good distances beyond 2 km | Unknown. Use map distances as the anchor |

## 8. Known error sources

| Source | Effect | Mitigation |
|---|---|---|
| Humidity | Swollen particles read as more PM2.5 | `f(RH)` correction, reject above 85% |
| Fog, low cloud | Reads as extreme pollution | Weather gate, colour check (fog is grey, smoke dims blue more) |
| Sun angle, shadows | Changes `J` | Reference frame from the same hour |
| Camera tone curve | Breaks linearity | Linearize, use ratios within one frame |
| Compression, low resolution | Far bands lose detail | Use band medians, not fine texture |
| Seasonal foliage | Changes `J` slowly | Rolling reference window |
| Particle type | Changes `alpha` | Regional calibration, report a range |
| Uneven haze (a plume in part of the view) | Bends the fit | Poor fit score, flag as "plume in view" |

## 9. Camera ARDOT 9004

This is probably the Hwy 16 at Edwards Junction camera (IDrive ID 168): same elevation and same eastbound view. That match is inferred, not confirmed.

Good points:

- Elevation 2,215 ft with ridges at several distances. This is the scene type the method needs.
- It shows temperature, so it is probably a road weather station, which may also report humidity.

Problems:

- The far ridges occupy a thin strip of a small image. Get the highest resolution the feed offers.
- The logo overlay covers part of the far ridges and sky.
- It faces east, so mornings will have sun glare.
- IDrive Arkansas terms prohibit embedding or linking its cameras, and there is no archive. Ask ARDOT for permission before building a product on it.
- Ridge distances and the nearest monitor have not been looked up yet.

## 10. Build order

1. Measure ridge distances for one camera on a map. Draw the masks.
2. Start saving frames with timestamps today.
3. Implement section 5 and plot `beta` over time.
4. Add weather gating and the PM2.5 conversion.
5. Plot against the nearest monitor. This is the proof slide.
6. Repeat on a second camera without recalibrating.

## 11. What Depth Anything 3 does in this system

The haze fit needs a distance for every measured region. DA3 supplies the structure of the scene and a map supplies the scale.

The Ariadne repo already has a working wrapper: `depth/da3_inference.py`, with DA3-SMALL weights in `models/da3-small`, running on Mac MPS. Its own notes record that DA3's metric depth depends on focal length and was about 2.3 times off without camera intrinsics. A DOT camera's focal length is unknown, so raw DA3 metres cannot be trusted here.

DA3 has four jobs:

1. **Depth bands.** Run DA3 once on each camera's clear reference frame. Sort pixels by depth and cut them into bands (near, mid, far, sky). This replaces drawing masks by hand, and is the step that lets the method run on a camera nobody has surveyed.
2. **Anchored scale.** Take two or three landmarks with known map distance. Fit `d_true = a * d_DA3 ^ b` through them. Every other pixel then gets a distance from the fitted curve.
3. **Camera scoring.** The share of non-sky pixels beyond 2 km says whether a camera qualifies, with no human looking at it.
4. **Sky and horizon.** The far limit of the depth map marks the horizon band used for `A`.

Open question: how well DA3 orders distances beyond 2 km. Look Rock answers this, because the National Park Service publishes a chart of its ridges with distances from 1 to 39 miles. Comparing DA3's ordering against that chart is a result nobody appears to have published.

Fallback if DA3 is poor at long range: use DA3 for the near and mid field and map distances for the far ridges.

## 12. Arkansas demo plan

Constraint: no Arkansas camera found so far has both a long view and a regulatory PM2.5 monitor within 10 km. So accuracy cannot be proven on an Arkansas DOT camera today.

### Part 1: prove the method

| Option | What it gives | Limits |
|---|---|---|
| Great Smoky Mountains, Look Rock | Monitor on site, labelled ridges, public-domain archive from 1998, a known smoke day (26 Nov 2016) | Tennessee, not Arkansas. Same scene type as the Ozarks: forested ridges |
| Your own camera in Fayetteville | Arkansas data, no terms problem, Springdale monitor (05-143-0005) nearby | Needs a high window with a long view, and days of capture |
| PurpleAir sensors near an Arkansas camera | Arkansas check on a DOT view | Not yet looked up. Lower-grade reference |

Use Look Rock for the proof chart. Add the Fayetteville camera if a suitable window exists, because it makes the proof local.

The IMPROVE filter site at Deer is 14 km from Edwards Junction, but it reports 24-hour samples with a long delay and ARDOT keeps no image archive, so it cannot be used for the demo.

### Part 2: show the Arkansas gap

| Camera | Location | Nearest regulatory monitor |
|---|---|---|
| ARDOT Tunnel Tower Cam (ID 304), I-49, Boston Mountains | 35.7678, -94.1893, 1,842 ft, facing south | Springdale, 46 km |
| Hwy 16 at Edwards Junction (ID 168) | 35.8482, -93.3616, 2,215 ft, facing east | Springdale, 77 km |

The Tunnel Tower camera has the better view. The north-central Ozarks (Harrison, Mountain Home, Clinton) have no regulatory PM2.5 monitor.

ARDOT limits:

- Terms prohibit linking to or embedding cameras, and images are copyrighted. Get written permission from the ARDOT Public Information Office before any automated use.
- The site is behind bot protection. Do not script around it.
- Stills are 720x405, so the far ridges are a few pixels tall.
- For the demo without permission: show the method on manually saved frames and state that deployment needs an ARDOT agreement.

### Demo flow

1. Look Rock, clear day against smoke day: the fit, the PM2.5 estimate, the monitor's value.
2. Look Rock over many days: camera line against monitor line.
3. Map of Arkansas monitors with the gap in the Ozarks.
4. An Arkansas ridge camera: DA3 depth bands, the fit, a reading with a range.

## 13. Backend design

A new project in this folder. It reuses Ariadne's DA3 wrapper and weights and does not change Ariadne.

```
pluma/
  cameras.yaml        camera registry: id, name, lat, lon, heading, source, anchors
  ingest/             frame sources: NPS live and archive, local folder
  depth/              DA3 on reference frame -> depth bands, anchored scale, score
  haze/               linearize, sky value, band medians, slope fit, quality
  weather/            humidity from National Weather Service
  truth/              monitor data: EPA AQS (history), AirNow (current)
  convert/            beta -> PM2.5, category, range
  store.py            SQLite: frames, readings, monitor values
  api.py              FastAPI
  ui/                 one page: map, camera panel, fit plot, time series
```

API:

| Route | Returns |
|---|---|
| `GET /cameras` | Registry with qualification score |
| `GET /cameras/{id}/latest` | Frame, depth band overlay, beta, PM2.5, range, quality |
| `GET /cameras/{id}/readings` | Time series with monitor values where available |
| `POST /cameras/{id}/frame` | Upload a frame by hand (for saved ARDOT stills) |
| `GET /validation/{id}` | Correlation, mean error, category agreement |

Base44 can be the public front end and call this API.

Build order:

1. Look Rock: fetch one clear frame and the 26 Nov 2016 frame. Run the fit with chart distances. First number.
2. DA3 on the clear frame. Compare its ordering with the chart.
3. Pull Look Rock PM2.5 from EPA AQS. Fit `alpha` and `g`.
4. Extend to a few weeks of frames. Proof chart.
5. API and one-page UI.
6. Add an Arkansas camera through the upload route.
