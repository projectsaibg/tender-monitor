"""Browser automation via Playwright (Chromium).

Primary fetch path renders JavaScript-heavy pages. If Playwright or its browser
binary is unavailable, a static httpx fetch is used as a fallback so the app
still functions (with reduced JS support). Every URL is SSRF-validated before
any request is made.
"""
from __future__ import annotations

from contextlib import contextmanager

import httpx

import config
from utils import security
from utils.logging_setup import get_logger

log = get_logger("scanner")

try:
    from playwright.sync_api import sync_playwright
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    _PLAYWRIGHT_AVAILABLE = True
except Exception:  # pragma: no cover - only when playwright not installed
    _PLAYWRIGHT_AVAILABLE = False

    class PlaywrightTimeout(Exception):
        pass


def _result(ok=False, status=0, final_url="", title="", html="", screenshot="",
            error="", engine=""):
    return {
        "ok": ok, "status": status, "final_url": final_url, "title": title,
        "html": html, "screenshot": screenshot, "error": error, "engine": engine,
    }


def fetch_static(url, timeout=None, allow_private=None):
    """Fetch a page with httpx (no JS). Returns a result dict."""
    safe_url = security.validate_url(url, allow_private=allow_private)
    timeout = timeout or (config.BROWSER_TIMEOUT_MS / 1000.0)
    headers = {"User-Agent": config.USER_AGENT}
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        resp = client.get(safe_url)
        title = ""
        return _result(
            ok=resp.status_code < 400,
            status=resp.status_code,
            final_url=str(resp.url),
            title=title,
            html=resp.text,
            engine="httpx",
            error="" if resp.status_code < 400 else ("HTTP %d" % resp.status_code),
        )


def fetch_page(url, headless=True, timeout_ms=None, wait_until="domcontentloaded",
               screenshot_path=None, allow_private=None):
    """Fetch a rendered page. Falls back to httpx if Playwright is unavailable."""
    safe_url = security.validate_url(url, allow_private=allow_private)
    timeout_ms = timeout_ms or config.BROWSER_TIMEOUT_MS

    if not _PLAYWRIGHT_AVAILABLE:
        log.warning("Playwright unavailable; using static fetch for %s", safe_url)
        try:
            return fetch_static(safe_url, allow_private=allow_private)
        except Exception as exc:
            return _result(error="static fetch failed: %s" % exc, engine="httpx")

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            try:
                context = browser.new_context(user_agent=config.USER_AGENT)
                page = context.new_page()
                response = page.goto(safe_url, wait_until=wait_until, timeout=timeout_ms)
                try:
                    page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 8000))
                except PlaywrightTimeout:
                    pass
                html = page.content()
                title = page.title()
                status = response.status if response else 0
                final_url = page.url
                shot = ""
                if screenshot_path:
                    try:
                        page.screenshot(path=str(screenshot_path), full_page=True)
                        shot = str(screenshot_path)
                    except Exception:
                        shot = ""
                return _result(
                    ok=(status == 0 or status < 400),
                    status=status, final_url=final_url, title=title,
                    html=html, screenshot=shot, engine="playwright",
                    error="" if (status == 0 or status < 400) else ("HTTP %d" % status),
                )
            finally:
                browser.close()
    except PlaywrightTimeout as exc:
        return _result(error="timeout: %s" % exc, engine="playwright")
    except Exception as exc:
        log.warning("Playwright fetch failed (%s); trying static fetch", exc)
        try:
            return fetch_static(safe_url, allow_private=allow_private)
        except Exception as exc2:
            return _result(error="fetch failed: %s" % exc2, engine="httpx")


@contextmanager
def open_session(headless=True):
    """Yield a single live Playwright page for stateful, multi-step navigation
    (needed by portals whose listing links carry a per-session token, e.g. NIC
    eProcurement). Raises RuntimeError if Playwright is unavailable.
    """
    if not _PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright is not available for a browser session")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        try:
            context = browser.new_context(user_agent=config.USER_AGENT)
            page = context.new_page()
            yield page
        finally:
            browser.close()
