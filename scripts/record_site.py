"""Record the site's Look Rock viewer hour by hour (from the first hour) plus stills, for the video.
Needs the site served at http://localhost:8420.
Run: uv run --with playwright python scripts/record_site.py
"""
import asyncio, glob, os
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/video_handoff/site_capture"
FR = OUT / "frames"; FR.mkdir(parents=True, exist_ok=True)
for f in FR.glob("*.png"): f.unlink()
URL = "http://localhost:8420/?rec=1"


def chromium_path():
    c = sorted(glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium"))) + \
        sorted(glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")))
    return c[-1] if c else None


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=chromium_path())
        page = await b.new_page(viewport={"width": 1280, "height": 1000}, device_scale_factor=2, color_scheme="light")
        await page.goto(URL); await page.wait_for_function("document.getElementById('when').textContent.includes('Nov')")
        await page.evaluate("document.fonts.ready")
        viewer = page.locator(".viewer").first
        tl = page.locator("#tl")
        await tl.focus()
        for _ in range(120):
            await page.keyboard.press("ArrowLeft")
        n = await page.evaluate("fetch('data/lookrock.json').then(r=>r.json()).then(j=>j.filter(r=>r.gate==='pass'&&r.pred_pm25!=null&&r.monitor_pm25!=null).length)")
        print("hours", n)
        for i in range(n):
            await page.wait_for_function("(() => { const im = document.getElementById('photo'); return im.complete && im.naturalWidth > 0; })()")
            await page.wait_for_timeout(120)
            await page.evaluate("document.activeElement && document.activeElement.blur()")
            await viewer.screenshot(path=str(FR / f"{i:03d}.png"))
            await tl.focus()
            await page.keyboard.press("ArrowRight")
        # stills
        await page.locator(".lead").screenshot(path=str(OUT / "still_lead.png"))
        await page.wait_for_function("document.getElementById('ark-now').children.length > 0")
        await page.locator("#arkansas").screenshot(path=str(OUT / "still_arkansas.png"))
        await page.locator("#depth").screenshot(path=str(OUT / "still_depth.png"))
        # 26 Nov still of the viewer
        await tl.focus()
        for _ in range(120):
            await page.keyboard.press("ArrowLeft")
        idx = await page.evaluate("fetch('data/lookrock.json').then(r=>r.json()).then(j=>j.filter(r=>r.gate==='pass'&&r.pred_pm25!=null&&r.monitor_pm25!=null).sort((a,b)=>a.timestamp<b.timestamp?-1:1).findIndex(r=>r.file.includes('20161126_1200')))")
        for _ in range(idx):
            await page.keyboard.press("ArrowRight")
        await page.wait_for_timeout(300)
        await page.evaluate("document.activeElement && document.activeElement.blur()")
        await viewer.screenshot(path=str(OUT / "still_viewer_26nov.png"))
        await b.close()

asyncio.run(main())
