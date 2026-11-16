import sqlite3

# Shared connection helpers. Each domain owns its own SCHEMA string
# (specs/store.py, samples/store.py); app.py passes both to init_db.

# 
def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path, schemas):
    """
    Initialize each domain's schema
    """
    conn = get_connection(db_path)
    try:
        for schema in schemas:
            conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()