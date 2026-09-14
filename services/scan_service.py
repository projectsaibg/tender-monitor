"""Scan orchestration.

For each portal: collect via the adapter, normalize records, run a safe-scan
validation (guard against a portal that suddenly returns almost nothing),
then stage-commit new/updated/existing tenders, download documents, and record
the scan outcome. One portal failing never aborts the others.
"""
from __future__ import annotations

import time
import traceback

import config
from database.models import (SCAN_STATUS_SUCCESS, SCAN_STATUS_PARTIAL,
                             SCAN_STATUS_FAILED, SCAN_STATUS_BASELINE,
                             TENDER_STATUS_NEW, TENDER_STATUS_UPDATED,
                             TENDER_STATUS_EXISTING)
from scraper import downloader
from scraper.registry import select_adapter
from services import change_detector
from services import tender_service as ts
from utils.dates import normalize_date, utcnow_iso
from utils.text import parse_currency, keyword_match, has_negative_keyword, relevance_score
from utils.logging_setup import get_logger

log = get_logger("scanner")

_DATE_FIELDS = ("published_date", "bid_submission_start", "bid_submission_end", "opening_date")

# Simple in-process flag so the UI can show whether a scan is running.
_STATE = {"running": False, "current": ""}


def scan_state():
    return dict(_STATE)


def _normalize_tender(raw, portal):
    t = dict(raw)
    t["portal_id"] = portal["id"]
    t["portal_name"] = portal["name"]
    if not t.get("source_url"):
        t["source_url"] = portal["url"]
    for field in _DATE_FIELDS:
        if t.get(field):
            t[field] = normalize_date(t[field]) or t[field]
    t["estimated_value"] = parse_currency(t.get("estimated_value_text"))
    t["unique_key"] = ts.compute_unique_key(t)
    t["fingerprint"] = ts.fingerprint(t)
    _apply_relevance(t, portal)
    return t


def _match_blob(t):
    return " ".join(str(t.get(f, "")) for f in (
        "tender_title", "organisation", "tender_category", "product_category",
        "department", "eligibility", "location", "tender_reference"))


def _apply_relevance(t, portal):
    keywords = portal.get("keywords") or []
    negatives = portal.get("negative_keywords") or []
    mode = portal.get("keyword_mode") or "any"
    blob = _match_blob(t)

    matched = keyword_match(blob, keywords, mode) and not has_negative_keyword(blob, negatives)

    # Value-range filter (only excludes when the value is known).
    val = t.get("estimated_value")
    if matched and val is not None:
        if portal.get("min_value") is not None and val < portal["min_value"]:
            matched = False
        if portal.get("max_value") is not None and val > portal["max_value"]:
            matched = False

    score, band = relevance_score(t, keywords, portal.get("location"))
    t["matched"] = 1 if matched else 0
    t["relevance_score"] = score
    t["relevance_band"] = band


def _save_diagnostics(portal, status, error, diagnostics):
    try:
        config.ensure_directories()
        stamp = utcnow_iso().replace(":", "").replace("-", "")
        from utils import security
        host = security.sanitize_path_component(portal.get("name") or "portal")
        path = config.DIAGNOSTICS_DIR / ("scan_%s_%s.txt" % (host, stamp))
        lines = [
            "Portal: %s" % portal.get("name"),
            "URL: %s" % portal.get("url"),
            "Status: %s" % status,
            "Reason: %s" % error,
            "Final URL: %s" % (diagnostics or {}).get("final_url", ""),
            "Page title: %s" % (diagnostics or {}).get("title", ""),
            "Screenshot: %s" % (diagnostics or {}).get("screenshot", ""),
            "Time: %s" % utcnow_iso(),
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)
    except Exception:
        return ""


def scan_portal(portal_id, trigger="manual", fetch_fn=None, allow_private=None):
    portal = ts.get_portal(portal_id)
    if portal is None:
        raise ValueError("Portal %s not found" % portal_id)

    _STATE["running"] = True
    _STATE["current"] = portal["name"]
    started = time.time()
    scan_id = ts.create_scan(portal_id, portal["name"], trigger)
    log.info("Scan start | portal=%s | url=%s | trigger=%s", portal["name"], portal["url"], trigger)

    prior_count = ts.count_tenders_for_portal(portal_id)
    last_scan = ts.last_completed_scan(portal_id)
    is_first_scan = prior_count == 0 and last_scan is None
    baseline_mode = is_first_scan and not portal.get("treat_first_scan_as_new")

    result = {"portal_id": portal_id, "portal_name": portal["name"], "scan_id": scan_id,
              "status": "", "new": 0, "updated": 0, "existing": 0, "documents": 0,
              "pages": 0, "found": 0, "error": ""}

    try:
        adapter = select_adapter(portal)(
            portal, fetch_fn=fetch_fn, allow_private=allow_private, logger=log)
        collected = adapter.collect()
    except Exception as exc:  # never let one portal abort the batch
        detail = traceback.format_exc()
        log.error("Scan crashed | portal=%s | %s", portal["name"], exc)
        ts.add_scan_error(scan_id, portal_id, portal["name"], "exception", str(exc), detail)
        ts.finish_scan(scan_id, finished_at=utcnow_iso(),
                       duration_seconds=round(time.time() - started, 2),
                       status=SCAN_STATUS_FAILED, error_count=1,
                       notes="Adapter crashed: %s" % exc)
        ts.update_portal_health(portal_id, "error", "failed", utcnow_iso())
        _STATE["running"] = False
        result["status"] = SCAN_STATUS_FAILED
        result["error"] = str(exc)
        return result

    if collected["status"] != "ok":
        status = collected["status"]
        error = collected.get("error", "")
        diag_path = _save_diagnostics(portal, status, error, collected.get("diagnostics"))
        ts.add_scan_error(scan_id, portal_id, portal["name"], status, error, diag_path)
        ts.finish_scan(scan_id, finished_at=utcnow_iso(),
                       duration_seconds=round(time.time() - started, 2),
                       status=status, error_count=1, pages_processed=collected["pages_processed"],
                       notes=error)
        health = "attention" if status in ("captcha_required", "login_required",
                                           "structure_not_detected") else "error"
        ts.update_portal_health(portal_id, health, status, utcnow_iso())
        ts.add_notification("warning", "Portal needs attention: %s" % portal["name"],
                            "%s - %s" % (status, error))
        log.warning("Scan not ok | portal=%s | status=%s | %s", portal["name"], status, error)
        _STATE["running"] = False
        result["status"] = status
        result["error"] = error
        result["pages"] = collected["pages_processed"]
        return result

    raw_tenders = collected["tenders"]
    normalized = [_normalize_tender(r, portal) for r in raw_tenders]

    # Optionally keep only tenders that match the portal keyword filter, so the
    # database stores just the relevant ones (per-portal "Store only matching").
    portal_cfg = portal.get("config") if isinstance(portal.get("config"), dict) else {}
    if portal_cfg.get("only_matching") and (portal.get("keywords") or portal.get("negative_keywords")):
        normalized = [t for t in normalized if t.get("matched")]

    # De-duplicate within this scan by unique_key.
    unique = {}
    for t in normalized:
        unique.setdefault(t["unique_key"], t)
    normalized = list(unique.values())
    found = len(normalized)
    result["found"] = found
    result["pages"] = collected["pages_processed"]

    # ---- Safe-scan validation (spec 35/36) ------------------------------- #
    scan_status = SCAN_STATUS_BASELINE if baseline_mode else SCAN_STATUS_SUCCESS
    prev_found = (last_scan or {}).get("tenders_found") or 0
    partial = False
    if (prev_found >= config.STRUCTURE_MIN_PREV
            and found < prev_found * config.STRUCTURE_DROP_RATIO):
        partial = True
        scan_status = SCAN_STATUS_PARTIAL
        msg = ("Found %d tenders vs %d previously - POSSIBLE PORTAL STRUCTURE CHANGE. "
               "Previous data preserved." % (found, prev_found))
        ts.add_scan_error(scan_id, portal_id, portal["name"], "structure_change", msg, "")
        ts.add_notification("warning", "Possible structure change: %s" % portal["name"], msg)
        log.warning("Safe-scan | %s", msg)

    new_count, updated_count, existing_count, doc_count = _commit_tenders(
        normalized, portal, scan_id, baseline_mode, allow_private)

    result.update({"new": new_count, "updated": updated_count,
                   "existing": existing_count, "documents": doc_count,
                   "status": scan_status})

    ts.finish_scan(scan_id, finished_at=utcnow_iso(),
                   duration_seconds=round(time.time() - started, 2),
                   pages_processed=collected["pages_processed"], tenders_found=found,
                   new_count=new_count, updated_count=updated_count,
                   existing_count=existing_count, documents_downloaded=doc_count,
                   error_count=1 if partial else 0, status=scan_status,
                   notes="Baseline scan" if baseline_mode else ("Partial" if partial else ""))

    health = "attention" if partial else "healthy"
    ts.update_portal_health(portal_id, health, scan_status, utcnow_iso())
    _notify_scan(portal, new_count, updated_count, doc_count, baseline_mode)
    log.info("Scan done | portal=%s | found=%d new=%d updated=%d docs=%d status=%s",
             portal["name"], found, new_count, updated_count, doc_count, scan_status)
    _STATE["running"] = False
    return result


def _commit_tenders(normalized, portal, scan_id, baseline_mode, allow_private):
    from database.database import get_db
    db = get_db()
    new_count = updated_count = existing_count = doc_count = 0

    for t in normalized:
        existing_row = ts.get_tender_by_key(portal["id"], t["unique_key"])
        change_candidate = False
        if existing_row is None:
            status = TENDER_STATUS_EXISTING if baseline_mode else TENDER_STATUS_NEW
            tid = ts.insert_tender(t, status)
            if status == TENDER_STATUS_NEW:
                new_count += 1
                change_candidate = True
            else:
                existing_count += 1
            tender_db_id = tid
        else:
            changes = change_detector.detect_changes(existing_row, t)
            if changes:
                ts.update_tender(existing_row["id"], t, TENDER_STATUS_UPDATED)
                ts.record_versions(existing_row["id"], changes, scan_id)
                # A changed tender resurfaces into the active list even if it was
                # previously archived, so updates are never missed.
                ts.set_tender_archived(existing_row["id"], False)
                updated_count += 1
                change_candidate = True
            else:
                ts.touch_tender_seen(existing_row["id"], TENDER_STATUS_EXISTING)
                existing_count += 1
            tender_db_id = existing_row["id"]

        if (portal.get("download_documents") and t.get("matched") and change_candidate
                and t.get("document_urls") and doc_count < config.MAX_DOWNLOADS_PER_SCAN):
            tender_row = {"id": tender_db_id, "portal_id": portal["id"],
                          "portal_name": portal["name"],
                          "tender_id": t.get("tender_id"),
                          "tender_reference": t.get("tender_reference")}
            _recs, n = downloader.download_tender_documents(
                db, tender_row, t["document_urls"], allow_private=allow_private,
                max_downloads=config.MAX_DOWNLOADS_PER_SCAN - doc_count)
            doc_count += n

    return new_count, updated_count, existing_count, doc_count


def _notify_scan(portal, new_count, updated_count, doc_count, baseline_mode):
    if baseline_mode:
        ts.add_notification("info", "Baseline created: %s" % portal["name"],
                            "Baseline recorded. Future scans will flag new/updated tenders.")
    elif new_count or updated_count:
        ts.add_notification(
            "info", "Scan complete: %s" % portal["name"],
            "%d new, %d updated, %d documents downloaded." % (new_count, updated_count, doc_count))


def scan_all(trigger="manual", fetch_fn=None, allow_private=None):
    portals = ts.list_portals(enabled_only=True)
    results = []
    for portal in portals:
        try:
            results.append(scan_portal(portal["id"], trigger, fetch_fn, allow_private))
        except Exception as exc:
            log.error("Portal %s failed: %s", portal["name"], exc)
            results.append({"portal_id": portal["id"], "portal_name": portal["name"],
                            "status": SCAN_STATUS_FAILED, "error": str(exc),
                            "new": 0, "updated": 0, "documents": 0})
    _STATE["running"] = False
    _STATE["current"] = ""
    summary = {
        "portals": len(results),
        "successful": sum(1 for r in results if r["status"] in
                          (SCAN_STATUS_SUCCESS, SCAN_STATUS_BASELINE, SCAN_STATUS_PARTIAL)),
        "new": sum(r.get("new", 0) for r in results),
        "updated": sum(r.get("updated", 0) for r in results),
        "documents": sum(r.get("documents", 0) for r in results),
        "results": results,
    }
    return summary
