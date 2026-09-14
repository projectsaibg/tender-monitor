"""Update-notification version comparison and unconfigured behaviour."""
import config
from services import update_service as us


def test_is_newer():
    assert us.is_newer("1.1.0", "1.0.0") is True
    assert us.is_newer("2.0", "1.9.9") is True
    assert us.is_newer("v1.2.0", "1.1.0") is True
    assert us.is_newer("1.0.0", "1.0.0") is False
    assert us.is_newer("1.0.0", "1.1.0") is False


def test_check_not_configured(monkeypatch):
    monkeypatch.setattr(config, "UPDATE_MANIFEST_URL", "")
    us._STATE["checked"] = False
    r = us.check_for_update(force=True)
    assert r["configured"] is False
    assert r["available"] is False
    assert r["current"] == config.APP_VERSION
