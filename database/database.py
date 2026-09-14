"""SQLite access layer.

A thin wrapper around the stdlib ``sqlite3`` module. All writes go through
parameterised statements (never string interpolation) and are serialised with a
lock so the scheduler thread, the scan worker thread and the web server can
share one database file safely. WAL mode keeps readers non-blocking.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager

import config
from database.migrations import apply_migrations


class Database:
    def __init__(self, path=None):
        self.path = str(path or config.DB_PATH)
        self._write_lock = threading.Lock()

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def initialize(self):
        config.ensure_directories()
        conn = self.connect()
        try:
            apply_migrations(conn)
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        """Serialised write transaction. Commits on success, rolls back on error."""
        with self._write_lock:
            conn = self.connect()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def execute(self, sql, params=()):
        with self.transaction() as conn:
            cur = conn.execute(sql, params)
            return cur.lastrowid

    def executemany(self, sql, seq_of_params):
        with self.transaction() as conn:
            conn.executemany(sql, seq_of_params)

    def query_all(self, sql, params=()):
        conn = self.connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def query_one(self, sql, params=()):
        conn = self.connect()
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row is not None else None
        finally:
            conn.close()

    def scalar(self, sql, params=()):
        conn = self.connect()
        try:
            row = conn.execute(sql, params).fetchone()
            return row[0] if row is not None else None
        finally:
            conn.close()


_DB = None


def get_db():
    """Return the shared Database singleton (initialised on first use)."""
    global _DB
    if _DB is None:
        _DB = Database()
        _DB.initialize()
    return _DB


def set_db(db):
    """Override the singleton (used by the test-suite)."""
    global _DB
    _DB = db
