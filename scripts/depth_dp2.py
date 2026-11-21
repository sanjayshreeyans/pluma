"""Depth Pro 2 (B) on one image. Run from third_party/ml-depth-pro-2 with its .venv.
Weights are research-only (Apple ML Research Model License)."""
import sys, time
import numpy as np, torch
from depth_pro_2 import create_model_and_transforms, load_rgb
src, out = sys.argv[1], sys.argv[2]
model, transform = create_model_and_transforms("depthpro2-b")
model.eval()
rgb, f_px = load_rgb(src)
t = time.time()
with torch.no_grad():
    o = model.infer(transform(rgb), f_px=f_px)
depth = o["depth"].float().cpu().numpy()
print("device", next(model.parameters()).device, "time %.1fs" % (time.time() - t),
      "f_px", float(o["focallength_px"]), "shape", depth.shape,
      "finite range", np.nanmin(depth[np.isfinite(depth)]), np.nanmax(depth[np.isfinite(depth)]), "inf px", int((~np.isfinite(depth)).sum()))
np.save(out, depth)
