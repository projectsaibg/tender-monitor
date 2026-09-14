"""Adapter for NIC eProcurement (GePNIC) portals.

Many Indian government portals run the NIC eProcurement System, served under
``/nicgep/app``. Their landing page has no tender table - listings live behind
menu pages. The free-text "Active Tenders" search is CAPTCHA-protected (which we
never bypass), but "Tenders by Organisation" drills into per-organisation tender
tables without a CAPTCHA. This adapter walks that path in a single browser
session (the drill-down links carry a per-session token) and parses each
organisation's tender table with the generic parser.

Most organisations list all their tenders on one page; where a deployment
paginates, a strict "Next" control (never a tender-detail link) is followed up
to a safety cap.
"""
from __future__ import annotations

from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

import config
from scraper import parser, browser
from scraper.base import BasePortalAdapter
from utils import security

# Exact visible-text of a pagination "next" control.
_NEXT_TEXTS = {"next", "next >", "next >>", "next \u00bb", "next page", "\u00bb", ">", ">>"}


def is_nic_portal(url, html=""):
    """Heuristic: is this a NIC eProcurement (GePNIC) portal?"""
    u = (url or "").lower()
    if "/nicgep/" in u or "nicgep/app" in u:
        return True
    low = (html or "").lower()
    return "nicgep" in low or ("national informatics centre" in low and "eprocurement" in low)


def next_listing_page(html, current_url):
    """Return an absolute URL for a strict pagination 'Next' link, else None.

    Conservative by design: it only matches an anchor whose *entire* visible text
    is a next-page control, and never a tender-detail link (FrontEndViewTender),
    so it can never accidentally follow a tender title.
    """
    soup = BeautifulSoup(html or "", "lxml")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href or href.startswith(("#", "javascript:")):
            continue
        if "frontendviewtender" in href.lower():
            continue
        text = " ".join(a.get_text().split()).lower()
        if text in _NEXT_TEXTS:
            return urljoin(current_url, href)
    return None


class NicEprocurementAdapter(BasePortalAdapter):
    name = "nic"

    def _org_page(self, url):
        parsed = urlparse(url)
        root = "%s://%s" % (parsed.scheme, parsed.netloc)
        return root, root + "/nicgep/app?page=FrontEndTendersByOrganisation&service=page"

    def _collect_org(self, page, org_url, seen, tenders, timeout, delay_ms, max_pages):
        """Walk one organisation, following strict Next pagination if present."""
        pages_done = 0
        visited = set()
        page_url = org_url
        for _ in range(max(1, max_pages)):
            if page_url in visited:
                break
            visited.add(page_url)
            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=timeout)
                page.wait_for_timeout(500)
                html = page.content()
            except Exception:
                break
            result = parser.extract(html, base_url=page_url)
            pages_done += 1
            added = 0
            for t in result["tenders"]:
                key = t.get("tender_id") or t.get("tender_reference") or t.get("tender_title")
                if key and key not in seen:
                    seen.add(key)
                    t["source_url"] = org_url
                    tenders.append(t)
                    added += 1
            if len(tenders) >= config.MAX_TENDERS_PER_SCAN:
                break
            # Stop if a follow-on page contributed nothing new (avoids loops).
            if pages_done > 1 and added == 0:
                break
            nxt = next_listing_page(html, page_url)
            if not nxt or nxt in visited:
                break
            page_url = nxt
            if delay_ms:
                page.wait_for_timeout(delay_ms)
        return pages_done

    def collect(self):
        portal = self.portal
        security.validate_url(portal["url"], allow_private=self.allow_private)
        root, org_page = self._org_page(portal["url"])
        headless = (portal.get("browser_mode") or "headless") != "visible"
        delay_ms = int(float(portal.get("request_delay") or 0) * 1000)
        cfg = portal.get("config") if isinstance(portal.get("config"), dict) else {}
        max_orgs = int(cfg.get("nic_max_orgs", config.NIC_MAX_ORGS))
        max_pages_per_org = int(cfg.get("nic_max_pages_per_org", config.NIC_MAX_PAGES_PER_ORG))
        timeout = config.BROWSER_TIMEOUT_MS

        tenders = []
        seen = set()
        pages = 0
        try:
            with browser.open_session(headless=headless) as page:
                page.goto(org_page, wait_until="domcontentloaded", timeout=timeout)
                page.wait_for_timeout(800)
                hrefs = page.eval_on_selector_all(
                    "a[href*='DirectLink']",
                    "els => els.map(e => e.getAttribute('href'))")
                org_urls = []
                for h in hrefs:
                    if not h:
                        continue
                    absolute = urljoin(root, h)
                    if absolute not in org_urls:
                        org_urls.append(absolute)

                if not org_urls:
                    return self._fail(
                        "structure_not_detected",
                        "No 'Tenders by Organisation' links found on the NIC portal",
                        {"final_url": page.url, "title": page.title()})

                for org_url in org_urls[:max_orgs]:
                    pages += self._collect_org(
                        page, org_url, seen, tenders, timeout, delay_ms, max_pages_per_org)
                    if len(tenders) >= config.MAX_TENDERS_PER_SCAN:
                        break
                    if delay_ms:
                        page.wait_for_timeout(delay_ms)
        except RuntimeError as exc:
            return self._fail("site_unavailable", str(exc), {})
        except Exception as exc:
            return self._fail("site_unavailable", "NIC navigation failed: %s" % exc, {})

        if not tenders:
            return self._fail(
                "structure_not_detected",
                "Reached the NIC organisation pages but no tenders were extracted",
                {})

        return {"tenders": tenders, "pages_processed": pages,
                "method": "nic_by_organisation", "status": "ok", "error": "",
                "diagnostics": {}}


def sample_org_tenders(url, headless=True, allow_private=None, max_orgs_probe=3):
    """Fetch a small sample of tenders via Tenders by Organisation.

    Used by TEST PORTAL so it can report the fields that a real scan actually
    reads (dates, ID, organisation), instead of the bare home-page widget.
    Returns (tenders, error_message).
    """
    parsed = urlparse(url)
    root = "%s://%s" % (parsed.scheme, parsed.netloc)
    org_page = root + "/nicgep/app?page=FrontEndTendersByOrganisation&service=page"
    try:
        with browser.open_session(headless=headless) as page:
            page.goto(org_page, wait_until="domcontentloaded", timeout=config.BROWSER_TIMEOUT_MS)
            page.wait_for_timeout(700)
            hrefs = page.eval_on_selector_all(
                "a[href*='DirectLink']", "els => els.map(e => e.getAttribute('href'))")
            org_urls = []
            for h in hrefs:
                if h:
                    absolute = urljoin(root, h)
                    if absolute not in org_urls:
                        org_urls.append(absolute)
            if not org_urls:
                return [], "no organisation links found"
            for org_url in org_urls[:max_orgs_probe]:
                try:
                    page.goto(org_url, wait_until="domcontentloaded", timeout=config.BROWSER_TIMEOUT_MS)
                    page.wait_for_timeout(600)
                    result = parser.extract(page.content(), base_url=org_url)
                except Exception:
                    continue
                if result["tenders"]:
                    return result["tenders"], ""
            return [], "sampled organisations had no tenders"
    except Exception as exc:
        return [], str(exc)
