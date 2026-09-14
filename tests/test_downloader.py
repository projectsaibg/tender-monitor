"""Downloader safety checks (offline - no network requests are made)."""
from scraper import downloader


def test_blocks_executable_before_network(tmp_path):
    # .exe on a public host: rejected by the extension policy, so no request.
    res = downloader.download_document("http://8.8.8.8/malware.exe", str(tmp_path))
    assert res["status"] == "blocked"


def test_blocks_private_host(tmp_path):
    res = downloader.download_document("http://127.0.0.1/doc.pdf", str(tmp_path))
    assert res["status"] == "blocked"
    assert "blocked" in res["error"].lower() or "private" in res["error"].lower()


def test_blocks_file_scheme(tmp_path):
    res = downloader.download_document("file:///etc/passwd", str(tmp_path))
    assert res["status"] == "blocked"
