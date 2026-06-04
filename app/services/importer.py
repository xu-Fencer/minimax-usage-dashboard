from dataclasses import dataclass

from app.db import get_conn


@dataclass
class ImportResult:
    filename: str
    file_size: int
    total_rows: int
    inserted: int
    skipped: int
    error_rows: int


def import_records(
    filename: str,
    file_size: int,
    rows: list[dict],
    errors: list[dict],
) -> ImportResult:
    inserted = 0
    skipped = 0
    with get_conn() as conn:
        for r in rows:
            cur = conn.execute(
                """INSERT OR IGNORE INTO usage_records
                   (account, api_key_name, endpoint, model,
                    cost, cost_after_voucher,
                    input_tokens, output_tokens, total_tokens,
                    bucket_start, result)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (r["account"], r["api_key_name"], r["endpoint"], r["model"],
                 r["cost"], r["cost_after_voucher"],
                 r["input_tokens"], r["output_tokens"], r["total_tokens"],
                 r["bucket_start"], r["result"]),
            )
            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1

        conn.execute(
            """INSERT INTO import_history
               (filename, file_size, total_rows, inserted_rows, skipped_rows, error_rows)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (filename, file_size, len(rows), inserted, skipped, len(errors)),
        )

    return ImportResult(
        filename=filename,
        file_size=file_size,
        total_rows=len(rows) + len(errors),
        inserted=inserted,
        skipped=skipped,
        error_rows=len(errors),
    )
