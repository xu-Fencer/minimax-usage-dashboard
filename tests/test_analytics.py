from app.services.analytics import (
    summary, daily_series, by_model, by_endpoint, heatmap, year_heatmap, paged_records
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
    assert s["total_input"] == 300  # chat input only (excludes cache-read)
    assert s["total_output"] == 30
    assert s["total_cache_read"] == 500
    assert s["earliest"].startswith("2026-05-04T19:00")


def test_daily_series(isolated_db):
    _seed(isolated_db)
    d = daily_series()
    assert len(d) == 2
    assert d[0]["day"] == "2026-05-04"
    assert d[0]["total_tokens"] == 610


def test_daily_series_splits_four_categories(isolated_db):
    _seed(isolated_db)
    d = daily_series()
    day1 = d[0]
    # day1: M1 chatcompletion-v2 (100 in, 10 out) + M1 cache-read (500 in)
    assert day1["input_tokens"] == 100
    assert day1["output_tokens"] == 10
    assert day1["cache_read_tokens"] == 500
    assert day1["cache_create_tokens"] == 0


def test_daily_series_cache_hit_rate(isolated_db):
    _seed(isolated_db)
    d = daily_series()
    day1 = d[0]
    # day1: 100 chat input + 500 cache read → 500/(500+100) = 83.33%
    assert abs(day1["cache_hit_rate"] - 83.33) < 0.01
    day2 = d[1]
    # day2: 200 chat input + 0 cache read → 0%
    assert day2["cache_hit_rate"] == 0.0


def test_summary_cache_hit_rate(isolated_db):
    _seed(isolated_db)
    s = summary()
    # total: 100+200 chat input + 500 cache read = 500/800 = 62.5%
    assert abs(s["cache_hit_rate"] - 62.5) < 0.01


def test_year_heatmap(isolated_db):
    _seed(isolated_db)
    h = year_heatmap()
    assert h["range"] is not None
    start, end = h["range"]
    # Range starts on Monday and ends on Sunday (full weeks)
    from datetime import date
    sd = date.fromisoformat(start)
    ed = date.fromisoformat(end)
    assert sd.weekday() == 0, "start should be Monday"
    assert ed.weekday() == 6, "end should be Sunday"
    cells = h["cells"]
    # Each cell has week/dow
    for c in cells[:5]:
        assert "date" in c
        assert "month" in c
        assert "day" in c
        assert "dow" in c
        assert "week" in c
        assert "tokens" in c
        assert "level" in c
        assert 0 <= c["dow"] <= 6
        assert 0 <= c["level"] <= 4
    # Day with data has level >= 1
    may4 = next(c for c in cells if c["date"] == "2026-05-04")
    assert may4["tokens"] == 610
    assert may4["level"] >= 1
    assert may4["dow"] == 0  # Monday
    # Empty day in range has level 0 (e.g. Friday 5/8)
    may8 = next(c for c in cells if c["date"] == "2026-05-08")
    assert may8["tokens"] == 0
    assert may8["level"] == 0
    assert may8["dow"] == 4  # Friday
    # Total cells = total days in range
    assert len(cells) == (ed - sd).days + 1


def test_year_heatmap_empty(isolated_db):
    h = year_heatmap()
    assert h["range"] is not None
    start, end = h["range"]
    from datetime import date
    sd = date.fromisoformat(start)
    ed = date.fromisoformat(end)
    assert sd.weekday() == 0
    assert ed.weekday() == 6
    for c in h["cells"]:
        assert c["level"] == 0
        assert c["tokens"] == 0


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
