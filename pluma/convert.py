"""Extinction -> PM2.5, category and range (plan sec 3.4, 4.3)."""
from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares

BETA_AIR = 11.0  # Mm^-1, Rayleigh at ~800 m, green

# EPA PM2.5 AQI breakpoints (2024 revision), ug/m3, upper edges.
CATEGORIES = [(9.0, "Good"), (35.4, "Moderate"), (55.4, "Unhealthy for sensitive groups"),
              (125.4, "Unhealthy"), (225.4, "Very unhealthy"), (np.inf, "Hazardous")]


def category(pm: float) -> str:
    for edge, name in CATEGORIES:
        if pm <= edge:
            return name
    return CATEGORIES[-1][1]


def f_rh(rh_pct, g):
    rh = np.minimum(np.asarray(rh_pct, float) / 100.0, 0.85)
    return (1.0 - rh) ** (-g)


def pm25(beta_Mm, rh_pct, alpha, g):
    return np.maximum(np.asarray(beta_Mm, float) - BETA_AIR, 0.0) / (alpha * f_rh(rh_pct, g))


OFFSET = 2.0  # ug/m3, keeps log residuals sane near zero


def fit_alpha_g(beta_Mm, rh_pct, pm_obs, fix_g: float | None = None):
    """Least squares in log(PM + 2). Returns (alpha, g, log-residual quantiles for the range)."""
    beta_Mm, rh_pct, pm_obs = map(lambda a: np.asarray(a, float), (beta_Mm, rh_pct, pm_obs))

    def res(p):
        a, g = (p[0], fix_g) if fix_g is not None else p
        return np.log(pm25(beta_Mm, rh_pct, a, g) + OFFSET) - np.log(pm_obs + OFFSET)

    p0, lo, hi = ([4.0], [0.5], [30.0]) if fix_g is not None else ([4.0, 0.4], [0.5, 0.0], [30.0, 2.0])
    sol = least_squares(res, p0, bounds=(lo, hi), loss="soft_l1", f_scale=0.3)
    a, g = (sol.x[0], fix_g) if fix_g is not None else sol.x
    r = res(sol.x)
    return float(a), float(g), (float(np.percentile(r, 10)), float(np.percentile(r, 90)))


def pm_range(pm_point, q):
    """Empirical 10-90% range from training log residuals: obs ~ pred * exp(-r)."""
    lo = (pm_point + OFFSET) * np.exp(-q[1]) - OFFSET
    hi = (pm_point + OFFSET) * np.exp(-q[0]) - OFFSET
    return np.maximum(lo, 0.0), hi
