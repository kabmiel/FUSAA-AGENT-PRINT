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
VIDEO_STAGING = MEDIA / ".recording"
BASE_URL = os.environ.get("FUSAA_DEMO_URL", "http://127.0.0.1:8765")
ADMIN_URL = os.environ.get("FUSAA_DEMO_ADMIN_URL", f"{BASE_URL.rstrip('/')}/admin")
EMAIL = "demo@fusaa-agent.com"
PASSWORD = "FusaaDemo2026!"
VIDEO_DURATION_MS = int(os.environ.get("FUSAA_VIDEO_DURATION_MS", "180000"))
SCENE_SCALE = float(os.environ.get("FUSAA_SCENE_SCALE", "1"))


def hold(page, seconds: int):
    """Leave each scene on screen long enough for a three-minute narration."""
    page.wait_for_timeout(max(0, int(seconds * 1_000 * SCENE_SCALE)))


def stage(label: str):
    print(f"[capture] {label}", flush=True)


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
    VIDEO_STAGING.mkdir(parents=True, exist_ok=True)
    wait_for_server()
    token = login_token()
    with sync_playwright() as playwright:
        stage("ouverture du navigateur")
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1600, "height": 900},
            record_video_dir=str(VIDEO_STAGING),
            record_video_size={"width": 1280, "height": 720},
            color_scheme="dark",
        )
        page = context.new_page()
        page.set_default_timeout(15_000)
        browser_errors = []
        page.on("pageerror", lambda error: browser_errors.append(f"page: {error}"))
        page.on(
            "console",
            lambda message: browser_errors.append(f"console: {message.text}")
            if message.type == "error"
            else None,
        )
        recording_started_at = time.monotonic()
        # The installed Playwright version accepts one script argument only.
        # JSON encoding keeps the locally-issued token safe inside the script.
        page.add_init_script(
            f"""
            (() => {{
              localStorage.setItem('token', {json.dumps(token)});
              localStorage.setItem('fusaa-theme', 'dark');
              localStorage.removeItem('org');
              localStorage.removeItem('workshop');
            }})()
            """
        )
        stage("vue d'ensemble")
        page.goto(ADMIN_URL, wait_until="domcontentloaded", timeout=15_000)
        try:
            page.wait_for_selector("#app:not(.hidden)")
            page.wait_for_selector("#dashboard.active")
        except Exception:
            page.screenshot(path=str(MEDIA / "debug-session-loading.png"), full_page=True)
            state = page.evaluate(
                """() => ({
                  token_present: Boolean(localStorage.getItem('token')),
                  app_class: document.getElementById('app')?.className,
                  loader_class: document.getElementById('sessionLoading')?.className,
                  loader_text: document.getElementById('sessionLoadingDetail')?.textContent,
                  body_text: document.body.innerText.slice(0, 500)
                })"""
            )
            print(f"[capture] diagnostic={json.dumps(state, ensure_ascii=True)}", flush=True)
            for error in browser_errors:
                print(f"[capture] {error}", flush=True)
            raise
        page.screenshot(path=str(MEDIA / "01-vue-ensemble.png"), full_page=True)
        hold(page, 25)

        stage("tableau de bord facturation")
        page.locator('a[data-view="billing"]').click()
        page.wait_for_selector("#billingWorkspaceContent .billing-landing")
        page.screenshot(path=str(MEDIA / "02-facturation-tableau-de-bord.png"), full_page=True)
        hold(page, 25)

        stage("documents")
        page.locator('button[data-billtab="documents"]').click()
        page.wait_for_selector("#billingGlassDialog[open] .billing-table")
        page.screenshot(path=str(MEDIA / "03-documents-facturation.png"), full_page=True)
        hold(page, 25)

        stage("parametres concurrence")
        page.locator('#billingGlassDialog button:has-text("Concurrence")').first.click()
        page.wait_for_selector("#billingCompetitionDialog[open]")
        page.screenshot(path=str(MEDIA / "04-concurrence-parametres.png"), full_page=True)
        hold(page, 30)

        stage("generation du devis")
        page.locator('[data-competition-margin="10"]').click()
        page.locator("#billingCompetitionForm button[type=submit]").click()
        page.wait_for_selector("#fusaaOperation.active")
        page.screenshot(path=str(MEDIA / "05-generation-animee.png"), full_page=True)
        hold(page, 8)
        stage("brouillon a verifier")
        page.wait_for_selector("#billingWorkspaceContent #billingNewForm")
        page.wait_for_timeout(850)
        page.screenshot(path=str(MEDIA / "06-brouillon-concurrence.png"), full_page=True)
        hold(page, 42)

        # UI transitions take a variable amount of time.  Calculate the final
        # hold from a monotonic clock so the WebM lasts at least three minutes.
        elapsed_ms = int((time.monotonic() - recording_started_at) * 1_000)
        page.wait_for_timeout(max(0, VIDEO_DURATION_MS - elapsed_ms))

        stage("finalisation du fichier")
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
