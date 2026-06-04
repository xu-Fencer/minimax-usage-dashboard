from app.services.importer import import_records
from app.db import get_conn


def test_import_records_inserts_and_dedupes(isolated_db):
    r1 = import_records(
        filename="a.csv",
        file_size=100,
        rows=[
            {"account": "主", "api_key_name": "k", "endpoint": "chatcompletion-v2", "model": "M",
             "cost": 0, "cost_after_voucher": 0, "input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
             "bucket_start": "2026-05-04 19:00:00", "result": "SUCCESS"},
        ],
        errors=[],
    )
    assert r1.inserted == 1
    assert r1.skipped == 0

    r2 = import_records(filename="a.csv", file_size=100, rows=[
            {"account": "主", "api_key_name": "k", "endpoint": "chatcompletion-v2", "model": "M",
             "cost": 0, "cost_after_voucher": 0, "input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
             "bucket_start": "2026-05-04 19:00:00", "result": "SUCCESS"},
        ], errors=[])
    assert r2.inserted == 0
    assert r2.skipped == 1


def test_import_records_writes_history(isolated_db):
    r = import_records(
        filename="x.csv", file_size=200, rows=[
            {"account": "主", "api_key_name": "k", "endpoint": "e", "model": "M",
             "cost": 0.01, "cost_after_voucher": 0.01, "input_tokens": 1, "output_tokens": 0, "total_tokens": 1,
             "bucket_start": "2026-05-05 00:00:00", "result": "SUCCESS"},
        ], errors=[],
    )
    with get_conn() as conn:
        row = conn.execute("SELECT filename, inserted_rows FROM import_history").fetchone()
    assert row["filename"] == "x.csv"
    assert row["inserted_rows"] == 1


def test_import_records_error_rows(isolated_db):
    r = import_records(
        filename="y.csv", file_size=50, rows=[],
        errors=[{"row_no": 2, "reason": "bad time", "raw": {}}],
    )
    assert r.error_rows == 1
    with get_conn() as conn:
        row = conn.execute("SELECT error_rows FROM import_history").fetchone()
    assert row["error_rows"] == 1
