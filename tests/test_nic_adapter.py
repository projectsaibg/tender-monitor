"""NIC eProcurement detection and adapter selection (offline)."""
from scraper.nic_adapter import is_nic_portal, NicEprocurementAdapter
from scraper.registry import select_adapter, get_adapter_class
from scraper.generic import GenericPortalAdapter


def test_is_nic_portal():
    assert is_nic_portal("https://wbtenders.gov.in/nicgep/app") is True
    assert is_nic_portal("https://eprocure.goa.gov.in/nicgep/app?page=x") is True
    assert is_nic_portal("https://wbphed.gov.in/en/tenders") is False
    assert is_nic_portal("https://example.com", "<html>Powered by nicgep</html>") is True


def test_select_adapter_autodetects_nic():
    nic = select_adapter({"adapter": "generic", "url": "https://x.gov.in/nicgep/app"})
    assert nic is NicEprocurementAdapter
    generic = select_adapter({"adapter": "generic", "url": "https://x.gov.in/tenders"})
    assert generic is GenericPortalAdapter


def test_explicit_adapter_wins():
    assert select_adapter({"adapter": "nic", "url": "https://x.gov.in/anything"}) is NicEprocurementAdapter
    assert get_adapter_class("nic") is NicEprocurementAdapter


def test_next_listing_page_follows_strict_next():
    from scraper.nic_adapter import next_listing_page
    html = ('<table><tr><td>rows</td></tr></table>'
            '<a href="/nicgep/app?page=FrontEndTendersByOrganisation&sp=2">Next</a>')
    url = next_listing_page(html, "https://x.gov.in/nicgep/app?sp=1")
    assert url is not None and url.endswith("sp=2")


def test_next_listing_page_ignores_tender_links():
    from scraper.nic_adapter import next_listing_page
    # A tender-detail link must never be treated as pagination, even if its
    # text is a bare ">" character.
    html = '<a href="/nicgep/app?page=FrontEndViewTender&sp=abc">&gt;</a>'
    assert next_listing_page(html, "https://x.gov.in/nicgep/app") is None


def test_next_listing_page_none_when_single_page():
    from scraper.nic_adapter import next_listing_page
    html = '<table><tr><td>1</td><td>Water work</td></tr></table>'
    assert next_listing_page(html, "https://x.gov.in/nicgep/app") is None
