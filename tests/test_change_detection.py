"""Field-level change detection tests."""
from services import change_detector as cd


def _base():
    return {
        "tender_title": "Water work", "estimated_value_text": "Rs. 5 Lakh",
        "emd": "Rs. 10,000", "tender_fee": "Rs. 500",
        "published_date": "2026-09-02", "bid_submission_end": "2026-09-20",
        "opening_date": "2026-09-21", "eligibility": "Class A",
        "work_period": "6 months", "organisation": "PHED", "location": "Kota",
        "tender_category": "Works", "document_urls": ["https://x/a.pdf"],
    }


def test_no_change():
    assert cd.detect_changes(_base(), _base()) == []


def test_closing_date_extended():
    old = _base()
    new = _base()
    new["bid_submission_end"] = "2026-09-27"
    changes = cd.detect_changes(old, new)
    assert len(changes) == 1
    assert changes[0]["field"] == "bid_submission_end"
    assert changes[0]["change_type"] == "CLOSING DATE EXTENDED"


def test_closing_date_advanced():
    old = _base()
    new = _base()
    new["bid_submission_end"] = "2026-09-15"
    changes = cd.detect_changes(old, new)
    assert changes[0]["change_type"] == "CLOSING DATE ADVANCED"


def test_value_and_documents_change():
    old = _base()
    new = _base()
    new["estimated_value_text"] = "Rs. 8 Lakh"
    new["document_urls"] = ["https://x/a.pdf", "https://x/b.pdf"]
    changes = {c["field"]: c["change_type"] for c in cd.detect_changes(old, new)}
    assert changes["estimated_value_text"] == "ESTIMATED VALUE CHANGED"
    assert changes["document_urls"] == "DOCUMENT LINKS CHANGED"


def test_multiple_changes():
    old = _base()
    new = _base()
    new["organisation"] = "PWD"
    new["eligibility"] = "Class B"
    assert len(cd.detect_changes(old, new)) == 2
