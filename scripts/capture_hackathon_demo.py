"""Capture a real local FUSAA billing walkthrough and record its WebM video."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs" / "hackathon" / "media"
BASE_URL = os.environ.get("FUSAA_DEMO_URL", "http://127.0.0.1:8765")
EMAIL = "demo@fusaa-agent.com"
PASSWORD = "FusaaDemo2026!"


def login_token() -> str:
    payload = json.dumps({"email": EMAIL, "password": PASSWORD}).encode("utf-8")
    request = Request(
        f"{BASE_URL}/api/v1/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.load(response)["access_token"]


def wait_for_server(retries: int = 30):
    for _ in range(retries):
        try:
            with urlopen(f"{BASE_URL}/readyz", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(1)
    raise RuntimeError(f"FUSAA ne répond pas sur {BASE_URL}")


def main():
    MEDIA.mkdir(parents=True, exist_ok=True)
    wait_for_server()
    token = login_token()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1600, "height": 900},
            record_video_dir=str(MEDIA),
            record_video_size={"width": 1280, "height": 720},
            color_scheme="dark",
        )
        page = context.new_page()
        page.add_init_script(
            """
            ([token]) => {
              localStorage.setItem('token', token);
              localStorage.setItem('fusaa-theme', 'dark');
              localStorage.removeItem('org');
              localStorage.removeItem('workshop');
            }
            """,
            [token],
        )
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector("#app:not(.hidden)")
        page.wait_for_selector("#dashboard.active")
        page.screenshot(path=str(MEDIA / "01-vue-ensemble.png"), full_page=True)

        page.locator('a[data-view="billing"]').click()
        page.wait_for_selector("#billingWorkspaceContent .billing-landing")
        page.screenshot(path=str(MEDIA / "02-facturation-tableau-de-bord.png"), full_page=True)

        page.locator('button[data-billtab="documents"]').click()
        page.wait_for_selector("#billingGlassDialog[open] .billing-table")
        page.screenshot(path=str(MEDIA / "03-documents-facturation.png"), full_page=True)

        page.locator('#billingGlassDialog button:has-text("Concurrence")').first.click()
        page.wait_for_selector("#billingCompetitionDialog[open]")
        page.screenshot(path=str(MEDIA / "04-concurrence-parametres.png"), full_page=True)

        page.locator('[data-competition-margin="10"]').click()
        page.locator("#billingCompetitionForm button[type=submit]").click()
        page.wait_for_selector("#fusaaOperation.active")
        page.screenshot(path=str(MEDIA / "05-generation-animee.png"), full_page=True)
        page.wait_for_selector("#billingWorkspaceContent #billingNewForm")
        page.wait_for_timeout(850)
        page.screenshot(path=str(MEDIA / "06-brouillon-concurrence.png"), full_page=True)

        video = page.video
        context.close()
        if video:
            video_path = Path(video.path())
            target = MEDIA / "fusaa-hackathon-demo.webm"
            if target.exists():
                target.unlink()
            video_path.replace(target)
        browser.close()


if __name__ == "__main__":
    main()
