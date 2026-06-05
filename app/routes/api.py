import logging
import sys
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.config import MAX_UPLOAD_SIZE
from app.db import get_conn
from app.parser import parse_csv
from app.services.importer import import_records
from app.services import billing, analytics

router = APIRouter(prefix="/api")

_log = logging.getLogger("minimax.import")
_log.setLevel(logging.DEBUG)
if not _log.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("[IMPORT] %(message)s"))
    _log.addHandler(_h)


@router.get("/dashboard")
def dashboard_data():
    s = analytics.summary()
    daily = analytics.daily_series()
    pricing = billing.pricing_dict()
    records = analytics.list_records()
    estimated_total = billing.estimate_for_records(records, pricing)
    by_day: dict[str, dict] = {d["day"]: dict(d, estimated_cost=0.0) for d in daily}
    for r in records:
        day = r["bucket_start"][:10]
        if day in by_day:
            by_day[day]["estimated_cost"] += billing.estimate_cost(r, pricing)
    for d in by_day.values():
        d["estimated_cost"] = round(d["estimated_cost"], 4)

    configured_mode = billing.get_setting("billing_mode", "auto") or "auto"
    resolved_mode = billing.resolve_mode(configured_mode)

    used_models = {r["model"] for r in records}
    unconfigured = [
        {"model": m}
        for m in used_models
        if m not in pricing or all(
            pricing[m].get(k, 0) == 0
            for k in ("input_price", "output_price", "cache_read_price", "cache_write_price", "call_price")
        )
    ]

    return {
        "summary": {
            **s,
            "estimated_cost": round(estimated_total, 4),
        },
        "billing_mode": resolved_mode,
        "billing_mode_source": configured_mode,
        "daily": list(by_day.values()),
        "by_model": analytics.by_model(),
        "by_endpoint": analytics.by_endpoint(),
        "heatmap": analytics.heatmap(),
        "year_heatmap": analytics.year_heatmap(),
        "unconfigured_pricing": unconfigured,
    }


@router.get("/records")
def records_api(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    model: str | None = None,
    endpoint: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    return analytics.paged_records(page, size, model, endpoint, date_from, date_to)


@router.post("/import")
async def import_csv(file: UploadFile = File(...), debug: int = Query(0)):
    if file.size and file.size > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"文件超过 {MAX_UPLOAD_SIZE // 1024 // 1024} MB")
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, "文件过大")
    tmp = Path("data") / "_upload.csv"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_bytes(content)
    try:
        rows, errors = parse_csv(tmp)
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        tmp.unlink(missing_ok=True)

    if errors:
        _log.warning("文件 %s 有 %d 行错误:", file.filename, len(errors))
        for i, e in enumerate(errors[:20], 1):
            _log.warning("  #%d  row=%s  reason=%s", i, e.get("row_no"), e.get("reason"))
            raw = e.get("raw", {})
            if raw:
                preview = {k: v for k, v in list(raw.items())[:6]}
                _log.warning("     raw=%s", preview)
        if len(errors) > 20:
            _log.warning("  ... (其余 %d 行省略)", len(errors) - 20)

    result = import_records(file.filename or "upload.csv", len(content), rows, errors)
    resp = {
        "filename": result.filename,
        "total_rows": result.total_rows,
        "inserted": result.inserted,
        "skipped": result.skipped,
        "error_rows": result.error_rows,
    }
    if debug:
        resp["errors"] = errors
    return resp


@router.get("/settings")
def get_settings():
    return {
        "billing_mode": billing.get_setting("billing_mode", "auto") or "auto",
        "theme": billing.get_setting("theme", "system") or "system",
    }


@router.get("/layout")
def get_layout():
    return billing.get_layout()


@router.put("/layout")
def put_layout(payload: dict):
    billing.save_layout(payload)
    return billing.get_layout()


@router.put("/settings")
def put_settings(payload: dict):
    for k, v in payload.items():
        billing.set_setting(k, str(v))
    return {"ok": True}


@router.get("/pricing")
def get_pricing():
    return billing.list_pricing()


@router.put("/pricing")
def put_pricing(payload: list[dict]):
    for p in payload:
        billing.upsert_pricing(
            p["model"],
            float(p.get("input_price", 0)),
            float(p.get("output_price", 0)),
            float(p.get("cache_read_price", 0)),
            float(p.get("cache_write_price", 0)),
            float(p.get("call_price", 0)),
        )
    return {"ok": True, "count": len(payload)}


@router.post("/pricing/sync")
def pricing_sync():
    added = billing.sync_pricing_from_data()
    return {"added": added}


@router.get("/stats")
def stats_api():
    s = analytics.summary()
    from app.config import DB_PATH
    db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
    return {**s, "db_size_bytes": db_size}


@router.get("/import-history")
def import_history_api():
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT id, imported_at, filename, file_size, total_rows, "
            "inserted_rows, skipped_rows, error_rows FROM import_history "
            "ORDER BY imported_at DESC LIMIT 50"
        )
        return [dict(r) for r in cur.fetchall()]


@router.post("/clear")
def clear_data(confirm: str = Query(...)):
    if confirm != "yes":
        raise HTTPException(400, "需要 confirm=yes")
    with get_conn() as conn:
        conn.execute("DELETE FROM usage_records")
    return {"ok": True}
