"""TEST PORTAL implementation.

Fetches a URL once, inspects the structure, and returns a detailed readiness
report. It never bypasses CAPTCHA, login or anti-bot controls - it only reports
their presence.
"""
from __future__ import annotations

from urllib.parse import urlparse

import config
from scraper import browser, discovery
from scraper.nic_adapter import is_nic_portal
from utils import security
from utils.dates import now_tz
from utils.logging_setup import get_logger

log = get_logger("scanner")


def _check(name, ok, detail="", kind="bool"):
    if kind == "bool":
        status = "PASS" if ok else "NOT DETECTED"
    else:
        status = ok
    return {"name": name, "status": status, "detail": detail}


def test_portal(url, browser_mode="headless", allow_private=None, fetch_fn=None):
    report = {
        "url": url, "final_url": "", "accessible": False, "https": False,
        "status_code": 0, "checks": [], "captcha": False, "login": False,
        "readiness": "SITE UNAVAILABLE", "sample": {}, "error": "",
        "screenshot": "",
    }

    try:
        security.validate_url(url, allow_private=allow_private)
    except security.SecurityError as exc:
        report["error"] = str(exc)
        report["readiness"] = "BLOCKED"
        report["checks"].append(_check("Website reachable", False, str(exc)))
        return report

    host = security.sanitize_path_component(urlparse(url).hostname or "portal")
    stamp = now_tz().strftime("%Y%m%d_%H%M%S")
    shot_path = config.DIAGNOSTICS_DIR / ("test_%s_%s.png" % (host, stamp))
    config.ensure_directories()

    fetch = (fetch_fn or browser.fetch_page)(
        url, headless=(browser_mode != "visible"),
        screenshot_path=str(shot_path), allow_private=allow_private,
    )

    report["status_code"] = fetch.get("status", 0)
    report["final_url"] = fetch.get("final_url", "")
    report["screenshot"] = fetch.get("screenshot", "")
    report["accessible"] = bool(fetch.get("ok"))

    if not fetch.get("ok"):
        report["error"] = fetch.get("error", "Not accessible")
        if fetch.get("status") in (401, 403):
            report["readiness"] = "BLOCKED"
        report["checks"].append(_check("Website reachable", False, report["error"]))
        return report

    html = fetch.get("html") or ""
    final_url = fetch.get("final_url") or url
    report["https"] = final_url.lower().startswith("https://")

    info = discovery.analyze(html, base_url=final_url)
    report["captcha"] = info["captcha_detected"]
    report["login"] = info["login_required"]
    report["info"] = info

    # NIC eProcurement (GePNIC) portals: the landing page has no real tender
    # table - the tenders (with dates, ID, organisation) are on the "Tenders by
    # Organisation" pages. Sample one of those so the checks reflect what a scan
    # actually reads, instead of the bare home-page widget.
    if is_nic_portal(url, html) or is_nic_portal(final_url, html):
        report["is_nic"] = True
        _build_nic_checks(report, browser_mode, allow_private, fetch_fn)
        report["readiness"] = "SUPPORTED (NIC eProcurement)"
        return report

    _build_checks(report, info)
    report["readiness"] = _readiness(info)
    return report


def _build_nic_checks(report, browser_mode, allow_private, fetch_fn):
    from scraper.nic_adapter import sample_org_tenders
    checks = [
        _check("Website reachable", True, "HTTP %s" % report["status_code"]),
        _check("HTTPS", report["https"], report["final_url"]),
        _check("NIC eProcurement portal", "DETECTED",
               "Scans via Tenders by Organisation (no CAPTCHA)", kind="raw"),
    ]
    sample, err = [], "not sampled"
    if fetch_fn is None:  # only launch a browser sample in real use, not in tests
        sample, err = sample_org_tenders(
            report["final_url"] or report["url"],
            headless=(browser_mode != "visible"), allow_private=allow_private)
    if sample:
        s = sample[0]
        checks.append(_check("Tender listing (organisation page)", True,
                             "%d tender(s) sampled" % len(sample)))
        checks.append(_check("Tender ID", bool(s.get("tender_id"))))
        checks.append(_check("Tender reference", bool(s.get("tender_reference"))))
        checks.append(_check("Published date", bool(s.get("published_date"))))
        checks.append(_check("Closing date", bool(s.get("bid_submission_end"))))
        checks.append(_check("Opening date", bool(s.get("opening_date"))))
        checks.append(_check("Organisation", bool(s.get("organisation"))))
        checks.append(_check("Document links", any(t.get("document_urls") for t in sample)))
        report["info"]["listing_detected"] = True
        report["info"]["listing_count"] = len(sample)
    else:
        checks.append(_check("Tender fields", "READ DURING SCAN",
                             "Dates, ID and organisation are read from the "
                             "Tenders-by-Organisation pages when you scan (%s)" % err,
                             kind="raw"))
    report["checks"] = checks


def _build_checks(report, info):
    checks = report["checks"]
    checks.append(_check("Website reachable", True, "HTTP %s" % report["status_code"]))
    checks.append(_check("HTTPS", report["https"], report["final_url"]))
    checks.append(_check("Tender listing detected", info["listing_detected"],
                         "%d record(s), method=%s" % (info["listing_count"], info["method"])))
    checks.append(_check("Pagination detected", info["pagination_detected"]))
    checks.append(_check("Search / filter controls", info["search_controls"]))
    checks.append(_check("Date fields", info["date_fields"]))
    checks.append(_check("Tender detail pages", info["detail_links"]))
    checks.append(_check("Tender ID", info["tender_id_detected"]))
    checks.append(_check("Tender reference", info["tender_reference_detected"]))
    checks.append(_check("Published date", info["published_date_detected"]))
    checks.append(_check("Closing date", info["closing_date_detected"]))
    checks.append(_check("Tender value", info["value_detected"]))
    checks.append(_check("Organisation", info["organisation_detected"]))
    checks.append(_check("Document links", info["document_links"]))
    checks.append(_check("JavaScript required", info["javascript_required"],
                         "Rendered with a real browser" if info["javascript_required"] else ""))
    checks.append(_check("CAPTCHA",
                         "DETECTED" if info["captcha_detected"] else "NOT DETECTED",
                         kind="raw"))
    checks.append(_check("Login required",
                         "REQUIRED" if info["login_required"] else "NOT REQUIRED",
                         kind="raw"))


def _readiness(info):
    if info["captcha_detected"]:
        return "CAPTCHA REQUIRED"
    if info["login_required"]:
        return "LOGIN REQUIRED"
    if not info["listing_detected"]:
        return "STRUCTURE NOT DETECTED"
    core = [
        info["tender_id_detected"] or info["tender_reference_detected"],
        info["closing_date_detected"] or info["published_date_detected"],
        info["organisation_detected"] or info["value_detected"],
    ]
    if info["listing_count"] >= 1 and all(core):
        return "GOOD"
    return "PARTIALLY SUPPORTED"
