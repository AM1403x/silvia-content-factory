"""
Initialize the SQLite database from schema.sql.
"""

import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH, DB_DIR


def init_database(db_path=None):
    """Create the database and tables from schema.sql."""
    db_path = db_path or DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_file = Path(__file__).parent / "schema.sql"
    schema_sql = schema_file.read_text()

    conn = sqlite3.connect(str(db_path))
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path}")
    return db_path


def get_connection(db_path=None):
    """Return a connection to the database."""
    db_path = db_path or DB_PATH
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


if __name__ == "__main__":
    init_database()
