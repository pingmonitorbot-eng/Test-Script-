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


def main() -> int:
    print("== Temp Numbers GA smoke test ==")
    print(f"login_url={LOGIN_URL}")
    print(f"target_url={TARGET_URL}")
    print(f"user={USERNAME}")

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
            print("[1] Opening login page...")
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.wait_for_selector("#nl-username", timeout=30000)
            print("[1] Login page OK")

            print("[2] Filling credentials...")
            page.fill("#nl-username", USERNAME)
            page.fill("#nl-password", PASSWORD)
            page.click("button.nl-submit, button[type='submit']")

            # Wait until we leave /login
            for i in range(30):
                time.sleep(1)
                url = page.url
                if "/login" not in url:
                    break
                if i in (5, 10, 15, 20):
                    print(f"[2] still on login... {url}")
            else:
                print(f"[FAIL] Still on login page: {page.url}")
                try:
                    page.screenshot(path="login_fail.png", full_page=True)
                    print("[info] screenshot saved: login_fail.png")
                except Exception:
                    pass
                browser.close()
                return 1

            print(f"[2] Login OK — url={page.url}")
            print("[SUCCESS] Logged in successfully")

            print("[3] Opening target page gen-stats...")
            page.goto(TARGET_URL, wait_until="domcontentloaded")
            time.sleep(3)

            url = page.url
            title = page.title()
            body = page.inner_text("body")[:500].replace("\n", " | ")

            if "/login" in url:
                print(f"[FAIL] Redirected back to login: {url}")
                browser.close()
                return 1

            print(f"[3] Target URL: {url}")
            print(f"[3] Title: {title}")
            print(f"[3] Body snippet: {body}")

            # Markers that gen-stats UI loaded
            markers = ["Gen. SMS", "Generated SMS", "Show Report", "From", "RECEIVED"]
            found = [m for m in markers if m.lower() in (title + body).lower() or m in page.content()]
            print(f"[3] UI markers found: {found or 'none'}")

            # Optional: confirm session via /api/me inside browser
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
            print(f"[4] /api/me status={me.get('status')} body={str(me.get('body'))[:200]}")

            if me.get("status") == 200 and USERNAME in str(me.get("body", "")):
                print("[SUCCESS] Session confirmed via /api/me")
            else:
                print("[WARN] /api/me did not confirm user (page may still be OK)")

            print("[SUCCESS] Reached target page gen-stats")
            print("== ALL CHECKS PASSED ==")
            browser.close()
            return 0

        except Exception as e:
            print(f"[FAIL] Exception: {e}")
            try:
                page.screenshot(path="error.png", full_page=True)
                print("[info] screenshot saved: error.png")
            except Exception:
                pass
            browser.close()
            return 1


if __name__ == "__main__":
    sys.exit(main())
