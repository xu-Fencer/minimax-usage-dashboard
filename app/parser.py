import re
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = [
    "消费账号", "接口密钥名称", "消费接口", "消费模型",
    "消费金额", "代金券后消费金额", "输入消费数", "输出消费数",
    "总消费数", "消费时间", "消费结果",
]


class ParseError(ValueError):
    pass


_BUCKET_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):00-(\d{2}):00$"
)


def parse_bucket(s: str) -> str:
    if not isinstance(s, str):
        raise ParseError(f"时间字段不是字符串: {s!r}")
    m = _BUCKET_RE.match(s.strip())
    if not m:
        raise ParseError(f"无法识别的时间格式: {s!r}")
    y, mo, d, h, h2 = m.groups()
    if int(h2) != (int(h) + 1) % 24:
        raise ParseError(f"时间桶不连续: {s!r}")
    return f"{y}-{mo}-{d} {h}:00:00"


def parse_csv(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        df = pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="gbk")

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV 缺少列: {missing}")

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for idx, raw in df.iterrows():
        try:
            row = {
                "account": str(raw["消费账号"]).strip(),
                "api_key_name": str(raw["接口密钥名称"]).strip(),
                "endpoint": str(raw["消费接口"]).strip(),
                "model": str(raw["消费模型"]).strip(),
                "cost": float(raw["消费金额"] or 0),
                "cost_after_voucher": float(raw["代金券后消费金额"] or 0),
                "input_tokens": int(raw["输入消费数"] or 0),
                "output_tokens": int(raw["输出消费数"] or 0),
                "total_tokens": int(raw["总消费数"] or 0),
                "bucket_start": parse_bucket(str(raw["消费时间"])),
                "result": str(raw["消费结果"]).strip() or "SUCCESS",
            }
            rows.append(row)
        except (ParseError, ValueError, TypeError) as e:
            errors.append({
                "row_no": int(idx) + 2,
                "reason": str(e),
                "raw": {k: ("" if pd.isna(v) else str(v)) for k, v in raw.items()},
            })
    return rows, errors
