from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_dashboard_empty(isolated_db):
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["total_buckets"] == 0
    assert data["billing_mode"] == "token_plan"


def test_import_csv(isolated_db, tmp_path):
    csv = "消费账号,接口密钥名称,消费接口,消费模型,消费金额,代金券后消费金额,输入消费数,输出消费数,总消费数,消费时间,消费结果\n主,k,e,M,0,0,1,1,2,2026-05-04 19:00-20:00,SUCCESS\n"
    p = tmp_path / "x.csv"
    p.write_text(csv, encoding="utf-8")
    with open(p, "rb") as f:
        r = client.post("/api/import", files={"file": ("x.csv", f, "text/csv")})
    assert r.status_code == 200
    data = r.json()
    assert data["inserted"] == 1


def test_pricing_crud(isolated_db):
    r = client.put("/api/pricing", json=[
        {"model": "M", "endpoint": "chatcompletion-v2",
         "input_price": 0.001, "output_price": 0.002,
         "cache_read_price": 0, "cache_write_price": 0}
    ])
    assert r.status_code == 200
    r = client.get("/api/pricing")
    assert len(r.json()) == 1


def test_settings(isolated_db):
    r = client.put("/api/settings", json={"billing_mode": "token_plan", "theme": "dark"})
    assert r.status_code == 200
    r = client.get("/api/settings")
    assert r.json()["billing_mode"] == "token_plan"


def test_clear(isolated_db):
    from app.db import get_conn
    with get_conn() as conn:
        conn.execute("INSERT INTO usage_records (account, api_key_name, endpoint, model, cost, cost_after_voucher, input_tokens, output_tokens, total_tokens, bucket_start, result) VALUES ('a','b','c','d',0,0,1,1,2,'2026-05-04 19:00:00','SUCCESS')")
    r = client.post("/api/clear", params={"confirm": "yes"})
    assert r.status_code == 200
    r = client.get("/api/dashboard")
    assert r.json()["summary"]["total_buckets"] == 0
