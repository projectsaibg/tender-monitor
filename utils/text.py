"""Text helpers: currency parsing, keyword matching and relevance scoring."""
from __future__ import annotations

import re

_MULTIPLIERS = [
    (re.compile(r"\bcrores?\b", re.IGNORECASE), 10_000_000),
    (re.compile(r"\blakhs?\b", re.IGNORECASE), 100_000),
    (re.compile(r"\blacs?\b", re.IGNORECASE), 100_000),
    (re.compile(r"\bmillion\b|\bmn\b", re.IGNORECASE), 1_000_000),
    (re.compile(r"\bbillion\b|\bbn\b", re.IGNORECASE), 1_000_000_000),
    (re.compile(r"\bthousand\b", re.IGNORECASE), 1_000),
]
_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def parse_currency(text):
    """Parse a currency string to a float amount.

    Handles symbols (Rs, INR, the rupee sign), thousands separators (including
    Indian grouping) and word multipliers (lakh, crore, million). Returns None
    when no number can be found.
    """
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)

    s = str(text).strip()
    if not s:
        return None

    match = _NUMBER_RE.search(s)
    if not match:
        return None

    number_str = match.group().replace(",", "")
    try:
        value = float(number_str)
    except ValueError:
        return None

    for pattern, factor in _MULTIPLIERS:
        if pattern.search(s):
            value *= factor
            break

    return value


def _normalise(text):
    if isinstance(text, str):
        return text.lower()
    return str(text or "").lower()


def keyword_match(text, keywords, mode="any"):
    """Case-insensitive keyword match. Empty ``keywords`` means 'no filter'."""
    if not keywords:
        return True
    haystack = _normalise(text)
    valid = [kw for kw in keywords if kw]
    hits = [kw for kw in valid if kw.lower() in haystack]
    if mode == "all":
        return len(hits) == len(valid) and len(valid) > 0
    return len(hits) > 0


def has_negative_keyword(text, negatives):
    if not negatives:
        return False
    haystack = _normalise(text)
    return any(kw and kw.lower() in haystack for kw in negatives)


def count_keyword_hits(text, keywords):
    if not keywords:
        return 0
    haystack = _normalise(text)
    return sum(1 for kw in keywords if kw and kw.lower() in haystack)


def relevance_score(tender, keywords, location=None):
    """Compute a 0-100 relevance score and a band (HIGH/MEDIUM/LOW).

    Heuristic ranking aid only. Does NOT determine legal/technical eligibility.
    """
    title = _normalise(tender.get("tender_title"))
    org = _normalise(tender.get("organisation"))
    category = _normalise(tender.get("tender_category")) + " " + _normalise(tender.get("product_category"))
    loc = _normalise(tender.get("location"))
    blob = " ".join([
        title, org, category, loc,
        _normalise(tender.get("eligibility")),
        _normalise(tender.get("department")),
    ])

    kw = [k for k in (keywords or []) if k]
    if not kw:
        return 50, "MEDIUM"

    score = 0
    for k in kw:
        kl = k.lower()
        if kl in title:
            score += 25
        elif kl in category:
            score += 15
        elif kl in org:
            score += 12
        elif kl in blob:
            score += 8

    if location and location.lower().strip() and location.lower().strip() in loc:
        score += 15

    score = max(0, min(100, score))
    if score >= 60:
        band = "HIGH"
    elif score >= 30:
        band = "MEDIUM"
    else:
        band = "LOW"
    return score, band
