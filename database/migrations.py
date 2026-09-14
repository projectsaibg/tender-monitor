"""Schema definition and migrations for the SQLite database.

Migrations are applied in order and tracked with PRAGMA user_version.
Append a new (version, statements) entry to evolve the schema; existing
databases upgrade automatically on next start.
"""
from __future__ import annotations

MIGRATIONS = [
    (
        1,
        [
            """
            CREATE TABLE IF NOT EXISTS portals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                schedule_type TEXT NOT NULL DEFAULT 'manual',
                run_time TEXT NOT NULL DEFAULT '07:00',
                day_of_week INTEGER,
                keywords TEXT NOT NULL DEFAULT '[]',
                negative_keywords TEXT NOT NULL DEFAULT '[]',
                keyword_mode TEXT NOT NULL DEFAULT 'any',
                location TEXT DEFAULT '',
                min_value REAL,
                max_value REAL,
                download_documents INTEGER NOT NULL DEFAULT 1,
                max_pages INTEGER NOT NULL DEFAULT 5,
                request_delay REAL NOT NULL DEFAULT 2.0,
                browser_mode TEXT NOT NULL DEFAULT 'headless',
                adapter TEXT NOT NULL DEFAULT 'generic',
                treat_first_scan_as_new INTEGER NOT NULL DEFAULT 0,
                config_json TEXT NOT NULL DEFAULT '{}',
                health TEXT NOT NULL DEFAULT 'unknown',
                last_status TEXT DEFAULT '',
                last_scan_at TEXT,
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tenders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portal_id INTEGER NOT NULL,
                portal_name TEXT DEFAULT '',
                source_url TEXT DEFAULT '',
                tender_id TEXT DEFAULT '',
                tender_reference TEXT DEFAULT '',
                tender_title TEXT DEFAULT '',
                organisation TEXT DEFAULT '',
                department TEXT DEFAULT '',
                tender_category TEXT DEFAULT '',
                product_category TEXT DEFAULT '',
                tender_type TEXT DEFAULT '',
                location TEXT DEFAULT '',
                published_date TEXT DEFAULT '',
                bid_submission_start TEXT DEFAULT '',
                bid_submission_end TEXT DEFAULT '',
                opening_date TEXT DEFAULT '',
                estimated_value REAL,
                estimated_value_text TEXT DEFAULT '',
                emd TEXT DEFAULT '',
                tender_fee TEXT DEFAULT '',
                work_period TEXT DEFAULT '',
                eligibility TEXT DEFAULT '',
                tender_detail_url TEXT DEFAULT '',
                document_urls TEXT NOT NULL DEFAULT '[]',
                extra_fields TEXT NOT NULL DEFAULT '{}',
                relevance_score INTEGER DEFAULT 0,
                relevance_band TEXT DEFAULT 'LOW',
                matched INTEGER NOT NULL DEFAULT 1,
                fingerprint TEXT DEFAULT '',
                unique_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'existing',
                scraped_at TEXT DEFAULT '',
                first_seen_at TEXT DEFAULT '',
                last_seen_at TEXT DEFAULT '',
                FOREIGN KEY (portal_id) REFERENCES portals (id) ON DELETE CASCADE,
                UNIQUE (portal_id, unique_key)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tender_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tender_id INTEGER NOT NULL,
                scan_id INTEGER,
                changed_at TEXT NOT NULL DEFAULT '',
                field TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                change_type TEXT DEFAULT 'FIELD CHANGED',
                FOREIGN KEY (tender_id) REFERENCES tenders (id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tender_id INTEGER NOT NULL,
                portal_id INTEGER,
                document_name TEXT DEFAULT '',
                document_url TEXT NOT NULL,
                local_path TEXT DEFAULT '',
                file_size INTEGER DEFAULT 0,
                sha256 TEXT DEFAULT '',
                content_type TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                downloaded_at TEXT DEFAULT '',
                FOREIGN KEY (tender_id) REFERENCES tenders (id) ON DELETE CASCADE,
                UNIQUE (tender_id, document_url)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portal_id INTEGER,
                portal_name TEXT DEFAULT '',
                started_at TEXT NOT NULL DEFAULT '',
                finished_at TEXT DEFAULT '',
                duration_seconds REAL DEFAULT 0,
                pages_processed INTEGER DEFAULT 0,
                tenders_found INTEGER DEFAULT 0,
                new_count INTEGER DEFAULT 0,
                updated_count INTEGER DEFAULT 0,
                existing_count INTEGER DEFAULT 0,
                documents_downloaded INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'running',
                trigger TEXT DEFAULT 'manual',
                notes TEXT DEFAULT ''
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS scan_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER,
                portal_id INTEGER,
                portal_name TEXT DEFAULT '',
                occurred_at TEXT NOT NULL DEFAULT '',
                error_type TEXT DEFAULT 'error',
                message TEXT DEFAULT '',
                detail TEXT DEFAULT ''
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT '',
                level TEXT NOT NULL DEFAULT 'info',
                title TEXT DEFAULT '',
                message TEXT DEFAULT '',
                read INTEGER NOT NULL DEFAULT 0,
                sent INTEGER NOT NULL DEFAULT 0
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_tenders_portal ON tenders (portal_id)",
            "CREATE INDEX IF NOT EXISTS idx_tenders_status ON tenders (status)",
            "CREATE INDEX IF NOT EXISTS idx_tenders_unique ON tenders (portal_id, unique_key)",
            "CREATE INDEX IF NOT EXISTS idx_tenders_fingerprint ON tenders (fingerprint)",
            "CREATE INDEX IF NOT EXISTS idx_versions_tender ON tender_versions (tender_id)",
            "CREATE INDEX IF NOT EXISTS idx_documents_tender ON documents (tender_id)",
            "CREATE INDEX IF NOT EXISTS idx_scans_portal ON scans (portal_id)",
            "CREATE INDEX IF NOT EXISTS idx_errors_scan ON scan_errors (scan_id)",
        ],
    ),
    (
        2,
        [
            "ALTER TABLE tenders ADD COLUMN archived INTEGER NOT NULL DEFAULT 0",
            "CREATE INDEX IF NOT EXISTS idx_tenders_archived ON tenders (archived)",
        ],
    ),
]

LATEST_VERSION = MIGRATIONS[-1][0]


def apply_migrations(conn):
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, statements in MIGRATIONS:
        if version > current:
            for stmt in statements:
                conn.execute(stmt)
            conn.execute("PRAGMA user_version = " + str(version))
            current = version
    conn.commit()
    return current
