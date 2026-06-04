def test_init_db_creates_all_tables(isolated_db):
    import sqlite3
    from app.db import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()
    assert "usage_records" in tables
    assert "import_history" in tables
    assert "settings" in tables
    assert "model_pricing" in tables
