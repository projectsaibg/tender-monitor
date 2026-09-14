"""Published-date and first-seen date filters, and today-bounds helper."""
from services import tender_service as ts
from database.models import new_tender_dict


def _mk(portal, tid, published, first_seen):
    t = new_tender_dict(portal["id"])
    t.update({"tender_id": tid, "tender_title": "T " + tid, "portal_name": portal["name"],
              "published_date": published, "first_seen_at": first_seen})
    t["unique_key"] = ts.compute_unique_key(t)
    return ts.insert_tender(t, "new")


def test_published_date_filter(db, sample_portal):
    _mk(sample_portal, "A", "2026-09-10", "2026-09-10T00:00:00+00:00")
    _mk(sample_portal, "B", "2026-09-14T10:30:00", "2026-09-14T05:00:00+00:00")
    _mk(sample_portal, "C", "2026-09-20", "2026-09-20T00:00:00+00:00")

    only14 = ts.search_tenders({"published_from": "2026-09-14", "published_to": "2026-09-14"})
    assert {t["tender_id"] for t in only14} == {"B"}

    span = ts.search_tenders({"published_from": "2026-09-10", "published_to": "2026-09-14"})
    assert {t["tender_id"] for t in span} == {"A", "B"}


def test_first_seen_filter(db, sample_portal):
    _mk(sample_portal, "A", "2026-09-10", "2026-09-10T00:00:00+00:00")
    _mk(sample_portal, "B", "2026-09-14", "2026-09-14T05:00:00+00:00")
    res = ts.search_tenders({"first_seen_from": "2026-09-14T00:00:00+00:00",
                             "first_seen_to": "2026-09-15T00:00:00+00:00"})
    assert {t["tender_id"] for t in res} == {"B"}


def test_local_today_bounds(db):
    b = ts.local_today_bounds()
    assert set(b) == {"date", "first_seen_from", "first_seen_to"}
    assert b["first_seen_from"] < b["first_seen_to"]
    assert len(b["date"]) == 10  # YYYY-MM-DD
