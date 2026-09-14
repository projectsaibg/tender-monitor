"""Database creation, insertion, duplicate detection and fingerprinting."""
import sqlite3
import pytest

from services import tender_service as ts
from database.models import new_tender_dict


def test_schema_created(db):
    names = {r["name"] for r in db.query_all(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for table in ("portals", "tenders", "tender_versions", "documents",
                  "scans", "scan_errors", "settings", "notifications"):
        assert table in names


def test_portal_crud(db):
    pid = ts.create_portal({"name": "P", "url": "https://x.gov.in",
                            "keywords": "water, pipeline"})
    portal = ts.get_portal(pid)
    assert portal["name"] == "P"
    assert portal["keywords"] == ["water", "pipeline"]
    ts.update_portal(pid, {"name": "P2"})
    assert ts.get_portal(pid)["name"] == "P2"
    ts.delete_portal(pid)
    assert ts.get_portal(pid) is None


def test_insert_and_lookup_tender(db, sample_portal):
    t = new_tender_dict(sample_portal["id"])
    t.update({"tender_id": "T-1", "tender_title": "Water work",
              "portal_name": sample_portal["name"]})
    t["unique_key"] = ts.compute_unique_key(t)
    tid = ts.insert_tender(t, "new")
    fetched = ts.get_tender_by_key(sample_portal["id"], t["unique_key"])
    assert fetched is not None
    assert fetched["id"] == tid
    assert fetched["tender_title"] == "Water work"


def test_duplicate_unique_key_rejected(db, sample_portal):
    t = new_tender_dict(sample_portal["id"])
    t.update({"tender_id": "T-9", "tender_title": "Dup"})
    t["unique_key"] = ts.compute_unique_key(t)
    ts.insert_tender(t, "new")
    with pytest.raises(sqlite3.IntegrityError):
        ts.insert_tender(t, "new")


def test_unique_key_precedence():
    assert ts.compute_unique_key({"tender_id": "A", "tender_reference": "B"}) == "id:A"
    assert ts.compute_unique_key({"tender_reference": "B"}) == "ref:B"
    key = ts.compute_unique_key({"tender_title": "T", "organisation": "O"})
    assert key.startswith("fp:")


def test_fingerprint_deterministic_and_distinct():
    a = {"tender_title": "Water", "organisation": "PHED", "published_date": "2026-01-01"}
    b = {"tender_title": "Water", "organisation": "PHED", "published_date": "2026-01-01"}
    c = {"tender_title": "Road", "organisation": "PWD", "published_date": "2026-01-02"}
    assert ts.fingerprint(a) == ts.fingerprint(b)
    assert ts.fingerprint(a) != ts.fingerprint(c)


def test_clone_portal_copies_all_settings(db):
    pid = ts.create_portal({"name": "Original", "url": "https://a.gov.in/nicgep/app",
        "enabled": "1", "schedule_type": "daily", "run_time": "08:00",
        "keywords": "water, pipeline", "negative_keywords": "vehicle",
        "location": "Kota", "max_pages": 7, "request_delay": 1.5,
        "config_json": {"nic_max_orgs": 30, "only_matching": True}})
    new_id = ts.clone_portal(pid)
    assert new_id and new_id != pid
    clone = ts.get_portal(new_id)
    src = ts.get_portal(pid)
    assert clone["name"] == "Original (copy)"
    assert clone["url"] == src["url"]
    assert clone["keywords"] == ["water", "pipeline"]
    assert clone["negative_keywords"] == ["vehicle"]
    assert clone["schedule_type"] == "daily" and clone["run_time"] == "08:00"
    assert clone["location"] == "Kota" and clone["max_pages"] == 7
    assert clone["config"]["nic_max_orgs"] == 30
    assert clone["config"]["only_matching"] is True
    assert src["name"] == "Original"   # original unchanged


def test_clone_missing_portal_returns_none(db):
    assert ts.clone_portal(999999) is None
