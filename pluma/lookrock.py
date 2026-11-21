"""Run the camera haze fit on a set of Look Rock frames (one season/period).

Blind to PM2.5: the only site value used is the reference day's visual range,
which sets beta_ref for the clear reference frame (plan sec 3.3). PM and RH are
attached to the rows afterwards, for calibration and scoring only.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from pluma.haze.fit import srgb_to_linear, luminance, beta_anchored
from pluma.haze.gate import sky_texture, SKY_TEXTURE_MAX
from pluma.regions_lookrock import LANDMARKS, SKY, FOREGROUND, MILE

RH_MAX = 85.0  # plan sec 4.2 humidity gate (percent)

NAMES = list(LANDMARKS)
DIST = np.array([LANDMARKS[n][0] * MILE for n in NAMES])


def _mask(shape, b):
    x0, x1, y0, y1 = b
    m = np.zeros(shape, bool)
    m[y0:y1, x0:x1] = True
    return m


def site_values(meta_files) -> dict[str, dict]:
    """'YYYYMMDD_HHMM' -> site readings, from saved NPS archive search results."""
    out = {}
    for f in meta_files:
        for r in json.loads(Path(f).read_text()).get("Results", []):
            a = r["Asset"]
            m, d, rest = a["LocalTimeString"].split("/", 2)
            y, hm, ap = rest.split(" ")[:3]
            hh, mm = map(int, hm.split(":"))
            hh = hh % 12 + (12 if ap == "PM" else 0)
            out[f"{y}{int(m):02d}{int(d):02d}_{hh:02d}{mm:02d}"] = {
                x["Name"]: x["Value"] for x in a["CustomNumberFields"]}
    return out


def run_period(frames: list[Path], site: dict, ref_key: str, period: str) -> list[dict]:
    ref_path = next(p for p in frames if ref_key in p.stem)
    ref = luminance(srgb_to_linear(np.asarray(Image.open(ref_path).convert("RGB"), float) / 255))
    shape = ref.shape
    sky, fg = _mask(shape, SKY), _mask(shape, FOREGROUND)
    bands = [_mask(shape, LANDMARKS[n][1]) for n in NAMES]
    beta_ref = 3912.0 / site[ref_key]["VisualRange"] * 1e-6

    rows = []
    for p in sorted(frames):
        key = p.stem.replace("grsm_", "")
        rgb = np.asarray(Image.open(p).convert("RGB"), float) / 255
        img = luminance(srgb_to_linear(rgb))
        an = beta_anchored(img, ref, sky, fg, bands, DIST, beta_ref)
        tex = sky_texture(rgb)
        s = site.get(key, {})
        vr, rh, pm = s.get("VisualRange"), s.get("RelativeHumidity"), s.get("ParticulateMatter")
        rows.append(dict(
            period=period, frame=key, is_ref=key == ref_key,
            cam_beta=an.beta_Mm, cam_lo=an.jackknife_per_m[0] * 1e6, cam_hi=an.jackknife_per_m[1] * 1e6,
            fit_r2=an.r2, A=an.A, gain=an.gain, sky_texture=tex,
            cloud_ok=tex <= SKY_TEXTURE_MAX, rh_ok=(rh is not None and rh <= RH_MAX),
            # attached for scoring only; not used above
            site_beta=3912.0 / vr if vr else None, vr=vr, rh=rh, pm=pm,
        ))
    return rows
