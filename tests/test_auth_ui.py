"""One small browser check. All HTTP responses are mocked; no real accounts."""
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

playwright = pytest.importorskip("playwright.sync_api")
WEB = Path(__file__).parents[1] / "backend/app/web"


def test_login_enter_and_activation_recovery_forms():
    with playwright.sync_playwright() as driver:
        try: browser = driver.chromium.launch(headless=True)
        except Exception as error: pytest.skip(f"Chromium indisponible : {error}")
        page = browser.new_page()
        page.set_default_timeout(5000)
        errors, posts = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        def serve(route):
            request = route.request
            path = urlsplit(request.url).path
            if request.method == "POST":
                body = request.post_data_json
                posts.append((path, body))
                if path.endswith("/login"):
                    route.fulfill(status=401, json={"detail": "Mot de passe incorrect"})
                elif path.endswith("/inspect"):
                    route.fulfill(json={"email": "invite@example.com", "display_name": "Invitation FUSAA en attente"})
                else: route.fulfill(json={"access_token": "new-account-token"})
            elif path == "/admin":
                html = '<h1>Espace FUSAA</h1>' if any(p.endswith("/register") or p.endswith("/reset") for p, _ in posts) else (WEB / "index.html").read_text(encoding="utf-8")
                route.fulfill(content_type="text/html", body=html)
            elif path in {"/inscription", "/reinitialiser"}:
                route.fulfill(content_type="text/html", body=(WEB / ("register.html" if path == "/inscription" else "password-reset.html")).read_text(encoding="utf-8"))
            elif path.endswith((".js", ".css")) and (WEB / path.lstrip("/")).is_file():
                route.fulfill(content_type="application/javascript" if path.endswith(".js") else "text/css", body=(WEB / path.lstrip("/")).read_text(encoding="utf-8"))
            else: route.fulfill(status=404, json={"detail": "Mock: aucune requête réelle"})
        page.route("**/*", serve)
        page.goto("http://auth-ui.test/admin")
        assert page.locator('#auth a[href="/boutique"]').is_visible()
        assert page.locator("#accountPasswordForm").count() == 1
        page.locator("#email").fill("invite@example.com")
        page.locator("#password").fill("1234")
        page.locator("#password").press("Enter")
        page.locator("#loginFeedback").filter(has_text="Mot de passe incorrect").wait_for()
        assert sum(path.endswith("/login") for path, _ in posts) == 1
        assert page.locator("#loginSubmit").is_enabled()
        page.goto("http://auth-ui.test/inscription?email=invite%40example.com#token=" + "a" * 43)
        page.wait_for_function("document.getElementById('authEmail').readOnly")
        page.locator("#authName").fill("Invité")
        page.locator("#authPassword").fill("1234")
        page.locator("#authConfirm").fill("1234")
        page.evaluate("localStorage.org='inviter-org';localStorage.workshop='inviter-workshop'")
        page.locator("#authConfirm").press("Enter")
        page.get_by_role("heading", name="Espace FUSAA").wait_for()
        activation = next(body for path, body in posts if path.endswith("/register"))
        assert activation["display_name"] == "Invité" and activation["invitation_token"] == "a" * 43
        assert page.evaluate("localStorage.getItem('org')") is None
        page.goto("http://auth-ui.test/reinitialiser#token=" + "r" * 43)
        page.locator("#authLinkForm").wait_for(state="visible")
        page.locator("#authPassword").fill("abcd")
        page.locator("#authConfirm").fill("abcd")
        page.locator("#authConfirm").press("Enter")
        page.get_by_role("heading", name="Espace FUSAA").wait_for()
        reset = next(body for path, body in posts if path.endswith("/reset"))
        assert reset == {"token": "r" * 43, "password": "abcd"}
        assert page.evaluate("localStorage.getItem('token')") == "new-account-token"
        assert not errors
        browser.close()
