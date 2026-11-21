"""Skyline ridges along view headings from Edwards Junction (35.8482,-93.3616, 2215 ft) using USGS EPQS (no key).
One request at a time. Outputs distance of each local maximum in elevation angle (visible ridge) per heading."""
import json, math, time, urllib.request
LAT, LON, H_CAM = 35.8482, -93.3616, 2215 * 0.3048 + 10
R = 6371000
def elev(lat, lon):
    u = f"https://epqs.nationalmap.gov/v1/json?x={lon:.6f}&y={lat:.6f}&units=Meters&wkid=4326"
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "pluma-research"}), timeout=30) as r:
        return float(json.loads(r.read())["value"])
out = {}
for hd in (100, 120):
    prof = []
    for k in range(1, 41):
        d = 500.0 * k if k <= 20 else 10000 + 1000.0 * (k - 20)   # 0.5-10 km every 500 m, 11-30 km every 1 km
        la = LAT + d * math.cos(math.radians(hd)) / 111320
        lo = LON + d * math.sin(math.radians(hd)) / (111320 * math.cos(math.radians(LAT)))
        try: z = elev(la, lo)
        except Exception as e: z = float("nan")
        ang = math.degrees(math.atan2(z - H_CAM - d * d / (2 * R) * 0.87, d))
        prof.append((d, z, ang)); time.sleep(0.2)
    vis, run = [], -90
    for d, z, a in prof:
        if a > run: vis.append((d, z, round(a, 3))); run = a
    out[hd] = dict(profile=prof, visible_rising=vis)
    print(hd, "visible (rising-angle) points:", [(int(d), int(z), a) for d, z, a in vis], flush=True)
json.dump(out, open("out/arkansas/skyline_profile.json", "w"), indent=1)
