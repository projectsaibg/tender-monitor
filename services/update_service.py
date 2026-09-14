"""Update-notification service.

The author publishes a small JSON manifest at a stable URL
(config.UPDATE_MANIFEST_URL). On start-up and on demand the app fetches it and,
if a newer version is available, shows a banner with release notes and a
download link. This lets the maintainer notify every user from one place.

Example manifest (see docs/update-manifest.example.json):
  { "latest_version": "1.1.0",
    "download_url": "https://github.com/<you>/tender-monitor/releases",
    "notes": "New: closing-soon alerts. Fixed: Odisha portal parsing.",
    "message": "Please update when convenient." }
"""
from __future__ import annotations

import threading

import httpx

import config
from utils import security
from utils.logging_setup import get_logger

log = get_logger("app")

_STATE = {
    "checked": False, "configured": False, "available": False,
    "current": config.APP_VERSION, "latest": "", "notes": "", "url": "",
    "message": "", "error": "",
}
_LOCK = threading.Lock()


def _parse_version(value):
    parts = []
    for chunk in str(value or "").strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def is_newer(latest, current):
    return _parse_version(latest) > _parse_version(current)


def state():
    return dict(_STATE)


def check_for_update(force=False):
    with _LOCK:
        if _STATE["checked"] and not force:
            return dict(_STATE)
        url = (config.UPDATE_MANIFEST_URL or "").strip()
        _STATE.update({"checked": True, "current": config.APP_VERSION,
                       "configured": bool(url), "error": ""})
        if not url:
            _STATE.update({"available": False, "error": "Update checking is not configured"})
            return dict(_STATE)
        try:
            security.validate_url(url)
            headers = {"User-Agent": config.USER_AGENT}
            with httpx.Client(follow_redirects=True, timeout=15, headers=headers) as client:
                data = client.get(url).json()
            latest = str(data.get("latest_version") or data.get("version") or "")
            _STATE.update({
                "latest": latest,
                "notes": str(data.get("notes") or data.get("changelog") or ""),
                "url": str(data.get("download_url") or data.get("url") or config.APP_REPO_URL or ""),
                "message": str(data.get("message") or ""),
                "available": bool(latest and is_newer(latest, config.APP_VERSION)),
                "error": "",
            })
        except Exception as exc:
            _STATE.update({"available": False, "error": str(exc)})
            log.warning("Update check failed: %s", exc)
        return dict(_STATE)


def check_in_background():
    threading.Thread(target=check_for_update, daemon=True).start()
