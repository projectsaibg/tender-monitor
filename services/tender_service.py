"""Core data-access service for portals, tenders, scans and settings.

All SQL is parameterised. Functions use the shared Database singleton via
get_db(); the test-suite injects an isolated Database with set_db().
"""
from __future__ import annotations

import hashlib

from database.database import get_db
from database import models
from utils.dates import utcnow_iso, normalize_date
from utils.text import parse_currency

PORTAL_WRITABLE = [
    "name", "url", "enabled", "schedule_type", "run_time", "day_of_week",
    "keywords", "negative_keywords", "keyword_mode", "location", "min_value",
    "max_value", "download_documents", "max_pages", "request_delay",
    "browser_mode", "adapter", "treat_first_scan_as_new", "config_json",
]


# --------------------------------------------------------------------------- #
# Fingerprint / identity
# --------------------------------------------------------------------------- #
def fingerprint(tender):
    def norm(v):
        return " ".join(str(v or "").split()).lower()
    parts = [
        norm(tender.get("tender_title")),
        norm(tender.get("organisation")),
        norm(normalize_date(tender.get("published_date")) or tender.get("published_date")),
        norm(tender.get("tender_detail_url") or tender.get("source_url")),
        norm(tender.get("location")),
    ]
    return hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()


def compute_unique_key(tender):
    tid = str(tender.get("tender_id") or "").strip()
    if tid:
        return "id:" + tid
    ref = str(tender.get("tender_reference") or "").strip()
    if ref:
        return "ref:" + ref
    return "fp:" + fingerprint(tender)


# --------------------------------------------------------------------------- #
# Portals
# --------------------------------------------------------------------------- #
def _portal_view(row):
    if row is None:
        return None
    row = dict(row)
    row["keywords"] = models.load_json(row.get("keywords"), [])
    row["negative_keywords"] = models.load_json(row.get("negative_keywords"), [])
    row["config"] = models.load_json(row.get("config_json"), {}) or {}
    return row


def list_portals(enabled_only=False):
    db = get_db()
    sql = "SELECT * FROM portals"
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY name COLLATE NOCASE"
    return [_portal_view(r) for r in db.query_all(sql)]


def get_portal(portal_id):
    db = get_db()
    return _portal_view(db.query_one("SELECT * FROM portals WHERE id = ?", (portal_id,)))


def _normalize_portal_payload(data):
    payload = {}
    for key in PORTAL_WRITABLE:
        if key not in data:
            continue
        value = data[key]
        if key in ("keywords", "negative_keywords"):
            if isinstance(value, list):
                value = models.dump_json([str(v).strip() for v in value if str(v).strip()])
            else:
                value = models.dump_json([v.strip() for v in str(value).split(",") if v.strip()])
        elif key == "config_json" and not isinstance(value, str):
            value = models.dump_json(value or {})
        elif key in ("enabled", "download_documents", "treat_first_scan_as_new"):
            value = 1 if str(value) in ("1", "true", "True", "on", "yes") else 0
        elif key in ("min_value", "max_value"):
            value = parse_currency(value) if value not in (None, "") else None
        elif key in ("max_pages",):
            value = int(value) if str(value).strip() else 5
        elif key in ("request_delay",):
            value = float(value) if str(value).strip() else 2.0
        elif key == "day_of_week":
            value = int(value) if value not in (None, "") and str(value).strip() != "" else None
        payload[key] = value
    return payload


def create_portal(data):
    db = get_db()
    payload = _normalize_portal_payload(data)
    now = utcnow_iso()
    payload.setdefault("keywords", "[]")
    payload.setdefault("negative_keywords", "[]")
    payload["created_at"] = now
    payload["updated_at"] = now
    cols = list(payload.keys())
    placeholders = ", ".join(["?"] * len(cols))
    sql = "INSERT INTO portals (%s) VALUES (%s)" % (", ".join(cols), placeholders)
    return db.execute(sql, tuple(payload[c] for c in cols))


def update_portal(portal_id, data):
    db = get_db()
    payload = _normalize_portal_payload(data)
    payload["updated_at"] = utcnow_iso()
    sets = ", ".join("%s = ?" % c for c in payload)
    params = tuple(payload.values()) + (portal_id,)
    db.execute("UPDATE portals SET %s WHERE id = ?" % sets, params)
    return get_portal(portal_id)


def delete_portal(portal_id):
    get_db().execute("DELETE FROM portals WHERE id = ?", (portal_id,))


def clone_portal(portal_id):
    """Create a copy of a portal with all settings preserved.

    The name gets a " (copy)" suffix; everything else (URL, schedule, keywords,
    filters and config such as nic_max_orgs / only_matching) is copied verbatim.
    The caller typically redirects to the clone's edit page so the user can
    change the name and URL. Returns the new portal id, or None if not found.
    """
    src = get_portal(portal_id)
    if src is None:
        return None
    data = {key: src.get(key) for key in PORTAL_WRITABLE if key in src}
    data["name"] = "%s (copy)" % (src.get("name") or "Portal")
    return create_portal(data)


def set_portal_enabled(portal_id, enabled):
    get_db().execute("UPDATE portals SET enabled = ?, updated_at = ? WHERE id = ?",
                     (1 if enabled else 0, utcnow_iso(), portal_id))


def update_portal_health(portal_id, health, last_status, last_scan_at=None):
    get_db().execute(
        "UPDATE portals SET health = ?, last_status = ?, last_scan_at = COALESCE(?, last_scan_at) WHERE id = ?",
        (health, last_status, last_scan_at, portal_id))


# --------------------------------------------------------------------------- #
# Tenders
# --------------------------------------------------------------------------- #
_TENDER_COLUMNS = [
    "portal_id", "portal_name", "source_url", "tender_id", "tender_reference",
    "tender_title", "organisation", "department", "tender_category",
    "product_category", "tender_type", "location", "published_date",
    "bid_submission_start", "bid_submission_end", "opening_date",
    "estimated_value", "estimated_value_text", "emd", "tender_fee",
    "work_period", "eligibility", "tender_detail_url", "document_urls",
    "extra_fields", "relevance_score", "relevance_band", "matched",
    "fingerprint", "unique_key", "status", "scraped_at", "first_seen_at",
    "last_seen_at",
]


def _tender_row_values(tender):
    row = {}
    for col in _TENDER_COLUMNS:
        value = tender.get(col)
        if col in ("document_urls", "extra_fields"):
            value = models.dump_json(value if value is not None else ([] if col == "document_urls" else {}))
        elif col == "matched" and value is None:
            value = 1
        elif col == "relevance_score" and value is None:
            value = 0
        elif col == "relevance_band" and not value:
            value = "LOW"
        row[col] = value
    return row


def get_tender(tender_id):
    row = get_db().query_one("SELECT * FROM tenders WHERE id = ?", (tender_id,))
    return _tender_view(row)


def get_tender_by_key(portal_id, unique_key):
    row = get_db().query_one(
        "SELECT * FROM tenders WHERE portal_id = ? AND unique_key = ?",
        (portal_id, unique_key))
    return _tender_view(row)


def _tender_view(row):
    if row is None:
        return None
    row = dict(row)
    row["document_urls"] = models.load_json(row.get("document_urls"), [])
    row["extra_fields"] = models.load_json(row.get("extra_fields"), {}) or {}
    return row


def insert_tender(tender, status):
    db = get_db()
    now = utcnow_iso()
    tender = dict(tender)
    tender["unique_key"] = tender.get("unique_key") or compute_unique_key(tender)
    tender["fingerprint"] = tender.get("fingerprint") or fingerprint(tender)
    tender["status"] = status
    tender["scraped_at"] = now
    tender.setdefault("first_seen_at", now)
    tender["last_seen_at"] = now
    row = _tender_row_values(tender)
    cols = list(row.keys())
    sql = "INSERT INTO tenders (%s) VALUES (%s)" % (
        ", ".join(cols), ", ".join(["?"] * len(cols)))
    return db.execute(sql, tuple(row[c] for c in cols))


def update_tender(tender_id, tender, status):
    db = get_db()
    tender = dict(tender)
    tender["unique_key"] = tender.get("unique_key") or compute_unique_key(tender)
    tender["fingerprint"] = fingerprint(tender)
    tender["status"] = status
    tender["last_seen_at"] = utcnow_iso()
    tender["scraped_at"] = utcnow_iso()
    row = _tender_row_values(tender)
    # never overwrite first_seen_at on update
    row.pop("first_seen_at", None)
    sets = ", ".join("%s = ?" % c for c in row)
    params = tuple(row.values()) + (tender_id,)
    db.execute("UPDATE tenders SET %s WHERE id = ?" % sets, params)


def touch_tender_seen(tender_id, status="existing"):
    get_db().execute(
        "UPDATE tenders SET last_seen_at = ?, status = ? WHERE id = ?",
        (utcnow_iso(), status, tender_id))


def record_versions(tender_id, changes, scan_id=None):
    if not changes:
        return
    now = utcnow_iso()
    rows = [
        (tender_id, scan_id, now, c["field"], c["old"], c["new"], c["change_type"])
        for c in changes
    ]
    get_db().executemany(
        "INSERT INTO tender_versions (tender_id, scan_id, changed_at, field, "
        "old_value, new_value, change_type) VALUES (?, ?, ?, ?, ?, ?, ?)", rows)


def list_versions(tender_id):
    return get_db().query_all(
        "SELECT * FROM tender_versions WHERE tender_id = ? ORDER BY id DESC",
        (tender_id,))


def documents_for_tender(tender_id):
    return get_db().query_all(
        "SELECT * FROM documents WHERE tender_id = ? ORDER BY document_name", (tender_id,))


def count_tenders_for_portal(portal_id):
    return get_db().scalar("SELECT COUNT(*) FROM tenders WHERE portal_id = ?", (portal_id,)) or 0


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
def get_settings():
    db = get_db()
    stored = {r["key"]: r["value"] for r in db.query_all("SELECT key, value FROM settings")}
    merged = dict(models.DEFAULT_SETTINGS)
    merged.update(stored)
    return merged


def get_setting(key, default=None):
    return get_settings().get(key, default)


def set_setting(key, value):
    get_db().execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))


def save_settings(data):
    for key in models.DEFAULT_SETTINGS:
        if key in data:
            set_setting(key, data[key])


def get_timezone_name():
    import config
    tz = get_setting("timezone", "") or ""
    return tz.strip() or config.DEFAULT_TIMEZONE


def local_today_bounds():
    """Bounds for 'today' in the configured timezone.

    Returns a dict with the local calendar date (for published-date filters) and
    the UTC ISO start/end of the local day (for first_seen filters, since
    first_seen_at is stored in UTC).
    """
    from datetime import datetime, timedelta
    from utils.dates import get_timezone
    tz = get_timezone(get_timezone_name())
    utc = get_timezone("UTC")
    start_local = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    return {
        "date": start_local.strftime("%Y-%m-%d"),
        "first_seen_from": start_local.astimezone(utc).replace(microsecond=0).isoformat(),
        "first_seen_to": end_local.astimezone(utc).replace(microsecond=0).isoformat(),
    }


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #
def add_notification(level, title, message):
    return get_db().execute(
        "INSERT INTO notifications (created_at, level, title, message) VALUES (?, ?, ?, ?)",
        (utcnow_iso(), level, title, message))


def list_notifications(limit=20):
    return get_db().query_all(
        "SELECT * FROM notifications ORDER BY id DESC LIMIT ?", (limit,))


def recent_errors(limit=10):
    return get_db().query_all(
        "SELECT * FROM scan_errors ORDER BY id DESC LIMIT ?", (limit,))


# --------------------------------------------------------------------------- #
# Scans
# --------------------------------------------------------------------------- #
def create_scan(portal_id, portal_name, trigger="manual"):
    return get_db().execute(
        "INSERT INTO scans (portal_id, portal_name, started_at, status, trigger) "
        "VALUES (?, ?, ?, 'running', ?)", (portal_id, portal_name, utcnow_iso(), trigger))


def finish_scan(scan_id, **fields):
    if not fields:
        return
    sets = ", ".join("%s = ?" % k for k in fields)
    params = tuple(fields.values()) + (scan_id,)
    get_db().execute("UPDATE scans SET %s WHERE id = ?" % sets, params)


def add_scan_error(scan_id, portal_id, portal_name, error_type, message, detail=""):
    return get_db().execute(
        "INSERT INTO scan_errors (scan_id, portal_id, portal_name, occurred_at, "
        "error_type, message, detail) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (scan_id, portal_id, portal_name, utcnow_iso(), error_type, message, detail))


def list_scans(limit=100):
    return get_db().query_all("SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,))


def get_scan(scan_id):
    return get_db().query_one("SELECT * FROM scans WHERE id = ?", (scan_id,))


def scan_errors_for(scan_id):
    return get_db().query_all(
        "SELECT * FROM scan_errors WHERE scan_id = ? ORDER BY id", (scan_id,))


def last_completed_scan(portal_id):
    return get_db().query_one(
        "SELECT * FROM scans WHERE portal_id = ? AND status IN "
        "('success', 'baseline', 'partial') ORDER BY id DESC LIMIT 1", (portal_id,))


# --------------------------------------------------------------------------- #
# Search / reporting queries
# --------------------------------------------------------------------------- #
def search_tenders(filters=None, limit=1000, order="last_seen_at DESC"):
    filters = filters or {}
    where = []
    params = []
    mapping = {
        "portal_id": "portal_id = ?",
        "tender_id": "tender_id LIKE ?",
        "organisation": "organisation LIKE ?",
        "location": "location LIKE ?",
        "status": "status = ?",
        "archived": "archived = ?",
        "relevance_band": "relevance_band = ?",
    }
    for key, clause in mapping.items():
        val = filters.get(key)
        if val not in (None, "", "all"):
            where.append(clause)
            params.append("%%%s%%" % val if "LIKE" in clause else val)

    keyword = filters.get("keyword")
    if keyword:
        where.append("(tender_title LIKE ? OR organisation LIKE ? OR tender_category "
                     "LIKE ? OR eligibility LIKE ? OR tender_reference LIKE ?)")
        params.extend(["%%%s%%" % keyword] * 5)

    if filters.get("min_value") not in (None, ""):
        where.append("estimated_value >= ?")
        params.append(parse_currency(filters["min_value"]))
    if filters.get("max_value") not in (None, ""):
        where.append("estimated_value IS NOT NULL AND estimated_value <= ?")
        params.append(parse_currency(filters["max_value"]))

    # Date filters. published_* compare the portal e-Published date (naive ISO,
    # date part only). first_seen_* compare the app's own first-seen timestamp
    # (UTC ISO) using pre-computed ISO bounds, so timezone handling stays in the
    # caller. ISO strings compare chronologically.
    if filters.get("published_from"):
        where.append("published_date != '' AND substr(published_date, 1, 10) >= ?")
        params.append(filters["published_from"])
    if filters.get("published_to"):
        where.append("published_date != '' AND substr(published_date, 1, 10) <= ?")
        params.append(filters["published_to"])
    if filters.get("first_seen_from"):
        where.append("first_seen_at >= ?")
        params.append(filters["first_seen_from"])
    if filters.get("first_seen_to"):
        where.append("first_seen_at < ?")
        params.append(filters["first_seen_to"])

    sql = "SELECT * FROM tenders"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY %s LIMIT ?" % order
    params.append(limit)
    return [_tender_view(r) for r in get_db().query_all(sql, tuple(params))]


def all_tenders(include_archived=False):
    sql = "SELECT * FROM tenders"
    if not include_archived:
        sql += " WHERE archived = 0"
    sql += " ORDER BY last_seen_at DESC"
    return [_tender_view(r) for r in get_db().query_all(sql)]


def set_tender_archived(tender_id, archived):
    get_db().execute("UPDATE tenders SET archived = ? WHERE id = ?",
                     (1 if archived else 0, tender_id))


def _bulk_set_archived(ids, value):
    if not ids:
        return 0
    db = get_db()
    v = 1 if value else 0
    for i in range(0, len(ids), 400):
        chunk = ids[i:i + 400]
        placeholders = ",".join("?" * len(chunk))
        db.execute("UPDATE tenders SET archived = ? WHERE id IN (%s)" % placeholders,
                   tuple([v] + chunk))
    return len(ids)


def archive_matching(filters):
    """Archive all ACTIVE tenders matching the filters. Returns count archived."""
    rows = search_tenders({**(filters or {}), "archived": 0}, limit=1000000)
    return _bulk_set_archived([r["id"] for r in rows], 1)


def restore_matching(filters):
    """Restore all ARCHIVED tenders matching the filters. Returns count restored."""
    rows = search_tenders({**(filters or {}), "archived": 1}, limit=1000000)
    return _bulk_set_archived([r["id"] for r in rows], 0)


def archive_older_than(first_seen_iso):
    """Archive active tenders first seen before the given ISO timestamp."""
    db = get_db()
    n = db.scalar(
        "SELECT COUNT(*) FROM tenders WHERE archived = 0 AND first_seen_at != '' "
        "AND first_seen_at < ?", (first_seen_iso,)) or 0
    db.execute(
        "UPDATE tenders SET archived = 1 WHERE archived = 0 AND first_seen_at != '' "
        "AND first_seen_at < ?", (first_seen_iso,))
    return n


def archive_existing():
    """Archive active tenders whose status is 'existing' (unchanged / already
    seen), keeping NEW and UPDATED ones in the active review list. Returns count.
    """
    db = get_db()
    n = db.scalar("SELECT COUNT(*) FROM tenders WHERE archived = 0 AND status = 'existing'") or 0
    db.execute("UPDATE tenders SET archived = 1 WHERE archived = 0 AND status = 'existing'")
    return n


def tenders_by_status(status):
    return search_tenders({"status": status, "archived": 0}, limit=100000)


def all_documents():
    return get_db().query_all(
        "SELECT d.*, t.tender_title, t.portal_name FROM documents d "
        "LEFT JOIN tenders t ON t.id = d.tender_id ORDER BY d.id DESC")


def dashboard_stats():
    db = get_db()
    total_portals = db.scalar("SELECT COUNT(*) FROM portals") or 0
    healthy = db.scalar("SELECT COUNT(*) FROM portals WHERE health = 'healthy'") or 0
    attention = db.scalar(
        "SELECT COUNT(*) FROM portals WHERE health IN ('attention', 'error')") or 0
    total_tenders = db.scalar("SELECT COUNT(*) FROM tenders") or 0
    archived_tenders = db.scalar("SELECT COUNT(*) FROM tenders WHERE archived = 1") or 0
    new_tenders = db.scalar("SELECT COUNT(*) FROM tenders WHERE status = 'new' AND archived = 0") or 0
    updated_tenders = db.scalar("SELECT COUNT(*) FROM tenders WHERE status = 'updated' AND archived = 0") or 0
    documents = db.scalar("SELECT COUNT(*) FROM documents WHERE status = 'downloaded'") or 0
    last_scan = db.query_one(
        "SELECT * FROM scans WHERE status IN ('success', 'baseline', 'partial') "
        "ORDER BY id DESC LIMIT 1")
    return {
        "total_portals": total_portals,
        "portals_healthy": healthy,
        "portals_attention": attention,
        "total_tenders": total_tenders,
        "archived_tenders": archived_tenders,
        "new_tenders": new_tenders,
        "updated_tenders": updated_tenders,
        "documents_downloaded": documents,
        "last_scan": last_scan,
        "recent_errors": recent_errors(5),
    }
