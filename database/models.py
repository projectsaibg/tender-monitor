"""Domain constants and helpers shared across the app.

Kept deliberately simple: rows are handled as dicts throughout, so this module
provides the canonical field lists, change-detection field set, default settings
and small JSON helpers rather than a heavy ORM.
"""
from __future__ import annotations

import json

# Canonical normalized tender fields (see spec section 8).
TENDER_FIELDS = [
    "portal_id", "portal_name", "source_url", "tender_id", "tender_reference",
    "tender_title", "organisation", "department", "tender_category",
    "product_category", "tender_type", "location", "published_date",
    "bid_submission_start", "bid_submission_end", "opening_date",
    "estimated_value", "estimated_value_text", "emd", "tender_fee",
    "work_period", "eligibility", "tender_detail_url", "document_urls",
    "extra_fields",
]

# Fields compared to decide UPDATED vs EXISTING (see spec section 11).
MONITORED_FIELDS = [
    "tender_title", "estimated_value_text", "emd", "tender_fee",
    "published_date", "bid_submission_end", "opening_date", "eligibility",
    "work_period", "organisation", "location", "tender_category",
    "document_urls",
]

# Human labels for change records.
FIELD_LABELS = {
    "tender_title": "Title",
    "estimated_value_text": "Estimated Value",
    "emd": "EMD",
    "tender_fee": "Tender Fee",
    "published_date": "Published Date",
    "bid_submission_end": "Closing Date",
    "opening_date": "Opening Date",
    "eligibility": "Eligibility",
    "work_period": "Work Period",
    "organisation": "Organisation",
    "location": "Location",
    "tender_category": "Category",
    "document_urls": "Document Links",
}

# Date fields where we detect EXTENDED / ADVANCED rather than a plain change.
DATE_CHANGE_FIELDS = {
    "bid_submission_end": ("CLOSING DATE EXTENDED", "CLOSING DATE ADVANCED"),
    "opening_date": ("OPENING DATE POSTPONED", "OPENING DATE ADVANCED"),
    "published_date": ("PUBLISHED DATE CHANGED", "PUBLISHED DATE CHANGED"),
}

# Settings stored in the DB (all user-editable; SMTP password never logged).
DEFAULT_SETTINGS = {
    "timezone": "",  # blank -> falls back to config.DEFAULT_TIMEZONE
    "smtp_host": "",
    "smtp_port": "587",
    "smtp_username": "",
    "smtp_password": "",
    "smtp_use_tls": "1",
    "email_from": "",
    "email_to": "",
    "notify_enabled": "0",
    "notify_only_if_new": "1",
    "notify_only_high_relevance": "0",
    "notify_only_errors": "0",
    "notify_attach_excel": "1",
}

TENDER_STATUS_NEW = "new"
TENDER_STATUS_UPDATED = "updated"
TENDER_STATUS_EXISTING = "existing"

SCAN_STATUS_SUCCESS = "success"
SCAN_STATUS_PARTIAL = "partial"
SCAN_STATUS_FAILED = "failed"
SCAN_STATUS_BASELINE = "baseline"


def dump_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def load_json(text, default=None):
    if text is None or text == "":
        return default if default is not None else []
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return default if default is not None else []


def new_tender_dict(portal_id=0):
    """Return a normalized tender dict with all fields defaulted."""
    d = {f: "" for f in TENDER_FIELDS}
    d["portal_id"] = portal_id
    d["estimated_value"] = None
    d["document_urls"] = []
    d["extra_fields"] = {}
    return d
