"""Fetch Nov 2016 Look Rock frames on the hour 10:00-16:00 EST, one request at a time, 2 s apart. Reuses files on disk."""
import json, glob, time, sys
from pathlib import Path
from pluma.ingest.nps_archive import fetch_frame
out = Path("data/frames/lookrock"); out.mkdir(parents=True, exist_ok=True)
todo = []
for f in sorted(glob.glob("data/nps_meta/r*.json")):
    for r in json.load(open(f)).get("Results", []):
        a = r["Asset"]; t = a["LocalTimeString"]
        m, d, rest = t.split("/", 2); y, hm, ap = rest.split(" ")[:3]
        hh, mm = map(int, hm.split(":")); hh = hh % 12 + (12 if ap == "PM" else 0)
        if mm == 0 and 10 <= hh <= 16:
            todo.append((f"{y}{int(m):02d}{int(d):02d}_{hh:02d}00", a["AssetID"]))
print("candidates", len(todo), flush=True)
n = 0
for key, aid in todo:
    p = out / f"grsm_{key}.jpg"
    if p.exists(): continue
    try:
        fetch_frame(aid, p); n += 1
    except Exception as e:
        print("fail", key, e, flush=True)
    time.sleep(2)
print("fetched", n, flush=True)
