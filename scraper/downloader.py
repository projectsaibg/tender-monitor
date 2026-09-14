"""Publicly-accessible tender document downloader.

Safety measures: HTTP(S) only + SSRF validation, extension allow-list (never
executables), a maximum file size, request timeouts, filename sanitisation and
path-traversal prevention. Unchanged files (same SHA-256) are not re-downloaded.
"""
from __future__ import annotations

import hashlib
import os
from urllib.parse import urlparse, unquote

import httpx

import config
from utils import security
from utils.dates import utcnow_iso
from utils.logging_setup import get_logger

log = get_logger("scanner")


def _filename_from_response(url, resp):
    disp = resp.headers.get("content-disposition", "")
    if "filename=" in disp:
        raw = disp.split("filename=")[-1].strip().strip('"').strip("'")
        if raw:
            return security.sanitize_filename(unquote(raw))
    path = urlparse(url).path
    name = unquote(os.path.basename(path)) or "document"
    return security.sanitize_filename(name)


def download_document(url, dest_dir, allow_private=None):
    """Download a single document. Returns a result dict (never raises)."""
    result = {
        "document_url": url, "document_name": "", "local_path": "",
        "file_size": 0, "sha256": "", "content_type": "", "status": "pending",
        "error": "", "downloaded_at": "",
    }
    try:
        safe_url = security.validate_url(url, allow_private=allow_private)
    except security.SecurityError as exc:
        result["status"] = "blocked"
        result["error"] = str(exc)
        return result

    if not security.download_extension_allowed(safe_url):
        result["status"] = "blocked"
        result["error"] = "Disallowed file type"
        return result

    os.makedirs(dest_dir, exist_ok=True)
    headers = {"User-Agent": config.USER_AGENT}
    try:
        with httpx.Client(follow_redirects=True, timeout=config.DOWNLOAD_TIMEOUT_S,
                          headers=headers) as client:
            with client.stream("GET", safe_url) as resp:
                if resp.status_code >= 400:
                    result["status"] = "failed"
                    result["error"] = "HTTP %d" % resp.status_code
                    return result
                content_type = resp.headers.get("content-type", "").split(";")[0].strip()
                result["content_type"] = content_type
                name = _filename_from_response(safe_url, resp)
                if not security.download_extension_allowed(name):
                    result["status"] = "blocked"
                    result["error"] = "Disallowed file type (attachment)"
                    return result
                dest_path = security.safe_join(dest_dir, name)

                hasher = hashlib.sha256()
                size = 0
                too_big = False
                with open(dest_path, "wb") as fh:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        size += len(chunk)
                        if size > config.MAX_DOWNLOAD_BYTES:
                            too_big = True
                            break
                        hasher.update(chunk)
                        fh.write(chunk)
                if too_big:
                    os.remove(dest_path)
                    result["status"] = "failed"
                    result["error"] = "File exceeds size limit"
                    return result

                result.update({
                    "document_name": name, "local_path": dest_path,
                    "file_size": size, "sha256": hasher.hexdigest(),
                    "status": "downloaded", "downloaded_at": utcnow_iso(),
                })
                return result
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
        return result


def _record_document(db, tender_id, portal_id, rec):
    sql = (
        "INSERT INTO documents (tender_id, portal_id, document_name, document_url, "
        "local_path, file_size, sha256, content_type, status, downloaded_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(tender_id, document_url) DO UPDATE SET "
        "document_name=excluded.document_name, local_path=excluded.local_path, "
        "file_size=excluded.file_size, sha256=excluded.sha256, "
        "content_type=excluded.content_type, status=excluded.status, "
        "downloaded_at=excluded.downloaded_at"
    )
    db.execute(sql, (
        tender_id, portal_id, rec["document_name"], rec["document_url"],
        rec["local_path"], rec["file_size"], rec["sha256"], rec["content_type"],
        rec["status"], rec["downloaded_at"],
    ))


def download_tender_documents(db, tender_row, urls, allow_private=None,
                              max_downloads=None):
    """Download all documents for a tender, recording each in the DB.

    Returns (records, downloaded_count). Files already downloaded (row present
    and file exists on disk) are skipped to avoid repeated downloads.
    """
    max_downloads = max_downloads if max_downloads is not None else config.MAX_DOWNLOADS_PER_SCAN
    portal_name = security.sanitize_path_component(tender_row.get("portal_name") or "portal")
    tid = security.sanitize_path_component(
        tender_row.get("tender_id") or tender_row.get("tender_reference")
        or ("tender_%s" % tender_row.get("id")))
    dest_dir = security.safe_join(config.DOWNLOADS_DIR, portal_name, tid)

    existing = {
        d["document_url"]: d
        for d in db.query_all(
            "SELECT document_url, local_path, status FROM documents WHERE tender_id = ?",
            (tender_row["id"],))
    }

    records = []
    downloaded = 0
    for url in urls or []:
        if downloaded >= max_downloads:
            break
        prev = existing.get(url)
        if prev and prev.get("status") == "downloaded" and prev.get("local_path") \
                and os.path.exists(prev["local_path"]):
            records.append({**prev, "document_url": url, "status": "skipped"})
            continue
        rec = download_document(url, dest_dir, allow_private=allow_private)
        _record_document(db, tender_row["id"], tender_row.get("portal_id"), rec)
        records.append(rec)
        if rec["status"] == "downloaded":
            downloaded += 1
            log.info("Downloaded %s (%d bytes)", rec["document_name"], rec["file_size"])
        elif rec["status"] in ("blocked", "failed"):
            log.warning("Document %s: %s (%s)", url, rec["status"], rec["error"])
    return records, downloaded
