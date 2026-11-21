"""Visible skyline ridges along view headings from a camera, using USGS EPQS point elevations (no key).
One request at a time. Usage: skyline.py LAT LON ELEV_FT OUT.json HEADING [HEADING ...]"""
import json, math, sys, time, urllib.request
lat0, lon0, elev_ft, out = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
heads = [float(h) for h in sys.argv[5:]]
H_CAM = elev_ft * 0.3048 + 10; R = 6371000
def elev(lat, lon):
    u = f"https://epqs.nationalmap.gov/v1/json?x={lon:.6f}&y={lat:.6f}&units=Meters&wkid=4326"
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "pluma-research"}), timeout=30) as r:
        return float(json.loads(r.read())["value"])
res = {}
for hd in heads:
    prof = []
    dists = [250 * k for k in range(1, 21)] + [5000 + 1000 * k for k in range(1, 26)]
    for d in dists:
        la = lat0 + d * math.cos(math.radians(hd)) / 111320
        lo = lon0 + d * math.sin(math.radians(hd)) / (111320 * math.cos(math.radians(lat0)))
        try: z = elev(la, lo)
        except Exception: z = float("nan")
        ang = math.degrees(math.atan2(z - H_CAM - d * d / (2 * R) * 0.87, d))
        prof.append((d, z, ang)); time.sleep(0.15)
    vis, run = [], -90
    for d, z, a in prof:
        if a == a and a > run: vis.append((d, round(z), round(a, 3))); run = a
    # local maxima of elevation angle that are visible-ish (ridge crests)
    crests = [prof[i] for i in range(1, len(prof) - 1) if prof[i][2] > prof[i-1][2] and prof[i][2] >= prof[i+1][2]]
    res[hd] = dict(profile=prof, visible=vis, crests=[(d, round(z), round(a, 3)) for d, z, a in crests])
    print(hd, "visible:", [(int(d), z, a) for d, z, a in vis], flush=True)
json.dump(res, open(out, "w"), indent=1)
