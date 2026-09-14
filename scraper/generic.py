"""Generic portal adapter - the default engine.

Opens the listing URL, extracts candidate tenders, follows pagination up to the
configured page limit, and (optionally) follows detail links to enrich records.
Reports CAPTCHA / login / blocked conditions instead of trying to bypass them.
"""
from __future__ import annotations

import time

import config
from scraper import parser, discovery
from scraper.base import BasePortalAdapter


class GenericPortalAdapter(BasePortalAdapter):
    name = "generic"

    def collect(self):
        portal = self.portal
        cfg = portal.get("config", {}) if isinstance(portal.get("config"), dict) else {}
        max_pages = max(1, min(int(portal.get("max_pages") or config.DEFAULT_MAX_PAGES),
                               config.HARD_MAX_PAGES))
        delay = float(portal.get("request_delay") or config.DEFAULT_REQUEST_DELAY)
        headless = (portal.get("browser_mode") or "headless") != "visible"

        tenders = []
        pages = 0
        method = "none"
        seen = set()
        url = portal["url"]
        diagnostics = {}

        for _ in range(max_pages):
            if not url or url in seen:
                break
            seen.add(url)
            fetch = self.fetch(url, headless=headless)
            if not fetch.get("ok"):
                if pages == 0:
                    return self._fail("site_unavailable",
                                      fetch.get("error") or "Page not accessible",
                                      fetch)
                break

            html = fetch.get("html") or ""
            result = parser.extract(html, base_url=fetch.get("final_url") or url)

            # Only treat CAPTCHA / login as blockers when the first page yields
            # no tenders. A portal template can include a search CAPTCHA widget
            # yet still list tenders below it - that must not block automation.
            if pages == 0 and not result["tenders"]:
                soup = __import__("bs4").BeautifulSoup(html, "lxml")
                if discovery.detect_captcha(html):
                    return self._fail("captcha_required",
                                      "CAPTCHA blocks the listing - automation not attempted", fetch)
                if discovery.detect_login_required(soup):
                    return self._fail("login_required",
                                      "Login required - automation not attempted", fetch)

            tenders.extend(result["tenders"])
            method = result["method"] if result["tenders"] else method
            pages += 1

            if len(tenders) >= config.MAX_TENDERS_PER_SCAN:
                break
            next_url = result["next_page_url"]
            if not next_url:
                break
            url = next_url
            if delay > 0:
                time.sleep(delay)

        if cfg.get("follow_detail"):
            self._enrich_details(tenders, cfg, headless)

        if not tenders:
            return self._fail("structure_not_detected",
                              "No tender listings could be detected", {})

        return {
            "tenders": tenders, "pages_processed": pages, "method": method,
            "status": "ok", "error": "", "diagnostics": diagnostics,
        }

    def _enrich_details(self, tenders, cfg, headless):
        limit = int(cfg.get("detail_limit", 20))
        enriched = 0
        for t in tenders:
            if enriched >= limit:
                break
            detail_url = t.get("tender_detail_url")
            if not detail_url:
                continue
            need = not (t.get("bid_submission_end") and t.get("published_date"))
            if not need:
                continue
            try:
                fetch = self.fetch(detail_url, headless=headless)
            except Exception:
                continue
            if not fetch.get("ok"):
                continue
            result = parser.extract(fetch.get("html") or "", base_url=detail_url)
            if result["tenders"]:
                best = result["tenders"][0]
                for field, value in best.items():
                    if value and not t.get(field):
                        t[field] = value
                enriched += 1

    def _fail(self, status, error, fetch):
        return {
            "tenders": [], "pages_processed": 0, "method": "none",
            "status": status, "error": error,
            "diagnostics": {
                "title": fetch.get("title", ""),
                "final_url": fetch.get("final_url", ""),
                "screenshot": fetch.get("screenshot", ""),
            },
        }
