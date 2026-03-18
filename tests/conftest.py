import pytest
from sqlite_utils import Database


@pytest.fixture
def sample_db(tmp_path):
    """Create a sample database with typed tables for testing."""
    db_path = str(tmp_path / "test.db")
    db = Database(db_path)

    db.execute("""CREATE TABLE repos (
        name TEXT,
        language TEXT,
        stars INTEGER,
        is_archived BOOLEAN,
        created_at DATETIME,
        description TEXT
    )""")
    db["repos"].insert_all([
        {"name": "alpha", "language": "python", "stars": 100,
         "is_archived": 0, "created_at": "2024-01-15", "description": "Alpha project"},
        {"name": "beta", "language": "go", "stars": 50,
         "is_archived": 1, "created_at": "2024-06-01", "description": "Beta project"},
        {"name": "gamma", "language": "python", "stars": 200,
         "is_archived": 0, "created_at": "2025-03-10", "description": None},
        {"name": "delta", "language": "rust", "stars": 75,
         "is_archived": 0, "created_at": "2025-11-20", "description": "Delta tools"},
    ])

    db.execute("""CREATE TABLE events (
        repo_name TEXT,
        event_type TEXT,
        timestamp DATETIME
    )""")
    db["events"].insert_all([
        {"repo_name": "alpha", "event_type": "push", "timestamp": "2026-03-15T10:00:00"},
        {"repo_name": "alpha", "event_type": "release", "timestamp": "2026-03-01T14:00:00"},
        {"repo_name": "beta", "event_type": "push", "timestamp": "2026-03-10T09:30:00"},
    ])

    db.execute("""CREATE VIEW active_repos AS
        SELECT * FROM repos WHERE is_archived = 0
    """)

    # Table with reserved column names and invalid flag names for edge case testing
    db.execute("""CREATE TABLE edge_cases (
        id INTEGER,
        format TEXT,
        name TEXT
    )""")
    db["edge_cases"].insert_all([
        {"id": 1, "format": "json", "name": "test"},
    ])

    return db_path


@pytest.fixture
def sample_db_with_fts(sample_db):
    """Extend sample_db with FTS index on repos.description."""
    db = Database(sample_db)
    db["repos"].enable_fts(["name", "description"], create_triggers=True)
    return sample_db
