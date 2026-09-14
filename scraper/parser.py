"""Generic HTML tender parser.

Given a page of HTML, attempt to discover tender listings without assuming any
particular site structure. Two strategies are tried - table extraction and
repeated-card extraction - and the one yielding the most/best records wins.

This module is pure (HTML in, data out) so it can be unit-tested against mock
pages with no browser or network.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from database.models import new_tender_dict
from utils import security

# Ordered header-to-field rules. First matching rule wins for a given header.
# More specific patterns are placed before more general ones.
_HEADER_RULES = [
    ("title_ref_id", ["title and ref", "title and reference", "ref.no./tender id",
                      "title and tender"]),
    ("emd", ["emd", "earnest money"]),
    ("tender_fee", ["tender fee", "document fee", "form fee", "cost of tender", "processing fee"]),
    ("tender_reference", ["reference", "ref no", "ref.", "file no", "nit no", "tender no"]),
    ("tender_id", ["tender id", "bid id", "e-tender id", "tender identifier", "id"]),
    ("bid_submission_end", ["closing", "last date", "due date", "submission end", "submission deadline", "bid submission closing", "closing date"]),
    ("bid_submission_start", ["submission start", "bid submission start", "start date"]),
    ("opening_date", ["opening", "bid opening", "tender opening"]),
    ("published_date", ["published", "publish", "e-published", "date of publish"]),
    ("estimated_value", ["estimated cost", "estimated value", "tender value", "value", "amount", "contract value"]),
    ("work_period", ["completion period", "work period", "period of work", "duration"]),
    ("tender_category", ["category", "classification", "sector"]),
    ("tender_type", ["tender type", "bid type", "form of contract"]),
    ("organisation", ["organisation", "organization", "ministry", "authority", "department", "dept", "office", "employer"]),
    ("location", ["location", "district", "state", "city", "region", "place", "area"]),
    ("tender_title", ["title", "name of work", "work description", "description", "brief", "subject", "work", "tender brief"]),
]


def _clean(text):
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def _map_header(header_text):
    h = _clean(header_text).lower()
    if not h:
        return None
    for field, needles in _HEADER_RULES:
        for needle in needles:
            if needle in h:
                return field
    return None


def _is_document_link(href, text=""):
    if not href:
        return False
    # Note: no SSRF check here - parsing is offline/pure. URLs are validated at
    # download time by scraper.downloader before any request is made.
    lowered = href.lower().split("?")[0]
    for ext in security.ALLOWED_DOWNLOAD_EXTENSIONS:
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff"):
            continue  # images are not tender documents by default
        if lowered.endswith(ext):
            return True
    hint = (text or "").lower()
    return any(w in hint for w in ("download", "nit", "boq", "corrigendum", ".pdf", "notice", "document"))


def _collect_links(node, base_url):
    detail_url = ""
    documents = []
    for a in node.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        absolute = urljoin(base_url, href)
        text = _clean(a.get_text())
        if _is_document_link(absolute, text):
            if absolute not in documents:
                documents.append(absolute)
        elif not detail_url:
            detail_url = absolute
    return detail_url, documents


def _direct_rows(table):
    """Rows belonging directly to this table (not to a nested table)."""
    return [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]


def _row_field_map(cells):
    mapping = {}
    raw = {}
    used = set()
    for idx, cell in enumerate(cells):
        text = _clean(cell.get_text())
        raw[idx] = text
        field = _map_header(text)
        if field and field not in used:
            mapping[idx] = field
            used.add(field)
    return mapping, raw


def _find_header_row(rows):
    """Locate the header row and its field mapping.

    Prefers a row with <th> cells; otherwise picks the earliest short row whose
    cells map to the most distinct tender fields. This handles portals (e.g. NIC
    eProcurement) that use styled <td> header cells with no <thead>/<th>.
    """
    for i, row in enumerate(rows):
        if row.find_all("th"):
            mapping, raw = _row_field_map(row.find_all(["th", "td"]))
            if mapping:
                return i, mapping, raw
    best = None
    for i, row in enumerate(rows[:10]):
        cells = row.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        mapping, raw = _row_field_map(cells)
        if not raw:
            continue
        avg_len = sum(len(v) for v in raw.values()) / len(raw)
        if len(mapping) >= 2 and avg_len < 40:
            if best is None or len(mapping) > best[0]:
                best = (len(mapping), i, mapping, raw)
    if best:
        return best[1], best[2], best[3]
    return None, {}, {}


_NIC_ID_RE = re.compile(r"\d{4}_[A-Za-z0-9]+_\d+_\d+")


def _split_title_ref_id(value):
    """Split a NIC-style "[Title] [Ref][Tender ID]" cell into its parts."""
    tender_id = ""
    match = _NIC_ID_RE.search(value)
    if match:
        tender_id = match.group(0)
    groups = re.findall(r"\[([^\[\]]+)\]", value)
    title = ref = ""
    if groups:
        title = groups[0].strip()
        remaining = [g.strip() for g in groups[1:] if not (tender_id and tender_id in g)]
        if remaining:
            ref = remaining[-1].strip()
    else:
        title = value.strip()
    return title, ref, tender_id


def _assign_cell(tender, field, value):
    if field == "estimated_value":
        if not tender.get("estimated_value_text"):
            tender["estimated_value_text"] = value
    elif field == "title_ref_id":
        title, ref, tid = _split_title_ref_id(value)
        if title and not tender.get("tender_title"):
            tender["tender_title"] = title
        if ref and not tender.get("tender_reference"):
            tender["tender_reference"] = ref
        if tid and not tender.get("tender_id"):
            tender["tender_id"] = tid
    elif not tender.get(field):
        tender[field] = value


def _extract_from_table(table, base_url):
    rows = _direct_rows(table)
    if len(rows) < 2:
        return []
    header_idx, mapped, raw_labels = _find_header_row(rows)
    if not mapped:
        return []
    records = []
    for row in rows[header_idx + 1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        tender = new_tender_dict()
        extra = {}
        used_field = False
        for idx, cell in enumerate(cells):
            value = _clean(cell.get_text())
            field = mapped.get(idx)
            if field:
                _assign_cell(tender, field, value)
                used_field = True
            elif value:
                label = raw_labels.get(idx) or ("column_%d" % idx)
                extra[label] = value
        detail_url, documents = _collect_links(row, base_url)
        if detail_url:
            tender["tender_detail_url"] = detail_url
        if documents:
            tender["document_urls"] = documents
        if extra:
            tender["extra_fields"] = extra
        if not used_field:
            continue
        if not (tender["tender_title"] or tender["tender_id"] or tender["tender_reference"]):
            continue
        records.append(tender)
    return records


def _card_signature(el):
    classes = tuple(sorted(el.get("class") or []))
    return (el.name, classes)


def _find_card_groups(soup):
    groups = {}
    for el in soup.find_all(["div", "li", "article", "section"]):
        parent = el.parent
        if parent is None:
            continue
        sig = (id(parent), _card_signature(el))
        groups.setdefault(sig, []).append(el)
    candidates = []
    for sig, members in groups.items():
        if len(members) >= 3 and sig[1][1]:  # require a class and repetition
            candidates.append(members)
    return candidates


def _card_title(el):
    for tag in ("h1", "h2", "h3", "h4", "h5", "strong", "b"):
        node = el.find(tag)
        if node:
            text = _clean(node.get_text())
            if text:
                return text
    link = el.find("a")
    if link:
        return _clean(link.get_text())
    return ""


def _extract_card(el, base_url):
    tender = new_tender_dict()
    tender["tender_title"] = _card_title(el)
    extra = {}

    # dt/dd definition lists.
    for dt in el.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        field = _map_header(dt.get_text())
        value = _clean(dd.get_text())
        if field and value:
            _assign(tender, field, value)
        elif value:
            extra[_clean(dt.get_text())] = value

    # "Label: value" lines.
    for line in el.get_text("\n").split("\n"):
        line = _clean(line)
        m = re.match(r"^(.{2,40}?)\s*[:–\-]\s*(.+)$", line)
        if not m:
            continue
        field = _map_header(m.group(1))
        value = _clean(m.group(2))
        if field and value and not tender.get(field):
            _assign(tender, field, value)

    detail_url, documents = _collect_links(el, base_url)
    if detail_url:
        tender["tender_detail_url"] = detail_url
    if documents:
        tender["document_urls"] = documents
    if extra:
        tender["extra_fields"] = extra

    if not (tender["tender_title"] or tender["tender_id"] or tender["tender_reference"]):
        return None
    # A card with only a title and nothing else is likely a nav item; require
    # at least one extra signal (a field, a link or a document).
    signals = any(tender[f] for f in ("tender_id", "tender_reference", "organisation",
                                      "bid_submission_end", "published_date", "location"))
    if not (signals or detail_url or documents):
        return None
    return tender


def _assign(tender, field, value):
    if field == "estimated_value":
        tender["estimated_value_text"] = value
    else:
        tender[field] = value


def _find_next_page(soup, base_url):
    a = soup.find("a", rel="next")
    if a and a.get("href"):
        return urljoin(base_url, a["href"])
    link = soup.find("link", rel="next")
    if link and link.get("href"):
        return urljoin(base_url, link["href"])
    for a in soup.find_all("a", href=True):
        text = _clean(a.get_text()).lower()
        rel = " ".join(a.get("rel") or []).lower()
        if text in ("next", "next >", "next page", "»", ">", "older") or "next" in rel:
            href = a["href"]
            if href and not href.startswith("#"):
                return urljoin(base_url, href)
    return None


def extract(html, base_url="", config=None):
    """Parse tenders from an HTML page.

    Returns a dict with keys: tenders, next_page_url, method, tables_found,
    cards_found.
    """
    soup = BeautifulSoup(html or "", "lxml")

    best_table = []
    tables = soup.find_all("table")
    for table in tables:
        recs = _extract_from_table(table, base_url)
        if len(recs) > len(best_table):
            best_table = recs

    best_cards = []
    for group in _find_card_groups(soup):
        recs = []
        for el in group:
            card = _extract_card(el, base_url)
            if card:
                recs.append(card)
        if len(recs) > len(best_cards):
            best_cards = recs

    if best_table and len(best_table) >= len(best_cards):
        tenders, method = best_table, "table"
    elif best_cards:
        tenders, method = best_cards, "cards"
    else:
        tenders, method = [], "none"

    return {
        "tenders": tenders,
        "next_page_url": _find_next_page(soup, base_url),
        "method": method,
        "tables_found": len(tables),
        "cards_found": len(best_cards),
    }
