import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import DB_PATH as _DEFAULT_DB_PATH

DB_PATH: Path = _DEFAULT_DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account TEXT NOT NULL,
    api_key_name TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    model TEXT NOT NULL,
    cost REAL NOT NULL DEFAULT 0,
    cost_after_voucher REAL NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    bucket_start DATETIME NOT NULL,
    result TEXT NOT NULL DEFAULT 'SUCCESS',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_record_unique
    ON usage_records(account, api_key_name, endpoint, model, bucket_start, result);

CREATE INDEX IF NOT EXISTS idx_bucket_start ON usage_records(bucket_start);
CREATE INDEX IF NOT EXISTS idx_model ON usage_records(model);
CREATE INDEX IF NOT EXISTS idx_endpoint ON usage_records(endpoint);

CREATE TABLE IF NOT EXISTS import_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    total_rows INTEGER NOT NULL,
    inserted_rows INTEGER NOT NULL,
    skipped_rows INTEGER NOT NULL,
    error_rows INTEGER NOT NULL,
    error_detail TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_pricing (
    model TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    input_price REAL NOT NULL DEFAULT 0,
    output_price REAL NOT NULL DEFAULT 0,
    cache_read_price REAL NOT NULL DEFAULT 0,
    cache_write_price REAL NOT NULL DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (model, endpoint)
);
"""


def init_db(path: Path | None = None) -> None:
    target = path or DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def get_conn(path: Path | None = None):
    target = path or DB_PATH
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
