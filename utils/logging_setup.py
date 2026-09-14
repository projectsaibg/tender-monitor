"""Rotating logging configuration for Tender Monitor.

Provides three named loggers writing to data/logs/:
  * app.log      - general application events
  * scanner.log  - scan / scraper activity
  * errors.log   - warnings and errors (from any logger)

Passwords and other secrets must never be written to logs.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

import config

_CONFIGURED = False
_MAX_BYTES = 2 * 1024 * 1024
_BACKUPS = 5
_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(console: bool = False) -> None:
    """Configure the logging hierarchy. Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    config.ensure_directories()

    formatter = logging.Formatter(_FORMAT)

    app_logger = logging.getLogger("tender_monitor")
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False

    app_handler = RotatingFileHandler(
        config.LOGS_DIR / "app.log", maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
    )
    app_handler.setFormatter(formatter)
    app_handler.setLevel(logging.INFO)
    app_logger.addHandler(app_handler)

    scanner_logger = logging.getLogger("tender_monitor.scanner")
    scanner_logger.setLevel(logging.INFO)
    scanner_logger.propagate = True
    scanner_handler = RotatingFileHandler(
        config.LOGS_DIR / "scanner.log", maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
    )
    scanner_handler.setFormatter(formatter)
    scanner_handler.setLevel(logging.INFO)
    scanner_logger.addHandler(scanner_handler)

    error_handler = RotatingFileHandler(
        config.LOGS_DIR / "errors.log", maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.WARNING)
    app_logger.addHandler(error_handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        app_logger.addHandler(console_handler)

    _CONFIGURED = True


def get_logger(name: str = "tender_monitor") -> logging.Logger:
    """Return a logger inside the tender_monitor hierarchy."""
    if not _CONFIGURED:
        setup_logging()
    if name == "tender_monitor" or name.startswith("tender_monitor."):
        return logging.getLogger(name)
    return logging.getLogger(f"tender_monitor.{name}")
