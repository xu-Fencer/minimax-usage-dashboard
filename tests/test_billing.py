from app.services.billing import (
    list_pricing, upsert_pricing, sync_pricing_from_data,
    resolve_mode, estimate_cost, estimate_for_records,
)


def test_upsert_and_list(isolated_db):
    upsert_pricing("M2.7", 2.1, 8.4, 0.42, 2.625)
    upsert_pricing("M3-512k", 4.2, 16.8, 0.84, 0)
    items = list_pricing()
    assert len(items) == 2
    m27 = next(i for i in items if i["model"] == "M2.7")
    assert m27["input_price"] == 2.1
    assert m27["cache_read_price"] == 0.42


def test_upsert_updates_existing(isolated_db):
    upsert_pricing("M", 1.0, 2.0, 0.5, 1.5)
    upsert_pricing("M", 1.5, 2.5, 0.6, 1.6)
    items = list_pricing()
    assert len(items) == 1
    assert items[0]["input_price"] == 1.5


def test_sync_pricing_from_data(isolated_db):
    from app.db import get_conn
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO usage_records (account, api_key_name, endpoint, model, cost, cost_after_voucher, input_tokens, output_tokens, total_tokens, bucket_start, result) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [("主", "k", "chatcompletion-v2", "M1", 0, 0, 1, 1, 2, "2026-05-04 19:00:00", "SUCCESS"),
             ("主", "k", "cache-read", "M1", 0, 0, 1, 0, 1, "2026-05-04 20:00:00", "SUCCESS"),
             ("主", "k", "chatcompletion-v2", "M2", 0, 0, 1, 1, 2, "2026-05-05 10:00:00", "SUCCESS")],
        )
    added = sync_pricing_from_data()
    assert added == 2
    items = list_pricing()
    assert {i["model"] for i in items} == {"M1", "M2"}


def test_sync_pricing_idempotent(isolated_db):
    from app.db import get_conn
    with get_conn() as conn:
        conn.execute("INSERT INTO usage_records (account, api_key_name, endpoint, model, cost, cost_after_voucher, input_tokens, output_tokens, total_tokens, bucket_start, result) VALUES ('a','b','c','M',0,0,1,1,2,'2026-05-04 19:00:00','SUCCESS')")
    assert sync_pricing_from_data() == 1
    assert sync_pricing_from_data() == 0


def test_resolve_mode_pay_as_you_go(isolated_db):
    from app.db import get_conn
    with get_conn() as conn:
        conn.execute("INSERT INTO usage_records (account, api_key_name, endpoint, model, cost, cost_after_voucher, input_tokens, output_tokens, total_tokens, bucket_start, result) VALUES ('a','b','c','d',1.5,1.5,1,1,2,'2026-05-04 19:00:00','SUCCESS')")
    assert resolve_mode("auto") == "pay_as_you_go"


def test_resolve_mode_token_plan(isolated_db):
    from app.db import get_conn
    with get_conn() as conn:
        conn.execute("INSERT INTO usage_records (account, api_key_name, endpoint, model, cost, cost_after_voucher, input_tokens, output_tokens, total_tokens, bucket_start, result) VALUES ('a','b','c','d',0,0,1,1,2,'2026-05-04 19:00:00','SUCCESS')")
    assert resolve_mode("auto") == "token_plan"


def test_estimate_cost_chatcompletion():
    pricing = {"M": {"input_price": 2.1, "output_price": 8.4, "cache_read_price": 0, "cache_write_price": 0}}
    rec = {"model": "M", "endpoint": "chatcompletion-v2", "input_tokens": 1_000_000, "output_tokens": 100_000}
    # (1M * 2.1 + 100k * 8.4) / 1M = 2.1 + 0.84 = 2.94
    assert abs(estimate_cost(rec, pricing) - 2.94) < 1e-9


def test_estimate_cost_cache_read():
    pricing = {"M": {"input_price": 2.1, "output_price": 8.4, "cache_read_price": 0.42, "cache_write_price": 0}}
    rec = {"model": "M", "endpoint": "cache-read", "input_tokens": 1_000_000, "output_tokens": 0}
    assert estimate_cost(rec, pricing) == 0.42


def test_estimate_cost_cache_create():
    pricing = {"M": {"input_price": 2.1, "output_price": 8.4, "cache_read_price": 0.42, "cache_write_price": 2.625}}
    rec = {"model": "M", "endpoint": "cache-create", "input_tokens": 1_000_000, "output_tokens": 0}
    assert estimate_cost(rec, pricing) == 2.625


def test_estimate_cost_unconfigured():
    rec = {"model": "M", "endpoint": "x", "input_tokens": 100, "output_tokens": 0}
    assert estimate_cost(rec, {}) == 0.0


def test_estimate_for_records_sum():
    pricing = {"M": {"input_price": 2.1, "output_price": 8.4, "cache_read_price": 0, "cache_write_price": 0}}
    recs = [
        {"model": "M", "endpoint": "chatcompletion-v2", "input_tokens": 1_000_000, "output_tokens": 0},
        {"model": "M", "endpoint": "chatcompletion-v2", "input_tokens": 0, "output_tokens": 100_000},
    ]
    assert abs(estimate_for_records(recs, pricing) - 2.94) < 1e-9
