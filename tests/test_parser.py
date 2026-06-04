from pathlib import Path

import pytest

from app.parser import parse_bucket, parse_csv, ParseError

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_bucket_normal():
    assert parse_bucket("2026-05-04 19:00-20:00") == "2026-05-04 19:00:00"


def test_parse_bucket_midnight():
    assert parse_bucket("2026-05-04 00:00-01:00") == "2026-05-04 00:00:00"


def test_parse_bucket_invalid():
    with pytest.raises(ParseError):
        parse_bucket("not a time")


def test_parse_csv_happy_path():
    rows, errors = parse_csv(FIXTURES / "sample.csv")
    assert len(errors) == 0
    assert len(rows) == 3
    r = rows[0]
    assert r["account"] == "主账号"
    assert r["api_key_name"] == "k1"
    assert r["endpoint"] == "chatcompletion-v2(Text API)"
    assert r["model"] == "MiniMax-M2.7"
    assert r["input_tokens"] == 100
    assert r["output_tokens"] == 50
    assert r["total_tokens"] == 150
    assert r["bucket_start"] == "2026-05-04 19:00:00"
    assert r["result"] == "SUCCESS"


def test_parse_csv_missing_columns(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("a,b,c\n1,2,3", encoding="utf-8")
    with pytest.raises(ValueError, match="缺少列"):
        parse_csv(p)
