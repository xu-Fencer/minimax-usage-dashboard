from app.services.analytics import (
    summary, daily_series, by_model, by_endpoint, heatmap, paged_records
)
from app.db import get_conn


def _seed(isolated_db):
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO usage_records (account, api_key_name, endpoint, model, cost, cost_after_voucher, input_tokens, output_tokens, total_tokens, bucket_start, result) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                ("a", "k", "chatcompletion-v2", "M1", 0, 0, 100, 10, 110, "2026-05-04 19:00:00", "SUCCESS"),
                ("a", "k", "cache-read", "M1", 0, 0, 500, 0, 500, "2026-05-04 19:00:00", "SUCCESS"),
                ("a", "k", "chatcompletion-v2", "M2", 0, 0, 200, 20, 220, "2026-05-05 10:00:00", "SUCCESS"),
            ],
        )


def test_summary(isolated_db):
    _seed(isolated_db)
    s = summary()
    assert s["total_buckets"] == 3
    assert s["total_input"] == 800
    assert s["total_output"] == 30
    assert s["earliest"].startswith("2026-05-04T19:00")


def test_daily_series(isolated_db):
    _seed(isolated_db)
    d = daily_series()
    assert len(d) == 2
    assert d[0]["day"] == "2026-05-04"
    assert d[0]["total_tokens"] == 610


def test_by_model(isolated_db):
    _seed(isolated_db)
    m = by_model()
    assert m[0]["model"] == "M1"
    assert m[0]["tokens"] == 610


def test_by_endpoint(isolated_db):
    _seed(isolated_db)
    e = by_endpoint()
    assert e[0]["endpoint"] == "cache-read"
    assert e[0]["tokens"] == 500


def test_heatmap(isolated_db):
    _seed(isolated_db)
    h = heatmap()
    assert isinstance(h, list)
    assert any(cell["hour"] == 19 for cell in h)


def test_paged_records(isolated_db):
    _seed(isolated_db)
    page = paged_records(page=1, size=2)
    assert page["total"] == 3
    assert len(page["rows"]) == 2
