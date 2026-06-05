from app.db import get_conn


def _to_iso(s: str | None) -> str | None:
    if s is None:
        return None
    return s.replace(" ", "T")


def _hit_rate(chat_input: int, cache_read: int) -> float:
    denom = chat_input + cache_read
    if denom <= 0:
        return 0.0
    return round(cache_read * 100.0 / denom, 2)


def summary() -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT
                COUNT(*) AS total_buckets,
                COALESCE(SUM(cost), 0) AS actual_cost,
                COALESCE(SUM(cost_after_voucher), 0) AS cost_after_voucher,
                COALESCE(SUM(CASE WHEN endpoint LIKE 'chatcompletion%' THEN input_tokens ELSE 0 END), 0) AS total_input,
                COALESCE(SUM(output_tokens), 0) AS total_output,
                COALESCE(SUM(CASE WHEN endpoint LIKE 'cache-read%' THEN input_tokens ELSE 0 END), 0) AS total_cache_read,
                COALESCE(SUM(CASE WHEN endpoint LIKE 'cache-create%' THEN input_tokens ELSE 0 END), 0) AS total_cache_create,
                MIN(bucket_start) AS earliest,
                MAX(bucket_start) AS latest
            FROM usage_records"""
        ).fetchone()
    chat_input = int(row["total_input"] or 0)
    cache_read = int(row["total_cache_read"] or 0)
    return {
        "total_buckets": row["total_buckets"] or 0,
        "actual_cost": float(row["actual_cost"] or 0),
        "cost_after_voucher": float(row["cost_after_voucher"] or 0),
        "total_input": chat_input,
        "total_output": int(row["total_output"] or 0),
        "total_cache_read": cache_read,
        "total_cache_create": int(row["total_cache_create"] or 0),
        "cache_hit_rate": _hit_rate(chat_input, cache_read),
        "earliest": _to_iso(row["earliest"]),
        "latest": _to_iso(row["latest"]),
    }


def daily_series() -> list[dict]:
    with get_conn() as conn:
        cur = conn.execute(
            """SELECT
                DATE(bucket_start) AS day,
                SUM(CASE WHEN endpoint LIKE 'chatcompletion%' THEN input_tokens ELSE 0 END) AS input_tokens,
                SUM(CASE WHEN endpoint LIKE 'chatcompletion%' THEN output_tokens ELSE 0 END) AS output_tokens,
                SUM(CASE WHEN endpoint LIKE 'cache-read%' THEN input_tokens ELSE 0 END) AS cache_read_tokens,
                SUM(CASE WHEN endpoint LIKE 'cache-create%' THEN input_tokens ELSE 0 END) AS cache_create_tokens,
                SUM(total_tokens) AS total_tokens,
                SUM(cost) AS actual_cost
            FROM usage_records
            GROUP BY DATE(bucket_start)
            ORDER BY day"""
        )
        rows = []
        for r in cur.fetchall():
            inp = int(r["input_tokens"] or 0)
            cr = int(r["cache_read_tokens"] or 0)
            rows.append({
                "day": r["day"],
                "input_tokens": inp,
                "output_tokens": int(r["output_tokens"] or 0),
                "cache_read_tokens": cr,
                "cache_create_tokens": int(r["cache_create_tokens"] or 0),
                "total_tokens": int(r["total_tokens"] or 0),
                "actual_cost": float(r["actual_cost"] or 0),
                "cache_hit_rate": _hit_rate(inp, cr),
            })
        return rows


def by_model() -> list[dict]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT model, SUM(total_tokens) AS tokens FROM usage_records "
            "GROUP BY model ORDER BY tokens DESC"
        )
        return [{"model": r["model"], "tokens": int(r["tokens"] or 0)} for r in cur.fetchall()]


def by_endpoint() -> list[dict]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT endpoint, SUM(total_tokens) AS tokens FROM usage_records "
            "GROUP BY endpoint ORDER BY tokens DESC"
        )
        return [{"endpoint": r["endpoint"], "tokens": int(r["tokens"] or 0)} for r in cur.fetchall()]


def heatmap() -> list[dict]:
    with get_conn() as conn:
        cur = conn.execute(
            """SELECT
                CAST(strftime('%w', bucket_start) AS INTEGER) AS dow,
                CAST(strftime('%H', bucket_start) AS INTEGER) AS hour,
                SUM(total_tokens) AS tokens
            FROM usage_records
            GROUP BY dow, hour
            ORDER BY dow, hour"""
        )
        return [
            {"dow": r["dow"], "hour": r["hour"], "tokens": int(r["tokens"] or 0)}
            for r in cur.fetchall()
        ]


def year_heatmap() -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            """SELECT
                DATE(bucket_start) AS day,
                SUM(total_tokens) AS tokens
            FROM usage_records
            GROUP BY DATE(bucket_start)
            ORDER BY day"""
        )
        rows = [{"day": r["day"], "tokens": int(r["tokens"] or 0)} for r in cur.fetchall()]
    if not rows:
        return {"range": None, "data": []}
    return {"range": [rows[0]["day"], rows[-1]["day"]], "data": rows}


def paged_records(page: int = 1, size: int = 50,
                  model: str | None = None, endpoint: str | None = None,
                  date_from: str | None = None, date_to: str | None = None) -> dict:
    where = []
    args: list = []
    if model:
        where.append("model = ?")
        args.append(model)
    if endpoint:
        where.append("endpoint = ?")
        args.append(endpoint)
    if date_from:
        where.append("DATE(bucket_start) >= ?")
        args.append(date_from)
    if date_to:
        where.append("DATE(bucket_start) <= ?")
        args.append(date_to)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    with get_conn() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS n FROM usage_records{where_sql}", args).fetchone()["n"]
        offset = (page - 1) * size
        cur = conn.execute(
            f"""SELECT bucket_start, account, api_key_name, endpoint, model,
                       input_tokens, output_tokens, total_tokens, cost
                FROM usage_records{where_sql}
                ORDER BY bucket_start DESC
                LIMIT ? OFFSET ?""",
            args + [size, offset],
        )
        rows = [dict(r) for r in cur.fetchall()]
    return {"total": total, "page": page, "size": size, "rows": rows}


def list_records() -> list[dict]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT bucket_start, account, api_key_name, endpoint, model, "
            "input_tokens, output_tokens, total_tokens, cost "
            "FROM usage_records ORDER BY bucket_start"
        )
        return [dict(r) for r in cur.fetchall()]
