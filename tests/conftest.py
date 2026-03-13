import os
import sys
import sqlite3
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def db_conn():
    """In-memory SQLite with schema applied."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'db', 'schema.sql')
    with open(schema_path) as f:
        conn.executescript(f.read())
    yield conn
    conn.close()


@pytest.fixture
def sample_csv_path():
    return os.path.join(os.path.dirname(__file__), 'fixtures', 'sample_netflix.csv')
