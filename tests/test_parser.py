"""Generic parser tests against mock HTML (no browser, no network)."""
from scraper import parser, discovery
from tests import mock_data


def test_table_extraction():
    res = parser.extract(mock_data.LISTING_V1, base_url="https://mock.gov.in/list")
    assert res["method"] == "table"
    assert len(res["tenders"]) == 3
    ids = {t["tender_id"] for t in res["tenders"]}
    assert {"T-001", "T-002", "T-003"} == ids
    t1 = next(t for t in res["tenders"] if t["tender_id"] == "T-001")
    assert t1["organisation"] == "PHED"
    assert t1["bid_submission_end"] == "20 September 2026"
    assert any("nit.pdf" in u for u in t1["document_urls"])
    assert t1["tender_detail_url"].endswith("/tender/T-001")


def test_card_extraction():
    res = parser.extract(mock_data.CARDS_V1, base_url="https://mock.gov.in/list")
    assert res["method"] == "cards"
    assert len(res["tenders"]) == 3
    titles = {t["tender_title"] for t in res["tenders"]}
    assert "Water supply scheme" in titles
    c1 = next(t for t in res["tenders"] if "Water" in t["tender_title"])
    assert c1["organisation"] == "PHED"
    assert c1["bid_submission_end"] == "2026-10-05"


def test_pagination_detected():
    res = parser.extract(mock_data.PAGE_1, base_url="https://mock.gov.in/list")
    assert res["next_page_url"] is not None
    assert res["next_page_url"].endswith("page=2")
    res2 = parser.extract(mock_data.PAGE_2, base_url="https://mock.gov.in/list")
    assert res2["next_page_url"] is None


def test_captcha_and_login_detection():
    assert discovery.detect_captcha(mock_data.CAPTCHA_PAGE) is True
    assert discovery.detect_captcha(mock_data.LISTING_V1) is False
    from bs4 import BeautifulSoup
    assert discovery.detect_login_required(BeautifulSoup(mock_data.LOGIN_PAGE, "lxml")) is True
    assert discovery.detect_login_required(BeautifulSoup(mock_data.LISTING_V1, "lxml")) is False


def test_analyze_reports_fields():
    info = discovery.analyze(mock_data.LISTING_V1, base_url="https://mock.gov.in/list")
    assert info["listing_detected"] is True
    assert info["tender_id_detected"] is True
    assert info["closing_date_detected"] is True
    assert info["organisation_detected"] is True
    assert info["captcha_detected"] is False


def test_nic_style_td_headers_and_combined_column():
    res = parser.extract(mock_data.NIC_LISTING, base_url="https://eprocure.x.gov.in/nicgep/app")
    assert res["method"] == "table"
    assert len(res["tenders"]) == 2
    t = res["tenders"][0]
    assert t["tender_id"] == "2026_DAHV_31788_1"
    assert t["tender_title"] == "Supply of Laboratory Equipments"
    assert "No.1-2" in t["tender_reference"]
    assert "ANIMAL HUSBANDRY" in t["organisation"]
    assert t["published_date"].startswith("11-Sep-2026")
    assert t["bid_submission_end"].startswith("29-Sep-2026")
    assert res["tenders"][1]["tender_id"] == "2026_DDW_31843_1"
