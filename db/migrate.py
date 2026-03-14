"""Simple SQL migration runner for Popcorn.

Reads .sql files from db/migrations/ in sorted order,
tracks applied migrations in schema_migrations table.
"""

import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), 'migrations')


def apply_migrations(db_path):
    """Apply any pending SQL migrations."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        applied = {row[0] for row in conn.execute(
            "SELECT filename FROM schema_migrations"
        ).fetchall()}

        if not os.path.isdir(MIGRATIONS_DIR):
            return

        for filename in sorted(os.listdir(MIGRATIONS_DIR)):
            if not filename.endswith('.sql') or filename in applied:
                continue
            filepath = os.path.join(MIGRATIONS_DIR, filename)
            with open(filepath) as f:
                sql = f.read()
            try:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (?)",
                    (filename,)
                )
                conn.commit()
                logger.info(f"Migration applied: {filename}")
            except Exception as e:
                logger.error(f"Migration failed: {filename} - {e}")
                raise
    finally:
        conn.close()
