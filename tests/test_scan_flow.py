"""End-to-end scan flow: baseline, no-duplicates, NEW and UPDATED detection.

Uses an injected fetch function that returns mock HTML, so no browser or network
is involved. This mirrors the acceptance test (spec section 39).
"""
from services import scan_service
from services import tender_service as ts
from tests import mock_data


def _fetch(html):
    def fetch_fn(url, **kwargs):
        return {"ok": True, "status": 200, "final_url": url, "title": "Mock",
                "html": html, "screenshot": "", "error": "", "engine": "mock"}
    return fetch_fn


def test_full_lifecycle(db, sample_portal):
    pid = sample_portal["id"]

    # ---- Scan 1: baseline ------------------------------------------------ #
    r1 = scan_service.scan_portal(pid, trigger="test", fetch_fn=_fetch(mock_data.LISTING_V1))
    assert r1["status"] == "baseline"
    assert r1["found"] == 3
    assert r1["new"] == 0                     # baseline is not counted as NEW
    assert ts.count_tenders_for_portal(pid) == 3
    assert all(t["status"] == "existing" for t in ts.search_tenders({"portal_id": pid}))

    # ---- Scan 2: identical -> no new, no updated, no duplicates ---------- #
    r2 = scan_service.scan_portal(pid, trigger="test", fetch_fn=_fetch(mock_data.LISTING_V1))
    assert r2["status"] == "success"
    assert r2["new"] == 0
    assert r2["updated"] == 0
    assert ts.count_tenders_for_portal(pid) == 3

    # ---- Scan 3: one changed (T-002), one new (T-004) ------------------- #
    r3 = scan_service.scan_portal(pid, trigger="test", fetch_fn=_fetch(mock_data.LISTING_V2))
    assert r3["new"] == 1
    assert r3["updated"] == 1
    assert ts.count_tenders_for_portal(pid) == 4

    new_ones = ts.search_tenders({"portal_id": pid, "status": "new"})
    assert len(new_ones) == 1
    assert new_ones[0]["tender_id"] == "T-004"

    updated_ones = ts.search_tenders({"portal_id": pid, "status": "updated"})
    assert len(updated_ones) == 1
    assert updated_ones[0]["tender_id"] == "T-002"

    # Version history recorded for the closing-date extension.
    versions = ts.list_versions(updated_ones[0]["id"])
    change_types = {v["change_type"] for v in versions}
    assert "CLOSING DATE EXTENDED" in change_types


def test_keyword_matching_and_negative(db, sample_portal):
    pid = sample_portal["id"]
    scan_service.scan_portal(pid, trigger="test", fetch_fn=_fetch(mock_data.LISTING_V1))
    tenders = {t["tender_id"]: t for t in ts.search_tenders({"portal_id": pid})}
    assert tenders["T-001"]["matched"] == 1      # water pipeline -> matches
    assert tenders["T-003"]["matched"] == 0      # vehicle -> negative keyword


def test_treat_first_scan_as_new(db):
    pid = ts.create_portal({"name": "P", "url": "https://x.gov.in", "enabled": "1",
                            "schedule_type": "manual", "treat_first_scan_as_new": "1",
                            "download_documents": "0", "request_delay": 0})
    r = scan_service.scan_portal(pid, trigger="test", fetch_fn=_fetch(mock_data.LISTING_V1))
    assert r["status"] == "success"
    assert r["new"] == 3


def test_captcha_reported(db):
    pid = ts.create_portal({"name": "C", "url": "https://x.gov.in", "enabled": "1",
                            "schedule_type": "manual", "request_delay": 0})
    r = scan_service.scan_portal(pid, trigger="test", fetch_fn=_fetch(mock_data.CAPTCHA_PAGE))
    assert r["status"] == "captcha_required"


def test_structure_change_guard(db):
    pid = ts.create_portal({"name": "S", "url": "https://x.gov.in", "enabled": "1",
                            "schedule_type": "manual", "download_documents": "0",
                            "request_delay": 0, "treat_first_scan_as_new": "1"})
    # Seed a big baseline so a sudden drop triggers the partial guard.
    big_rows = "\n".join(
        "<tr><td>B-%03d</td><td>Water work %d</td><td>2026-12-31</td></tr>" % (i, i)
        for i in range(30))
    big_html = ("<table><thead><tr><th>Tender ID</th><th>Title</th>"
                "<th>Closing Date</th></tr></thead><tbody>%s</tbody></table>" % big_rows)
    r1 = scan_service.scan_portal(pid, trigger="test", fetch_fn=_fetch(big_html))
    assert r1["found"] == 30
    # Now a page with only 1 tender -> should be flagged partial, data preserved.
    small = ("<table><thead><tr><th>Tender ID</th><th>Title</th><th>Closing Date</th>"
             "</tr></thead><tbody><tr><td>B-000</td><td>Water work 0</td>"
             "<td>2026-12-31</td></tr></tbody></table>")
    r2 = scan_service.scan_portal(pid, trigger="test", fetch_fn=_fetch(small))
    assert r2["status"] == "partial"
    assert ts.count_tenders_for_portal(pid) == 30   # previous data preserved


def test_only_matching_stores_relevant_only(db):
    pid = ts.create_portal({"name": "P", "url": "https://x.gov.in", "enabled": "1",
                            "schedule_type": "manual", "download_documents": "0",
                            "request_delay": 0, "treat_first_scan_as_new": "1",
                            "keywords": "water, pipeline, STP", "negative_keywords": "vehicle",
                            "config_json": {"only_matching": True}})
    scan_service.scan_portal(pid, trigger="test", fetch_fn=_fetch(mock_data.LISTING_V1))
    ids = {t["tender_id"] for t in ts.search_tenders({"portal_id": pid})}
    assert "T-001" in ids and "T-002" in ids   # water / STP match
    assert "T-003" not in ids                   # vehicle -> negative keyword, excluded
    assert ts.count_tenders_for_portal(pid) == 2


def test_config_roundtrip_nic_max_orgs(db):
    pid = ts.create_portal({"name": "P", "url": "https://x.gov.in/nicgep/app",
                            "config_json": {"nic_max_orgs": 12, "only_matching": True}})
    p = ts.get_portal(pid)
    assert p["config"]["nic_max_orgs"] == 12
    assert p["config"]["only_matching"] is True


def test_updated_tender_resurfaces_from_archive(db):
    pid = ts.create_portal({"name": "P", "url": "https://x.gov.in", "enabled": "1",
                            "schedule_type": "manual", "download_documents": "0",
                            "request_delay": 0, "treat_first_scan_as_new": "1"})
    scan_service.scan_portal(pid, trigger="test", fetch_fn=_fetch(mock_data.LISTING_V1))
    ts.archive_matching({})
    assert len(ts.search_tenders({"archived": 0})) == 0
    scan_service.scan_portal(pid, trigger="test", fetch_fn=_fetch(mock_data.LISTING_V2))
    active = {t["tender_id"] for t in ts.search_tenders({"archived": 0})}
    assert "T-002" in active   # changed -> resurfaced from archive
    assert "T-004" in active   # brand new -> active
    assert "T-001" not in active   # unchanged -> stays archived
