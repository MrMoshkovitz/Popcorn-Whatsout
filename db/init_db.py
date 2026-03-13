import os
import sqlite3


def get_connection(db_path=None):
    """Get a database connection with row_factory set."""
    if db_path is None:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from config import DB_PATH
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=None):
    """Initialize database from schema.sql."""
    conn = get_connection(db_path)
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.close()


if __name__ == '__main__':
    init_db()
    print('Database initialized.')
