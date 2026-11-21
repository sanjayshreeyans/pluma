"""Record the site's Arkansas section (map, readings list, viewer) into a short video.
Run: uv run --no-project --with playwright python scripts/record_arkansas.py"""
import asyncio, glob, os, subprocess
from pathlib import Path
from PIL import Image
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/video_handoff"; CAP = OUT / "site_capture"; CAP.mkdir(parents=True, exist_ok=True)
exe = sorted(glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/*.app/Contents/MacOS/*")))[-1]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=exe)
        pg = await b.new_page(viewport={"width": 1280, "height": 1000}, device_scale_factor=2, color_scheme="light")
        await pg.goto("http://localhost:8420/?rec=ark")
        await pg.wait_for_function("document.getElementById('ark-now').children.length > 0 && document.getElementById('ark-map').children.length > 5")
        await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(400)
        await pg.locator("#ark-map-wrap").screenshot(path=str(CAP / "ark_1_map.png"))
        await pg.locator("#ark-now").screenshot(path=str(CAP / "ark_2_readings.png"))
        await pg.locator("#ark-viewer").screenshot(path=str(CAP / "ark_3_viewer_tunnel.png"))
        await b.close()

asyncio.run(main())

# compose onto 1920x1080 paper cards, then crossfade
W, H, PAPER = 1920, 1080, (244, 245, 242)
cards = []
for name in ["ark_1_map", "ark_2_readings", "ark_3_viewer_tunnel"]:
    im = Image.open(CAP / f"{name}.png").convert("RGB")
    s = min((W - 160) / im.width, (H - 140) / im.height)
    im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    c = Image.new("RGB", (W, H), PAPER); c.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    c.save(CAP / f"{name}_card.png"); cards.append(CAP / f"{name}_card.png")
hold, xf = [4.0, 3.5, 5.0], 0.6
args = ["ffmpeg", "-y", "-loglevel", "error"]
for c, hsec in zip(cards, hold):
    args += ["-loop", "1", "-t", str(hsec), "-i", str(c)]
f = f"[0:v][1:v]xfade=transition=fade:duration={xf}:offset={hold[0]-xf}[a];[a][2:v]xfade=transition=fade:duration={xf}:offset={hold[0]+hold[1]-2*xf},format=yuv420p[v]"
args += ["-filter_complex", f, "-map", "[v]", "-r", "30", "-c:v", "libx264", "-crf", "20", "-preset", "slow", "-movflags", "+faststart", str(OUT / "pluma_arkansas_reading.mp4")]
subprocess.run(args, check=True)
print("ok", round((OUT / "pluma_arkansas_reading.mp4").stat().st_size / 1e6, 2), "MB")
