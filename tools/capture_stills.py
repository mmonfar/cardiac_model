"""Re-capture the README / docs stills from the running app, the same way every release.

Starts the planner on a free local port, captures each page at 390, 768 and 1280 px
(first screen + full page) into ``docs/screenshots/v2.2/``, then stops the server.

    PYTHONPATH=src python tools/capture_stills.py [--python PATH]

Needs ``playwright`` (``python -m playwright install chromium``) for the capture itself;
``--python`` picks the interpreter that has the app's dependencies.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots" / "v2.2"
PAGES = {"": "summary", "diagnosis": "diagnosis", "assumptions": "assumptions"}
WIDTHS = {390: 844, 768: 1024, 1280: 800}
SETTLE_S = 60  # the summary page runs the simulation before it draws


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_up(url: str, timeout: float = 60) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except OSError:
            time.sleep(1)
    raise SystemExit(f"app did not start at {url}")


def name(page: str, width: int, kind: str) -> str:
    prefix = "after" if page == "summary" else f"after-{page}"
    return f"{prefix}-{width}-{kind}.png"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()
    port = free_port()
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    server = subprocess.Popen(
        [args.python, "-m", "streamlit", "run", "src/cardiac_capacity_planner/app.py",
         "--server.port", str(port), "--server.headless", "true"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        base = f"http://127.0.0.1:{port}/"
        wait_up(base)
        OUT.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for path, page_name in PAGES.items():
                for width, height in WIDTHS.items():
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.goto(base + path)
                    page.wait_for_selector(".ccp-band", timeout=SETTLE_S * 1000)
                    page.wait_for_function(
                        "!document.querySelector('[data-testid=\"stStatusWidget\"]')",
                        timeout=SETTLE_S * 1000,
                    )
                    page.wait_for_timeout(1500)
                    logos = page.locator(
                        '[data-testid="stSidebarLogo"]:visible, [data-testid="stHeaderLogo"]:visible'
                    ).count()
                    if logos != 1:
                        raise SystemExit(f"{page_name} at {width}px shows {logos} logos, expected 1")
                    page.screenshot(path=OUT / name(page_name, width, "first-screen"))
                    # Streamlit scrolls inside its main panel, so grow the viewport to the
                    # panel's height instead of relying on full_page.
                    tall = page.evaluate(
                        "Math.max(...[...document.querySelectorAll("
                        "'[data-testid=\"stMain\"], [data-testid=\"stAppViewContainer\"]')]"
                        ".map(e => e.scrollHeight))"
                    )
                    page.set_viewport_size({"width": width, "height": max(height, int(tall))})
                    page.wait_for_timeout(1500)
                    page.screenshot(path=OUT / name(page_name, width, "full"))
                    print("captured", page_name, width)
                    page.close()
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=20)


if __name__ == "__main__":
    main()
