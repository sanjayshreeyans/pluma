"""Export data for the static site (site/). Values copied as computed."""
import json, shutil
from pathlib import Path
import numpy as np
from PIL import Image
from pluma.regions_lookrock import LANDMARKS, MILE

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "site"
rows = json.loads((ROOT / "out/demo/rows.json").read_text())
head = json.loads((ROOT / "out/demo/headline.json").read_text())
out = []
for r in rows:
    shutil.copy2(ROOT / "data/frames/lookrock" / r["file"], S / "frames" / r["file"])
    out.append({k: r.get(k) for k in ["timestamp", "file", "gate", "reject_reason", "cam_beta", "site_beta", "pred_pm25",
                                       "monitor_pm25", "rh", "split", "category", "monitor_category"]})
(S / "data/lookrock.json").write_text(json.dumps(out, default=float))

dist = np.load(ROOT / "out/depth/lookrock_distance_m.npy")[200:720]
sky = np.load(ROOT / "out/depth/lookrock_sky.npy")[200:720]
LO, HI = np.log10(40), np.log10(70000)
v = np.clip((np.log10(np.where(sky, 40, dist)) - LO) / (HI - LO), 0, 1) * 254 + 1
v[sky] = 0
Image.fromarray(v.astype(np.uint8)).save(S / "data/distance.png")
ridges = [dict(name=n, miles=mi, km=round(mi * MILE / 1000, 1), x=(b[0] + b[1]) / 2 / 1000, y=(b[2] - 200) / 520)
          for n, (mi, b) in LANDMARKS.items()]
(S / "data/meta.json").write_text(json.dumps(dict(headline=head, ridges=ridges, crop=[200, 720],
                                                 distance_encoding=dict(log10_min=LO, log10_max=HI, sky=0)), indent=1, default=float))
print("rows", len(out), "frames copied; distance.png", v.shape)
