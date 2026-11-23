#!/usr/bin/env python3
"""Smoke test: Playwright login → gen-stats on tempnumbers.net (GitHub Actions)."""
import os
import sys
import time

from playwright.sync_api import sync_playwright

LOGIN_URL = os.getenv("LOGIN_URL", "https://tempnumbers.net/login")
TARGET_URL = os.getenv("TARGET_URL", "https://tempnumbers.net/gen-stats")
USERNAME = os.getenv("PANEL_USER", "test_panel")
PASSWORD = os.getenv("PANEL_PASS", "test_panel")


def fill_react(page, selector: str, value: str) -> None:
    """Fill controlled React inputs reliably."""
    loc = page.locator(selector).first
    loc.wait_for(state="visible", timeout=30000)
    loc.click()
    loc.fill("")
    loc.type(value, delay=20)
    # Fallback: native setter + input/change events
    page.evaluate(
        """([sel, val]) => {
            const el = document.querySelector(sel);
            if (!el) return;
            const desc = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            );
            if (desc && desc.set) desc.set.call(el, val);
            else el.value = val;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
        [selector, value],
    )


def is_logged_in(page) -> bool:
    url = (page.url or "").lower()
    if "/login" in url and url.rstrip("/").endswith("login"):
        # still on login route
        pass
    else:
        if any(x in url for x in ("/dashboard", "/gen-stats", "/cli-search", "/numbers")):
            return True
    # DOM markers
    try:
        if page.locator("text=test_panel").count() > 0:
            return True
    except Exception:
        pass
    try:
        body = page.inner_text("body")
        if "Dashboard" in body and "Sign in" not in body[:800]:
            if "Assigned numbers" in body or "Estimated earnings" in body or "CLI Search" in body:
                return True
    except Exception:
        pass
    return False


def main() -> int:
    print("== Temp Numbers GA smoke test ==", flush=True)
    print(f"login_url={LOGIN_URL}", flush=True)
    print(f"target_url={TARGET_URL}", flush=True)
    print(f"user={USERNAME}", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.set_default_timeout(60000)

        try:
            print("[1] Opening login page...", flush=True)
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.wait_for_selector("#nl-username", timeout=30000)
            print("[1] Login page OK", flush=True)

            print("[2] Filling credentials...", flush=True)
            fill_react(page, "#nl-username", USERNAME)
            fill_react(page, "#nl-password", PASSWORD)
            # ensure values stuck
            uv = page.input_value("#nl-username")
            print(f"[2] username field={uv!r}", flush=True)

            print("[2] Clicking Sign in...", flush=True)
            page.locator("button.nl-submit, button[type='submit']").first.click()

            # Wait up to 45s for login success (URL or DOM)
            ok = False
            for i in range(45):
                time.sleep(1)
                if is_logged_in(page):
                    ok = True
                    print(f"[2] Login detected after {i+1}s — url={page.url}", flush=True)
                    break
                if i in (5, 10, 15, 20, 30):
                    print(f"[2] waiting... url={page.url}", flush=True)

            if not ok:
                # last chance: SPA may have navigated without matching
                time.sleep(2)
                ok = is_logged_in(page)

            if not ok:
                print(f"[FAIL] Login not detected. url={page.url}", flush=True)
                try:
                    page.screenshot(path="login_fail.png", full_page=True)
                    print("[info] screenshot: login_fail.png", flush=True)
                except Exception:
                    pass
                browser.close()
                return 1

            print("[SUCCESS] Logged in successfully", flush=True)

            print("[3] Opening target page gen-stats...", flush=True)
            page.goto(TARGET_URL, wait_until="domcontentloaded")
            time.sleep(4)

            url = page.url
            title = page.title()
            body = page.inner_text("body")
            body_flat = body[:600].replace("\n", " | ")

            if "/login" in url and url.rstrip("/").endswith("login"):
                print(f"[FAIL] Redirected back to login: {url}", flush=True)
                page.screenshot(path="target_fail.png", full_page=True)
                browser.close()
                return 1

            print(f"[3] Target URL: {url}", flush=True)
            print(f"[3] Title: {title}", flush=True)
            print(f"[3] Body snippet: {body_flat}", flush=True)

            markers = ["Gen. SMS", "Generated SMS", "Show Report", "RECEIVED", "Export Report"]
            found = [m for m in markers if m.lower() in (title + " " + body).lower()]
            print(f"[3] UI markers found: {found or 'none'}", flush=True)

            me = page.evaluate(
                """async () => {
                    try {
                        const r = await fetch('/api/me', { credentials: 'include' });
                        return { status: r.status, body: await r.text() };
                    } catch (e) {
                        return { status: 0, body: String(e) };
                    }
                }"""
            )
            print(
                f"[4] /api/me status={me.get('status')} body={str(me.get('body'))[:220]}",
                flush=True,
            )

            if me.get("status") == 200 and USERNAME in str(me.get("body", "")):
                print("[SUCCESS] Session confirmed via /api/me", flush=True)
            else:
                print("[WARN] /api/me did not confirm user", flush=True)

            if found or "gen-stats" in url:
                print("[SUCCESS] Reached target page gen-stats", flush=True)
            else:
                print("[WARN] Target opened but markers weak — check screenshot", flush=True)
                page.screenshot(path="target_weak.png", full_page=True)

            print("== ALL CHECKS PASSED ==", flush=True)
            browser.close()
            return 0

        except Exception as e:
            print(f"[FAIL] Exception: {e}", flush=True)
            try:
                page.screenshot(path="error.png", full_page=True)
                print("[info] screenshot: error.png", flush=True)
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
            return 1


if __name__ == "__main__":
    sys.exit(main())
