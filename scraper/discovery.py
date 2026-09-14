"""Portal structure discovery.

Heuristics used by the TEST PORTAL feature and the generic adapter to describe
what a page looks like: tables, pagination, search controls, detail links, and
red flags such as CAPTCHA or login requirements. Detection only - nothing here
attempts to bypass any control.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from scraper import parser

_CAPTCHA_MARKERS = [
    "g-recaptcha", "recaptcha", "hcaptcha", "h-captcha", "cf-turnstile",
    "captcha", "are you human", "verify you are human", "data-sitekey",
]
_LOGIN_MARKERS = ["sign in", "signin", "log in", "login", "username", "password"]


def _text_of(soup):
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


def detect_captcha(html):
    low = (html or "").lower()
    return any(marker in low for marker in _CAPTCHA_MARKERS)


def detect_login_required(soup):
    if soup.find("input", attrs={"type": "password"}):
        return True
    for form in soup.find_all("form"):
        blob = (" ".join(form.get("action", "").split()) + " " + form.get_text(" ")).lower()
        if any(m in blob for m in ("login", "signin", "sign in")):
            if form.find("input", attrs={"type": "password"}):
                return True
    return False


def detect_search_controls(soup):
    for inp in soup.find_all("input"):
        itype = (inp.get("type") or "text").lower()
        name = (inp.get("name") or "") + (inp.get("id") or "") + (inp.get("placeholder") or "")
        if itype in ("search",) or "search" in name.lower() or "keyword" in name.lower():
            return True
    return bool(soup.find("input", attrs={"type": "search"}))


def detect_date_fields(soup):
    if soup.find("input", attrs={"type": "date"}):
        return True
    for inp in soup.find_all("input"):
        name = ((inp.get("name") or "") + (inp.get("id") or "") + (inp.get("placeholder") or "")).lower()
        if "date" in name:
            return True
    return False


def analyze(html, base_url=""):
    """Return a structured description of the page for reporting."""
    soup = BeautifulSoup(html or "", "lxml")
    parse_result = parser.extract(html or "", base_url=base_url)
    text = _text_of(BeautifulSoup(html or "", "lxml"))
    tenders = parse_result["tenders"]

    scripts = soup.find_all("script")
    js_required = len(text) < 400 and len(scripts) >= 3

    sample = tenders[0] if tenders else {}
    doc_links = any(t.get("document_urls") for t in tenders)
    detail_links = any(t.get("tender_detail_url") for t in tenders)

    return {
        "accessible": True,
        "listing_detected": len(tenders) > 0,
        "listing_count": len(tenders),
        "method": parse_result["method"],
        "pagination_detected": parse_result["next_page_url"] is not None,
        "search_controls": detect_search_controls(soup),
        "date_fields": detect_date_fields(soup),
        "detail_links": detail_links,
        "document_links": doc_links,
        "tender_id_detected": bool(sample.get("tender_id")),
        "tender_reference_detected": bool(sample.get("tender_reference")),
        "published_date_detected": bool(sample.get("published_date")),
        "closing_date_detected": bool(sample.get("bid_submission_end")),
        "value_detected": bool(sample.get("estimated_value_text")),
        "organisation_detected": bool(sample.get("organisation")),
        "captcha_detected": detect_captcha(html),
        "login_required": detect_login_required(soup),
        "javascript_required": js_required,
        "forms_count": len(soup.find_all("form")),
        "tables_count": parse_result["tables_found"],
    }
