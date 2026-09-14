"""Currency parsing, keyword matching and relevance scoring."""
from utils import text


def test_parse_currency_plain():
    assert text.parse_currency("Rs. 15,00,000") == 1500000.0
    assert text.parse_currency("1,250.50") == 1250.50
    assert text.parse_currency("") is None
    assert text.parse_currency(None) is None


def test_parse_currency_multipliers():
    assert text.parse_currency("Rs. 5 Lakh") == 500000.0
    assert text.parse_currency("1.5 Crore") == 15000000.0
    assert text.parse_currency("2 million") == 2000000.0


def test_keyword_match_modes():
    assert text.keyword_match("Water pipeline work", ["water"]) is True
    assert text.keyword_match("Road work", ["water"]) is False
    assert text.keyword_match("Water pipeline", ["water", "pipeline"], "all") is True
    assert text.keyword_match("Water only", ["water", "pipeline"], "all") is False
    assert text.keyword_match("anything", []) is True


def test_negative_keywords():
    assert text.has_negative_keyword("Vehicle hire", ["vehicle"]) is True
    assert text.has_negative_keyword("Water work", ["vehicle"]) is False


def test_relevance_scoring():
    tender = {"tender_title": "Water pipeline WTP", "organisation": "PHED",
              "tender_category": "Works", "location": "Kota"}
    score, band = text.relevance_score(tender, ["water", "WTP"], "Kota")
    assert score > 0
    assert band in ("HIGH", "MEDIUM", "LOW")
    score2, band2 = text.relevance_score(tender, [])
    assert band2 == "MEDIUM"
