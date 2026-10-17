"""Screenshot the prototypes: 1440x900 and 390x844, dark and light (full page).

    python3 docs/design_v2/shoot.py [outdir]
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "shots"
OUT.mkdir(parents=True, exist_ok=True)
SIZES = {"desktop": (1440, 900), "mobile": (390, 844)}

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    kw = {"executable_path": exe} if Path(exe).is_file() else {}
    browser = p.chromium.launch(**kw)
    for page_name in ("home", "company"):
        for size, (w, h) in SIZES.items():
            for scheme in ("dark", "light"):
                ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=scheme,
                                          device_scale_factor=1, reduced_motion="reduce")
                pg = ctx.new_page()
                errors = []
                pg.on("pageerror", lambda e: errors.append(str(e)))
                pg.goto((HERE / f"{page_name}.html").as_uri())
                pg.wait_for_timeout(300)
                pg.screenshot(path=str(OUT / f"{page_name}-{size}-{scheme}.png"), full_page=True)
                pg.screenshot(path=str(OUT / f"{page_name}-{size}-{scheme}-fold.png"))
                if errors:
                    print(page_name, size, scheme, "JS ERRORS:", errors)
                ctx.close()
    browser.close()
print("shots in", OUT)
