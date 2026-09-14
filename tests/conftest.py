"""Shared pytest fixtures.

Each test gets an isolated SQLite database and temporary data directories, so
tests never touch real data and never depend on any live website.
"""
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

import config
from database.database import Database, set_db


@pytest.fixture
def db(tmp_path, monkeypatch):
    data = tmp_path / "data"
    downloads = data / "downloads"
    reports = data / "reports"
    logs = data / "logs"
    diag = logs / "portal_diagnostics"
    for d in (data, downloads, reports, logs, diag):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "DOWNLOADS_DIR", downloads)
    monkeypatch.setattr(config, "REPORTS_DIR", reports)
    monkeypatch.setattr(config, "LOGS_DIR", logs)
    monkeypatch.setattr(config, "DIAGNOSTICS_DIR", diag)

    database = Database(str(data / "test.db"))
    database.initialize()
    set_db(database)
    yield database
    set_db(None)


@pytest.fixture
def sample_portal(db):
    from services import tender_service as ts
    portal_id = ts.create_portal({
        "name": "Mock Portal",
        "url": "https://mock.example.gov.in/tenders",
        "enabled": "1",
        "schedule_type": "manual",
        "keywords": "water, pipeline, WTP, STP",
        "negative_keywords": "vehicle",
        "download_documents": "0",
        "max_pages": 2,
        "request_delay": 0,
        "browser_mode": "headless",
    })
    return ts.get_portal(portal_id)
