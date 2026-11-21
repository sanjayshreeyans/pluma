"""Build step 3: fit alpha and g on one period, score PM2.5 on the other.

Camera extinction is computed blind to PM (pluma.lookrock). PM reference is the
NPS on-site TEOM at Look Rock, read from the NPS AirWebCams archive metadata.
Run: PYTHONPATH=. uv run python scripts/step3_calibrate.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr

from pluma.lookrock import run_period, site_values
from pluma.convert import fit_alpha_g, pm25, pm_range, category, CATEGORIES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/step3"
OUT.mkdir(parents=True, exist_ok=True)

REF_NOTE = ("PM2.5 reference: NPS on-site TEOM at Look Rock (from NPS AirWebCams archive metadata), "
            "not an EPA file. TEOMs can read low in heavy smoke.")

periods = {
    "Nov 2016": dict(frames=sorted((ROOT / "data/frames/lookrock").glob("grsm_2016*.jpg")),
                     meta=sorted((ROOT / "data/nps_meta").glob("r*.json")), ref="20161120_1200"),
    "Jun 2016": dict(frames=sorted((ROOT / "data/frames/lookrock_jun2016").glob("grsm_2016*.jpg")),
                     meta=sorted((ROOT / "data/nps_meta_2016summer").glob("r0616_*.json")), ref="20160608_1200"),
}

# ---- 1. camera pass (blind to PM) ----
rows = []
for name, p in periods.items():
    rows += run_period(p["frames"], site_values(p["meta"]), p["ref"], name)


def usable(r):
    return (not r["is_ref"]) and r["cloud_ok"] and r["rh_ok"] and r["pm"] is not None


print(f"{'frame':14s} {'per':8s} {'camβ':>6s} {'siteβ':>6s} {'PM':>6s} {'RH':>4s} {'tex':>5s}  gate")
for r in rows:
    g = "REF" if r["is_ref"] else ("ok" if usable(r) else
         ("cloud" if not r["cloud_ok"] else "RH>85" if not r["rh_ok"] else "no PM"))
    sb = f"{r['site_beta']:.0f}" if r["site_beta"] else "-"
    pm = f"{r['pm']:.1f}" if r["pm"] is not None else "-"
    print(f"{r['frame']:14s} {r['period']:8s} {r['cam_beta']:6.0f} {sb:>6s} {pm:>6s} {r['rh'] or 0:4.0f} {r['sky_texture']:5.1f}  {g}")

U = {k: [r for r in rows if r["period"] == k and usable(r)] for k in periods}
for k, v in U.items():
    print(f"{k}: {len(v)} usable frames")


def arr(rs, key):
    return np.array([r[key] for r in rs], float)


# ---- 2. haze fallback: camera vs site extinction (no calibration involved) ----
haze = {}
for k, rs in U.items():
    rs2 = [r for r in rs if r["site_beta"]]
    if len(rs2) > 2:
        haze[k] = dict(n=len(rs2), spearman=spearmanr(arr(rs2, "cam_beta"), arr(rs2, "site_beta"))[0])
print("\nhaze fallback:", json.dumps(haze, indent=1))


# ---- 3. calibrate on one, score the other ----
def score(rs, a, g, q):
    pm_hat = pm25(arr(rs, "cam_beta"), arr(rs, "rh"), a, g)
    obs = arr(rs, "pm")
    lo, hi = pm_range(pm_hat, q)
    cat_hat = [category(x) for x in pm_hat]
    cat_obs = [category(x) for x in obs]
    return dict(
        n=len(rs), spearman=float(spearmanr(pm_hat, obs)[0]) if len(rs) > 2 else None,
        mae=float(np.mean(np.abs(pm_hat - obs))), bias=float(np.mean(pm_hat - obs)),
        category_match=float(np.mean([a_ == b_ for a_, b_ in zip(cat_hat, cat_obs)])),
        in_range=float(np.mean((obs >= lo) & (obs <= hi))),
    ), pm_hat, lo, hi


results = {}
for train, test in [("Nov 2016", "Jun 2016"), ("Jun 2016", "Nov 2016")]:
    tr, te = U[train], U[test]
    out = {}
    for label, fix in [("with humidity (fit g)", None), ("no humidity (g=0)", 0.0)]:
        a, g, q = fit_alpha_g(arr(tr, "cam_beta"), arr(tr, "rh"), arr(tr, "pm"), fix_g=fix)
        s_tr, *_ = score(tr, a, g, q)
        s_te, pm_hat, lo, hi = score(te, a, g, q)
        out[label] = dict(alpha=a, g=g, q=q, train=s_tr, test=s_te,
                          test_points=[dict(frame=r["frame"], obs=r["pm"], rh=r["rh"], pred=float(p), lo=float(l), hi=float(h))
                                       for r, p, l, h in zip(te, pm_hat, lo, hi)])
    results[f"train {train} -> test {test}"] = out

for k, v in results.items():
    print(f"\n== {k}")
    for lab, o in v.items():
        t = o["test"]
        print(f"  {lab:22s} alpha={o['alpha']:.2f} g={o['g']:.2f} | test n={t['n']} rho={t['spearman']:.2f} "
              f"MAE={t['mae']:.1f} bias={t['bias']:+.1f} cat={t['category_match']:.0%} in-range={t['in_range']:.0%}")

# ---- 4. plots ----
fig, axs = plt.subplots(1, 3, figsize=(17, 5.6))
for ax, (k, v) in zip(axs[:2], results.items()):
    o = v["with humidity (fit g)"]
    pts = o["test_points"]
    obs = np.array([p["obs"] for p in pts]); pr = np.array([p["pred"] for p in pts])
    lo = np.array([p["lo"] for p in pts]); hi = np.array([p["hi"] for p in pts])
    rh = np.array([p["rh"] for p in pts])
    for e, name in CATEGORIES[:-1]:
        ax.axhline(e, color="#ddd", lw=0.8); ax.axvline(e, color="#ddd", lw=0.8)
    ax.errorbar(obs, pr, yerr=[pr - lo, hi - pr], fmt="none", ecolor="#bbb", lw=0.8)
    sc = ax.scatter(obs, pr, c=rh, cmap="viridis", vmin=30, vmax=85, s=36, zorder=3)
    for p in pts:
        ax.annotate(p["frame"][4:8], (p["obs"], p["pred"]), fontsize=6, xytext=(3, 2), textcoords="offset points")
    m = max(obs.max(), pr.max()) * 1.15 + 5
    ax.plot([0, m], [0, m], "k--", lw=0.8)
    ax.set_xlim(0, m); ax.set_ylim(0, m)
    t = o["test"]
    ax.set_title(f"{k}\nalpha={o['alpha']:.2f}, g={o['g']:.2f}  |  n={t['n']}  rho={t['spearman']:.2f}  "
                 f"MAE={t['mae']:.1f}  category={t['category_match']:.0%}", fontsize=9)
    ax.set_xlabel("PM2.5, NPS on-site TEOM (µg/m³)"); ax.set_ylabel("PM2.5 from camera (µg/m³)")
    plt.colorbar(sc, ax=ax, label="RH %", fraction=0.04)

ax = axs[2]
for k, rs in U.items():
    rs2 = [r for r in rs if r["site_beta"]]
    ax.scatter(arr(rs2, "site_beta"), arr(rs2, "cam_beta"), label=f"{k} (rho={haze.get(k, {}).get('spearman', float('nan')):.2f})", s=30)
ax.plot([10, 3000], [10, 3000], "k--", lw=0.8)
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(10, 3000); ax.set_ylim(10, 3000)
ax.set_xlabel("site extinction 3.912/VR (Mm⁻¹)"); ax.set_ylabel("camera extinction (Mm⁻¹)")
ax.set_title("Fallback: haze/extinction, no PM calibration", fontsize=9); ax.legend(fontsize=8); ax.grid(alpha=0.3, which="both")
fig.text(0.5, 0.005, REF_NOTE + "  Usable = cloud gate passed, RH ≤ 85%, reference frame excluded. Grey bars: 10–90% range from training residuals.",
         ha="center", fontsize=8, style="italic")
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(OUT / "pm25_cross_season.png", dpi=130)

(OUT / "step3_results.json").write_text(json.dumps(dict(rows=rows, haze=haze, results=results, note=REF_NOTE),
                                                   indent=1, default=float))
print("wrote", OUT / "pm25_cross_season.png")
