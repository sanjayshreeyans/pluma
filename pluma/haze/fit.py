"""Koschmieder haze fit (plan sections 3 and 5).

All image values are linear-light luminance in 0..1.
Distances are metres; beta is returned per metre (multiply by 1e6 for Mm^-1).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import theilslopes, linregress


def srgb_to_linear(x: np.ndarray) -> np.ndarray:
    """x in 0..1 -> linear light."""
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def luminance(rgb_lin: np.ndarray) -> np.ndarray:
    """Rec.709 luminance from linear RGB [H,W,3]."""
    return rgb_lin @ np.array([0.2126, 0.7152, 0.0722])


def band_median(img: np.ndarray, mask: np.ndarray) -> float:
    return float(np.median(img[mask]))


@dataclass
class FitResult:
    beta_per_m: float          # fitted extinction (or delta-beta for differential)
    ci_per_m: tuple[float, float]
    intercept: float
    r2: float                  # straightness of ln(A-I) vs d (OLS r^2)
    d_m: np.ndarray            # distances used
    y: np.ndarray              # ln(A - I) or dy values used
    sky: float                 # A
    band_vals: np.ndarray      # I_i

    @property
    def beta_Mm(self) -> float:
        return self.beta_per_m * 1e6


def _robust_line(y: np.ndarray, d: np.ndarray):
    slope, icpt, lo, hi = theilslopes(y, d)
    r2 = linregress(d, y).rvalue ** 2 if len(d) > 2 else float("nan")
    return slope, icpt, lo, hi, r2


def beta_absolute(img, sky, bands, dist_m) -> FitResult | None:
    """Section 3.1: slope of ln(A - I_i) against d_i is -beta.

    Assumes every band has the same intrinsic brightness J.
    """
    A = band_median(img, sky)
    I = np.array([band_median(img, m) for m in bands])
    d = np.asarray(dist_m, float)
    diff = A - I
    ok = diff > 0
    if ok.sum() < 2:
        return None
    y = np.log(diff[ok])
    slope, icpt, lo, hi, r2 = _robust_line(y, d[ok]) if ok.sum() > 2 else (
        (y[1] - y[0]) / (d[ok][1] - d[ok][0]), y[0], np.nan, np.nan, np.nan)
    return FitResult(-slope, (-hi, -lo), icpt, r2, d[ok], y, A, I)


@dataclass
class AnchoredResult:
    beta_per_m: float
    jackknife_per_m: tuple[float, float]   # min/max of leave-one-band-out fits
    A: float                               # fitted horizon airlight (inside the haze)
    gain: float                            # lighting change vs reference, from foreground
    r2: float                              # fit quality on band brightness
    d_m: np.ndarray
    I: np.ndarray
    J: np.ndarray                          # per-band intrinsic brightness (from reference)

    @property
    def beta_Mm(self) -> float:
        return self.beta_per_m * 1e6


def intrinsic_from_ref(ref, sky, bands, dist_m, beta_ref_per_m):
    """Invert the clear reference frame for each band's own J_i.

    On a clear day the sky band is a fair estimate of A (haze is thin and even),
    so J_i = A_ref + (I_ref_i - A_ref) / t_ref_i.
    """
    A_r = band_median(ref, sky)
    I_r = np.array([band_median(ref, m) for m in bands])
    t_r = np.exp(-beta_ref_per_m * np.asarray(dist_m, float))
    return A_r + (I_r - A_r) / t_r


def _fit_A_beta(I, gJ, d):
    from scipy.optimize import least_squares

    def res(p):
        A, b = p
        return A + (gJ - A) * np.exp(-b * 1e-6 * d) - I

    p0 = [max(I.max(), 1e-3), 100.0]
    sol = least_squares(res, p0, bounds=([0.0, 0.0], [1.0, 5000.0]), loss="soft_l1", f_scale=0.01)
    return sol.x


def beta_anchored(img, ref, sky, fg, bands, dist_m, beta_ref_per_m) -> AnchoredResult | None:
    """Fixed method (replaces sky-band A on hazy days).

    1. Each band's own J_i comes from the clear reference frame (as in sec 3.3).
    2. Lighting gain g = foreground / foreground_ref. Foreground canopy is ~50 m
       away, so haze barely touches it.
    3. A (horizon airlight inside the haze) and beta are both fitted:
           I_i = A + (g J_i - A) exp(-beta d_i)
       Bands that have vanished into the haze pin A; bands still visible give beta.
    """
    d = np.asarray(dist_m, float)
    J = intrinsic_from_ref(ref, sky, bands, d, beta_ref_per_m)
    g = band_median(img, fg) / band_median(ref, fg)
    I = np.array([band_median(img, m) for m in bands])
    gJ = g * J
    A, b = _fit_A_beta(I, gJ, d)
    pred = A + (gJ - A) * np.exp(-b * 1e-6 * d)
    r2 = 1 - np.sum((I - pred) ** 2) / np.sum((I - I.mean()) ** 2)
    jk = []
    for k in range(len(d)):
        keep = np.arange(len(d)) != k
        jk.append(_fit_A_beta(I[keep], gJ[keep], d[keep])[1])
    return AnchoredResult(b * 1e-6, (min(jk) * 1e-6, max(jk) * 1e-6), A, g, r2, d, I, J)


NOISE_FLOOR = 0.02  # |A - I| / A below this = band indistinguishable from the haze


def beta_windowed(img, ref, sky, fg, bands, dist_m, beta_ref_per_m, lo=0.1, hi=2.5, max_iter=6):
    """Anchored fit restricted to informative bands: signal above the noise floor
    and beta*d inside [lo, hi]. Estimate beta, drop bands outside, refit, repeat.
    Returns (AnchoredResult on kept bands, kept mask over all bands)."""
    d = np.asarray(dist_m, float)
    full = beta_anchored(img, ref, sky, fg, bands, d, beta_ref_per_m)
    keep = np.ones(len(d), bool)
    res = full
    for _ in range(max_iter):
        signal = np.abs(res.A - full.I) / max(res.A, 1e-6)
        bd = res.beta_per_m * d
        new = (signal > NOISE_FLOOR) & (bd >= lo) & (bd <= hi)
        if new.sum() < 3:          # not enough informative bands: keep the full fit
            return full, np.ones(len(d), bool)
        if np.array_equal(new, keep) and res is not full:
            break
        keep = new
        res = beta_anchored(img, ref, sky, fg, [b for b, k in zip(bands, keep) if k], d[keep], beta_ref_per_m)
    return res, keep


def beta_differential(img, ref, sky, bands, dist_m, beta_ref_per_m: float) -> FitResult | None:
    """Section 3.3: dy_i = c - (beta - beta_ref) d_i. Each band's own J cancels."""
    A, A_ref = band_median(img, sky), band_median(ref, sky)
    d = np.asarray(dist_m, float)
    I = np.array([band_median(img, m) for m in bands])
    I_ref = np.array([band_median(ref, m) for m in bands])
    cur, base = A - I, A_ref - I_ref
    ok = (cur > 0) & (base > 0)
    if ok.sum() < 3:
        return None
    dy = np.log(cur[ok]) - np.log(base[ok])
    slope, icpt, lo, hi, r2 = _robust_line(dy, d[ok])
    return FitResult(beta_ref_per_m - slope, (beta_ref_per_m - hi, beta_ref_per_m - lo),
                     icpt, r2, d[ok], dy, A, I)
