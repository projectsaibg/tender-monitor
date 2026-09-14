"""Field-level change detection between a stored tender and a freshly-scraped one.

Produces a list of change records (field, old, new, change_type). Date fields
get semantic change types (e.g. CLOSING DATE EXTENDED); everything else gets a
generic FIELD CHANGED, plus a couple of value-specific labels.
"""
from __future__ import annotations

from database.models import MONITORED_FIELDS, FIELD_LABELS, DATE_CHANGE_FIELDS
from utils.dates import parse_datetime


def _norm(value):
    if isinstance(value, (list, tuple)):
        return sorted(str(v).strip() for v in value if str(v).strip())
    return " ".join(str(value or "").split())


def _as_text(value):
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value or "")


def _date_change_type(field, old_text, new_text):
    later_label, earlier_label = DATE_CHANGE_FIELDS[field]
    old_dt = parse_datetime(old_text)
    new_dt = parse_datetime(new_text)
    if old_dt and new_dt:
        if new_dt > old_dt:
            return later_label
        if new_dt < old_dt:
            return earlier_label
    return "%s CHANGED" % FIELD_LABELS.get(field, field).upper()


def detect_changes(old_tender, new_tender):
    """Return a list of change dicts. Empty list means no monitored change."""
    changes = []
    for field in MONITORED_FIELDS:
        old_val = old_tender.get(field)
        new_val = new_tender.get(field)
        if _norm(old_val) == _norm(new_val):
            continue
        # Ignore a change that merely fills a previously-empty field with nothing.
        if not _norm(old_val) and not _norm(new_val):
            continue

        if field in DATE_CHANGE_FIELDS:
            change_type = _date_change_type(field, _as_text(old_val), _as_text(new_val))
        elif field == "document_urls":
            change_type = "DOCUMENT LINKS CHANGED"
        elif field == "estimated_value_text":
            change_type = "ESTIMATED VALUE CHANGED"
        elif field == "emd":
            change_type = "EMD CHANGED"
        elif field == "tender_fee":
            change_type = "TENDER FEE CHANGED"
        else:
            change_type = "%s CHANGED" % FIELD_LABELS.get(field, field).upper()

        changes.append({
            "field": field,
            "label": FIELD_LABELS.get(field, field),
            "old": _as_text(old_val),
            "new": _as_text(new_val),
            "change_type": change_type,
        })
    return changes


def has_changes(old_tender, new_tender):
    return len(detect_changes(old_tender, new_tender)) > 0
