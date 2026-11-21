"""Skyline ridge distances along view headings from AWS Terrain Tiles (Terrarium PNG, public, no key).
Tiles are fetched one at a time and cached. Usage: dem_profile.py LAT LON ELEV_FT OUT.json HEADING [HEADING...]"""
import io, json, math, sys, urllib.request
from pathlib import Path
import numpy as np
from PIL import Image
Z = 12
CACHE = Path("data/dem_tiles"); CACHE.mkdir(parents=True, exist_ok=True)
lat0, lon0, elev_ft, out = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
heads = [float(h) for h in sys.argv[5:]]
H_CAM = elev_ft * 0.3048 + 10; R = 6371000; tiles = {}
def tile_xy(lat, lon):
    n = 2 ** Z; x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y
def tile(tx, ty):
    k = (tx, ty)
    if k not in tiles:
        f = CACHE / f"{Z}_{tx}_{ty}.png"
        if not f.exists():
            u = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{tx}/{ty}.png"
            f.write_bytes(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "pluma-research"}), timeout=60).read())
        a = np.asarray(Image.open(f).convert("RGB"), float)
        tiles[k] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
    return tiles[k]
def elev(lat, lon):
    x, y = tile_xy(lat, lon); tx, ty = int(x), int(y)
    return float(tile(tx, ty)[min(int((y - ty) * 256), 255), min(int((x - tx) * 256), 255)])
z0 = elev(lat0, lon0)
res = dict(camera_ground_m=z0, camera_eye_m=H_CAM)
for hd in heads:
    prof = []
    for d in np.arange(100, 40001, 100.0):
        la = lat0 + d * math.cos(math.radians(hd)) / 111320
        lo = lon0 + d * math.sin(math.radians(hd)) / (111320 * math.cos(math.radians(lat0)))
        z = elev(la, lo)
        prof.append((float(d), z, math.degrees(math.atan2(z - H_CAM - d * d / (2 * R) * 0.87, d))))
    run, vis = -90, []
    for d, z, a in prof:
        if a > run: vis.append((d, z, a)); run = a
    # visible crests: points where the running-max angle rises and the terrain then drops behind
    crests = []
    for i in range(1, len(prof) - 1):
        d, z, a = prof[i]
        if a >= max(p[2] for p in prof[:i + 1]) and prof[i + 1][2] < a:
            crests.append((d, round(z), round(a, 3)))
    res[str(hd)] = dict(visible_crests_km=[round(c[0] / 1000, 1) for c in crests],
                        crests=crests, horizon_km=round(vis[-1][0] / 1000, 1))
    print(hd, "camera ground", round(z0), "m | visible crests (km):", res[str(hd)]["visible_crests_km"], "| horizon", res[str(hd)]["horizon_km"], "km", flush=True)
Path(out).write_text(json.dumps(res, indent=1))
