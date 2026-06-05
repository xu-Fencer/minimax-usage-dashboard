from decimal import Decimal

from app.db import get_conn


PER_TOKEN_KINDS = ("chatcompletion", "cache-read", "cache-create")


def list_pricing() -> list[dict]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT model, input_price, output_price, cache_read_price, cache_write_price, call_price "
            "FROM model_pricing ORDER BY model"
        )
        return [dict(r) for r in cur.fetchall()]


def upsert_pricing(model: str,
                   input_price: float, output_price: float,
                   cache_read_price: float, cache_write_price: float,
                   call_price: float = 0) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO model_pricing
               (model, input_price, output_price, cache_read_price, cache_write_price, call_price)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(model) DO UPDATE SET
                 input_price=excluded.input_price,
                 output_price=excluded.output_price,
                 cache_read_price=excluded.cache_read_price,
                 cache_write_price=excluded.cache_write_price,
                 call_price=excluded.call_price,
                 updated_at=CURRENT_TIMESTAMP""",
            (model, input_price, output_price, cache_read_price, cache_write_price, call_price),
        )


def sync_pricing_from_data() -> int:
    with get_conn() as conn:
        cur = conn.execute("SELECT DISTINCT model FROM usage_records")
        models = [r["model"] for r in cur.fetchall()]
        added = 0
        for m in models:
            exists = conn.execute(
                "SELECT 1 FROM model_pricing WHERE model=?", (m,)
            ).fetchone()
            if exists:
                continue
            conn.execute("INSERT INTO model_pricing (model) VALUES (?)", (m,))
            added += 1
    return added


def get_setting(key: str, default: str | None = None) -> str | None:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO settings (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP""",
            (key, value),
        )


def resolve_mode(configured: str) -> str:
    if configured in ("pay_as_you_go", "token_plan"):
        return configured
    with get_conn() as conn:
        row = conn.execute("SELECT COALESCE(SUM(cost), 0) AS s FROM usage_records").fetchone()
    return "token_plan" if (row["s"] or 0) == 0 else "pay_as_you_go"


def _is_per_token(ep: str) -> bool:
    return any(ep.startswith(k) for k in PER_TOKEN_KINDS)


def estimate_cost(record: dict, pricing: dict[str, dict]) -> float:
    p = pricing.get(record["model"])
    if not p:
        return 0.0
    ep = record["endpoint"]
    in_t = record.get("input_tokens", 0) or 0
    out_t = record.get("output_tokens", 0) or 0

    if _is_per_token(ep):
        if ep.startswith("chatcompletion"):
            raw = in_t * p["input_price"] + out_t * p["output_price"]
        elif ep.startswith("cache-read"):
            raw = in_t * p["cache_read_price"]
        else:  # cache-create and any future per-token kind
            raw = in_t * p["cache_write_price"]
        return float(Decimal(str(raw)) / Decimal("1000000"))
    else:
        # Per-call: input_tokens field is the call count
        call_price = p.get("call_price", 0) or 0
        return float(in_t * call_price)


def estimate_for_records(records: list[dict], pricing: dict[str, dict]) -> float:
    total = Decimal("0")
    for r in records:
        c = estimate_cost(r, pricing)
        if _is_per_token(r["endpoint"]):
            total += Decimal(str(c))
        else:
            total += Decimal(str(c))
    return float(total.quantize(Decimal("0.0001")))


def pricing_dict() -> dict[str, dict]:
    out = {}
    for row in list_pricing():
        out[row["model"]] = row
    return out
