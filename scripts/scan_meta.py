"""Scan NPS archive metadata (search results only, no images), one day at a time, 1 s apart."""
import json, sys, time, datetime
from pathlib import Path
from pluma.ingest.nps_archive import search_day
start, end, outdir = sys.argv[1], sys.argv[2], Path(sys.argv[3])
d = datetime.date.fromisoformat(start); e = datetime.date.fromisoformat(end)
while d <= e:
    f = outdir / f"r{d:%Y%m%d}.json"
    if not f.exists():
        f.write_text(json.dumps(search_day(d.strftime("%m/%d/%Y"))))
        time.sleep(1)
    print(d, "ok", flush=True)
    d += datetime.timedelta(days=1)
