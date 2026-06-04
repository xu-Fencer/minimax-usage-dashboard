from app.services.billing import (
    list_pricing, upsert_pricing, sync_pricing_from_data,
    resolve_mode, estimate_cost, estimate_for_records,
)


def test_upsert_and_list(isolated_db):
    upsert_pricing("M", "chatcompletion-v2", 0.001, 0.002, 0, 0)
    upsert_pricing("M", "cache-read", 0, 0, 0.0005, 0)
    items = list_pricing()
    assert len(items) == 2
    chat = next(i for i in items if i["endpoint"] == "chatcompletion-v2")
    assert chat["input_price"] == 0.001


def test_sync_pricing_from_data(isolated_db):
    from app.db import get_conn
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO usage_records (account, api_key_name, endpoint, model, cost, cost_after_voucher, input_tokens, output_tokens, total_tokens, bucket_start, result) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [("主", "k", "chatcompletion-v2", "M1", 0, 0, 1, 1, 2, "2026-05-04 19:00:00", "SUCCESS"),
             ("主", "k", "cache-read", "M1", 0, 0, 1, 0, 1, "2026-05-04 20:00:00", "SUCCESS")],
        )
    added = sync_pricing_from_data()
    assert added == 2
    items = list_pricing()
    assert {(i["model"], i["endpoint"]) for i in items} == {("M1", "chatcompletion-v2"), ("M1", "cache-read")}


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
    pricing = {("M", "chatcompletion-v2"): {"input_price": 0.001, "output_price": 0.002, "cache_read_price": 0, "cache_write_price": 0}}
    rec = {"model": "M", "endpoint": "chatcompletion-v2", "input_tokens": 1000, "output_tokens": 500}
    assert estimate_cost(rec, pricing) == 0.002


def test_estimate_cost_cache_read():
    pricing = {("M", "cache-read"): {"input_price": 0, "output_price": 0, "cache_read_price": 0.0005, "cache_write_price": 0}}
    rec = {"model": "M", "endpoint": "cache-read", "input_tokens": 2000, "output_tokens": 0}
    assert estimate_cost(rec, pricing) == 0.001


def test_estimate_cost_cache_create():
    pricing = {("M", "cache-create"): {"input_price": 0, "output_price": 0, "cache_read_price": 0, "cache_write_price": 0.001}}
    rec = {"model": "M", "endpoint": "cache-create", "input_tokens": 500, "output_tokens": 0}
    assert estimate_cost(rec, pricing) == 0.0005


def test_estimate_cost_unconfigured():
    rec = {"model": "M", "endpoint": "x", "input_tokens": 100, "output_tokens": 0}
    assert estimate_cost(rec, {}) == 0.0


def test_estimate_for_records_sum():
    pricing = {("M", "chatcompletion-v2"): {"input_price": 0.001, "output_price": 0.002, "cache_read_price": 0, "cache_write_price": 0}}
    recs = [
        {"model": "M", "endpoint": "chatcompletion-v2", "input_tokens": 1000, "output_tokens": 0},
        {"model": "M", "endpoint": "chatcompletion-v2", "input_tokens": 0, "output_tokens": 500},
    ]
    assert estimate_for_records(recs, pricing) == 0.002
