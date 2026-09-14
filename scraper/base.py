"""Portal adapter architecture.

BasePortalAdapter defines the contract every adapter honours. The default is
GenericPortalAdapter (see generic.py). Custom adapters for specific portals can
be added later without touching the database, scheduler, reporting or dashboard
code - register them in scraper.registry.

An adapter is constructed with a portal config dict and an optional ``fetch_fn``
(defaulting to the Playwright fetcher). Injecting ``fetch_fn`` lets the test
suite drive an adapter with mock HTML and no browser.
"""
from __future__ import annotations

from utils.logging_setup import get_logger


class BasePortalAdapter:
    name = "base"

    def __init__(self, portal, fetch_fn=None, allow_private=None, logger=None):
        self.portal = portal
        self._fetch_fn = fetch_fn
        self.allow_private = allow_private
        self.log = logger or get_logger("scanner")

    def fetch(self, url, headless=True, screenshot_path=None):
        fetch_fn = self._fetch_fn
        if fetch_fn is None:
            from scraper import browser  # lazy import to avoid hard playwright dep
            fetch_fn = browser.fetch_page
        return fetch_fn(
            url, headless=headless, screenshot_path=screenshot_path,
            allow_private=self.allow_private,
        )

    def collect(self):
        """Return a CollectResult dict:

        {
            "tenders": [normalized tender dicts],
            "pages_processed": int,
            "method": str,             # table / cards / none
            "status": str,             # ok / captcha_required / login_required /
                                       # blocked / site_unavailable / structure_not_detected
            "error": str,
            "diagnostics": dict,
        }
        """
        raise NotImplementedError
