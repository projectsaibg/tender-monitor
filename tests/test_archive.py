"""Archive / restore behaviour and active-only views."""
from services import tender_service as ts
from database.models import new_tender_dict


def _mk(portal, tid, first_seen, status="new"):
    t = new_tender_dict(portal["id"])
    t.update({"tender_id": tid, "tender_title": "T " + tid,
              "portal_name": portal["name"], "first_seen_at": first_seen})
    t["unique_key"] = ts.compute_unique_key(t)
    return ts.insert_tender(t, status)


def test_all_tenders_excludes_archived(db, sample_portal):
    _mk(sample_portal, "A", "2026-09-14T00:00:00+00:00")
    b = _mk(sample_portal, "B", "2026-09-14T00:00:00+00:00")
    ts.set_tender_archived(b, True)
    assert {t["tender_id"] for t in ts.all_tenders()} == {"A"}
    assert {t["tender_id"] for t in ts.all_tenders(include_archived=True)} == {"A", "B"}


def test_search_archived_filter(db, sample_portal):
    _mk(sample_portal, "A", "2026-09-14T00:00:00+00:00")
    b = _mk(sample_portal, "B", "2026-09-14T00:00:00+00:00")
    ts.set_tender_archived(b, True)
    assert {t["tender_id"] for t in ts.search_tenders({"archived": 0})} == {"A"}
    assert {t["tender_id"] for t in ts.search_tenders({"archived": 1})} == {"B"}


def test_archive_older_than(db, sample_portal):
    _mk(sample_portal, "OLD", "2026-09-10T00:00:00+00:00")
    _mk(sample_portal, "TODAY", "2026-09-14T12:00:00+00:00")
    n = ts.archive_older_than("2026-09-14T00:00:00+00:00")
    assert n == 1
    assert {t["tender_id"] for t in ts.search_tenders({"archived": 0})} == {"TODAY"}
    assert {t["tender_id"] for t in ts.search_tenders({"archived": 1})} == {"OLD"}


def test_archive_and_restore_all(db, sample_portal):
    _mk(sample_portal, "A", "2026-09-14T00:00:00+00:00")
    _mk(sample_portal, "B", "2026-09-14T00:00:00+00:00")
    assert ts.archive_matching({}) == 2
    assert len(ts.search_tenders({"archived": 0})) == 0
    assert ts.restore_matching({}) == 2
    assert len(ts.search_tenders({"archived": 0})) == 2


def test_dashboard_excludes_archived(db, sample_portal):
    _mk(sample_portal, "A", "2026-09-14T00:00:00+00:00", status="new")
    b = _mk(sample_portal, "B", "2026-09-14T00:00:00+00:00", status="new")
    ts.set_tender_archived(b, True)
    stats = ts.dashboard_stats()
    assert stats["new_tenders"] == 1
    assert stats["archived_tenders"] == 1


def test_archive_existing_keeps_new_and_updated(db, sample_portal):
    _mk(sample_portal, "N", "2026-09-14T00:00:00+00:00", status="new")
    _mk(sample_portal, "U", "2026-09-14T00:00:00+00:00", status="updated")
    _mk(sample_portal, "E1", "2026-09-14T00:00:00+00:00", status="existing")
    _mk(sample_portal, "E2", "2026-09-14T00:00:00+00:00", status="existing")
    n = ts.archive_existing()
    assert n == 2
    assert {t["tender_id"] for t in ts.search_tenders({"archived": 0})} == {"N", "U"}
