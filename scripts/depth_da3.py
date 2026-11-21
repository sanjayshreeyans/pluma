"""DA3-SMALL on one image, using Ariadne's installed package and weights (Ariadne unchanged)."""
import sys, time
import numpy as np
from PIL import Image
from depth_anything_3.api import DepthAnything3
src, out = sys.argv[1], sys.argv[2]
import torch
dev = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
m = DepthAnything3.from_pretrained("/Users/sanjayj/Documents/Ariadne/models/da3-small").to(dev).eval()
t = time.time(); p = m.inference([src])
d = np.asarray(p.depth[0], np.float32)
W, H = Image.open(src).size
if d.shape != (H, W):
    d = np.asarray(Image.fromarray(d).resize((W, H), Image.BILINEAR))
print("device", dev, "time %.1fs" % (time.time() - t), "shape", d.shape, "range", d.min(), d.max())
np.save(out, d)
