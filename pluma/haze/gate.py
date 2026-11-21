"""Frame gates (plan sec 4.2). Camera-only, so they transfer to cameras with no sensors."""
import numpy as np
from scipy.ndimage import uniform_filter

from pluma.haze.fit import srgb_to_linear, luminance

# Chosen from visual cloud labels on the Nov 2016 Look Rock frames (labelled before
# scoring): cloudy frames 13.7-29.1, non-cloudy 3.8-10.3 (thin cirrus at 10.3).
SKY_TEXTURE_MAX = 12.0


def sky_texture(rgb01: np.ndarray, sky_rows: slice = slice(0, 300)) -> float:
    """Median local contrast of the upper sky, x1000. Clear, hazy and smoky skies are
    smooth; cumulus and broken cloud are textured (and cast shadows that change J)."""
    L = luminance(srgb_to_linear(rgb01[sky_rows]))
    hp = np.abs(L - uniform_filter(L, 31))
    return float(np.median(hp) / np.median(L) * 1000)


def passes_cloud_gate(rgb01: np.ndarray) -> bool:
    return sky_texture(rgb01) <= SKY_TEXTURE_MAX
