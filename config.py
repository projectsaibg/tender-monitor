"""Central configuration for Tender Monitor.

All values here are safe technical defaults. User-facing configuration
(portals, schedules, keywords, SMTP credentials, timezone) is stored in the
SQLite database and edited through the UI, NOT here. Optional overrides may be
supplied through environment variables or a local ``.env`` file.

Nothing secret is ever hard-coded in this file.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dotenv is a hard dependency but stay safe
    def load_dotenv(*_a, **_k):  # type: ignore
        return False

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent

# Load an optional .env sitting next to this file.
load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    return _env(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


# Allow relocating the whole data directory (useful for Task Scheduler / testing).
DATA_DIR = Path(_env("TENDER_MONITOR_DATA_DIR", str(BASE_DIR / "data"))).resolve()
DB_PATH = Path(_env("TENDER_MONITOR_DB", str(DATA_DIR / "tender_monitor.db"))).resolve()
DOWNLOADS_DIR = DATA_DIR / "downloads"
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = DATA_DIR / "logs"
DIAGNOSTICS_DIR = LOGS_DIR / "portal_diagnostics"

TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# --------------------------------------------------------------------------- #
# Server
# --------------------------------------------------------------------------- #
APP_HOST = _env("TENDER_MONITOR_HOST", "127.0.0.1")
APP_PORT = _env_int("TENDER_MONITOR_PORT", 8000)
APP_TITLE = "Tender Monitor"
APP_VERSION = "1.0.0"

# --------------------------------------------------------------------------- #
# Authorship / contact (this is an open-source project)
# --------------------------------------------------------------------------- #
APP_AUTHOR = "Ganguly B (Shavarna)"
APP_CONTACT_EMAIL = _env("TENDER_MONITOR_CONTACT_EMAIL", "enlaceet@gmail.com")
APP_CONTACT_WHATSAPP = _env("TENDER_MONITOR_CONTACT_WHATSAPP", "+91-9073288770")
APP_REPO_URL = _env("TENDER_MONITOR_REPO_URL", "")
APP_LICENSE = "MIT"

# wa.me link needs digits only (country code + number, no + or dashes).
APP_CONTACT_WHATSAPP_LINK = "https://wa.me/" + "".join(
    ch for ch in APP_CONTACT_WHATSAPP if ch.isdigit())

# URL of a small JSON manifest the author publishes to announce new versions.
# Leave blank to disable update checks. See docs/PUBLISHING_UPDATES.md.
UPDATE_MANIFEST_URL = _env("TENDER_MONITOR_UPDATE_URL", "")

# --------------------------------------------------------------------------- #
# Timezone (default only; the effective value is read from Settings in the DB)
# --------------------------------------------------------------------------- #
DEFAULT_TIMEZONE = _env("TENDER_MONITOR_TIMEZONE", "Asia/Kolkata")

# --------------------------------------------------------------------------- #
# Scraper / safety limits (defaults; per-portal values override these)
# --------------------------------------------------------------------------- #
DEFAULT_MAX_PAGES = _env_int("TENDER_MONITOR_MAX_PAGES", 5)
DEFAULT_REQUEST_DELAY = _env_float("TENDER_MONITOR_REQUEST_DELAY", 2.0)
BROWSER_TIMEOUT_MS = _env_int("TENDER_MONITOR_BROWSER_TIMEOUT_MS", 30000)
DOWNLOAD_TIMEOUT_S = _env_int("TENDER_MONITOR_DOWNLOAD_TIMEOUT", 60)
MAX_DOWNLOAD_BYTES = _env_int("TENDER_MONITOR_MAX_DOWNLOAD_BYTES", 60 * 1024 * 1024)
MAX_DOWNLOADS_PER_SCAN = _env_int("TENDER_MONITOR_MAX_DOWNLOADS_PER_SCAN", 200)
MAX_TENDERS_PER_SCAN = _env_int("TENDER_MONITOR_MAX_TENDERS_PER_SCAN", 3000)
HARD_MAX_PAGES = _env_int("TENDER_MONITOR_HARD_MAX_PAGES", 50)

# NIC eProcurement (GePNIC) adapter: how many organisations to walk per scan,
# and a safety cap on pages per organisation (most orgs list on a single page).
NIC_MAX_ORGS = _env_int("TENDER_MONITOR_NIC_MAX_ORGS", 60)
NIC_MAX_PAGES_PER_ORG = _env_int("TENDER_MONITOR_NIC_MAX_PAGES_PER_ORG", 20)

# --------------------------------------------------------------------------- #
# Security
# --------------------------------------------------------------------------- #
# When False (default) requests to localhost / private / reserved IP ranges are
# blocked to reduce SSRF risk, since the app accepts arbitrary user URLs.
ALLOW_PRIVATE_HOSTS = _env_bool("TENDER_MONITOR_ALLOW_PRIVATE_HOSTS", False)

# --------------------------------------------------------------------------- #
# Safe-scan / structure-change detection
# --------------------------------------------------------------------------- #
# If a scan returns fewer than STRUCTURE_DROP_RATIO * (previous count) tenders,
# and the previous count was at least STRUCTURE_MIN_PREV, the scan is flagged as
# PARTIAL and previous data is preserved rather than treated as authoritative.
STRUCTURE_DROP_RATIO = _env_float("TENDER_MONITOR_STRUCTURE_DROP_RATIO", 0.4)
STRUCTURE_MIN_PREV = _env_int("TENDER_MONITOR_STRUCTURE_MIN_PREV", 20)

USER_AGENT = _env(
    "TENDER_MONITOR_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TenderMonitor/1.0 (+local)",
)


def ensure_directories() -> None:
    """Create all runtime directories. Safe to call repeatedly."""
    for path in (DATA_DIR, DOWNLOADS_DIR, REPORTS_DIR, LOGS_DIR, DIAGNOSTICS_DIR):
        path.mkdir(parents=True, exist_ok=True)
