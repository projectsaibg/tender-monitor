"""SSRF-conscious URL validation and filename sanitisation."""
import pytest
from utils import security


def test_scheme_blocking():
    with pytest.raises(security.SecurityError):
        security.validate_url("file:///etc/passwd")
    with pytest.raises(security.SecurityError):
        security.validate_url("ftp://example.com/x")


def test_private_ip_blocking():
    for url in ("http://127.0.0.1/", "http://10.0.0.1/", "http://192.168.1.1/",
                "http://169.254.1.1/", "http://localhost/"):
        with pytest.raises(security.SecurityError):
            security.validate_url(url)


def test_private_allowed_when_flagged():
    assert security.validate_url("http://127.0.0.1:8899/x", allow_private=True)


def test_public_ip_allowed():
    assert security.validate_url("http://8.8.8.8/", allow_private=False)


def test_sanitize_filename():
    assert security.sanitize_filename("../../etc/passwd") == "passwd"
    assert "/" not in security.sanitize_filename("a/b/c.pdf")
    assert "\\" not in security.sanitize_filename(r"a\b\c.pdf")
    assert security.sanitize_filename("") == "file"
    assert security.sanitize_filename("con.txt").startswith("_")


def test_download_extension_policy():
    assert security.download_extension_allowed("nit.pdf") is True
    assert security.download_extension_allowed("doc.docx") is True
    assert security.download_extension_allowed("malware.exe") is False
    assert security.download_extension_allowed("script.js") is False
