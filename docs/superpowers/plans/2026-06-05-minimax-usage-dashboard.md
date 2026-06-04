# MiniMax 用量看板 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 本地 Web 看板，把 MiniMax 导出的 CSV 用量明细导入并可视化，支持按量计费 / Token 套餐两种模式自动切换

**Architecture:** Python + FastAPI 后端，SQLite 存数据，Jinja2 模板 + 原生 JS + ECharts 渲染。`uv` 管理 Python 环境。每个核心模块（解析、导入、计费、聚合）独立文件 + 独立测试。

**Tech Stack:** Python 3.10+ / FastAPI / SQLite (stdlib) / pandas / Jinja2 / ECharts (CDN) / pytest / uv

**Spec:** `docs/superpowers/specs/2026-06-05-minimax-usage-dashboard-design.md`

---

## 文件结构

```
minimax-usage-dashboard/
├── pyproject.toml              # uv 项目配置 + 依赖
├── start.bat                   # Windows 双击启动
├── README.md
├── .gitignore
├── data/
│   └── usage.db                # 运行时生成
├── exports/
│   └── .gitkeep
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 入口、路由挂载
│   ├── config.py               # 端口、db 路径常量
│   ├── db.py                   # SQLite 连接、schema 初始化
│   ├── parser.py               # CSV 解析、bucket_start 解析
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── pages.py            # /  /settings 页面渲染
│   │   └── api.py              # 所有 JSON 端点
│   ├── services/
│   │   ├── __init__.py
│   │   ├── importer.py         # 批量写入、去重
│   │   ├── billing.py          # 价格配置、auto 判定、估算
│   │   └── analytics.py        # 看板聚合 SQL
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   └── settings.html
│   └── static/
│       ├── css/base.css
│       └── js/
│           ├── dashboard.js
│           ├── settings.js
│           └── theme.js
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_parser.py
    ├── test_importer.py
    ├── test_billing.py
    ├── test_analytics.py
    └── test_api.py
```

---

## Task 1: 项目脚手架

**Files:**
- Create: `D:\Code\project\minimax-usage-dashboard\pyproject.toml`
- Create: `D:\Code\project\minimax-usage-dashboard\.gitignore`
- Create: `D:\Code\project\minimax-usage-dashboard\start.bat`
- Create: `D:\Code\project\minimax-usage-dashboard\app\__init__.py`
- Create: `D:\Code\project\minimax-usage-dashboard\app\config.py`
- Create: `D:\Code\project\minimax-usage-dashboard\app\routes\__init__.py`
- Create: `D:\Code\project\minimax-usage-dashboard\app\services\__init__.py`
- Create: `D:\Code\project\minimax-usage-dashboard\tests\__init__.py`
- Create: `D:\Code\project\minimax-usage-dashboard\data\.gitkeep`
- Create: `D:\Code\project\minimax-usage-dashboard\exports\.gitkeep`

- [ ] **Step 1: 初始化 git 仓库**

```bash
cd D:\Code\project\minimax-usage-dashboard
git init
git config user.email "dev@local"
git config user.name "dev"
```

- [ ] **Step 2: 写 pyproject.toml**

```toml
[project]
name = "minimax-usage-dashboard"
version = "0.1.0"
description = "本地 MiniMax 用量看板"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "jinja2>=3.1",
    "pandas>=2.0",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 3: 写 .gitignore**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
data/usage.db
data/usage.db-*
*.egg-info/
.idea/
.vscode/
exports/*.csv
```

- [ ] **Step 4: 写 start.bat**

```bat
@echo off
cd /d %~dp0
uv sync
uv run uvicorn app.main:app --port 8765 --host 127.0.0.1
pause
```

- [ ] **Step 5: 写空 __init__.py 和 config.py**

`app/__init__.py`: 空文件

`app/config.py`:
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = BASE_DIR / "exports"
DB_PATH = DATA_DIR / "usage.db"

HOST = "127.0.0.1"
PORT = 8765

MAX_UPLOAD_SIZE = 50 * 1024 * 1024
```

`app/routes/__init__.py`: 空文件
`app/services/__init__.py`: 空文件
`tests/__init__.py`: 空文件

- [ ] **Step 6: 创建空目录占位**

```bash
mkdir -p D:\Code\project\minimax-usage-dashboard\data D:\Code\project\minimax-usage-dashboard\exports
echo. > D:\Code\project\minimax-usage-dashboard\data\.gitkeep
echo. > D:\Code\project\minimax-usage-dashboard\exports\.gitkeep
```

- [ ] **Step 7: 同步依赖 + 验证**

```bash
cd D:\Code\project\minimax-usage-dashboard
uv sync
uv run python -c "import fastapi, uvicorn, jinja2, pandas; print('ok')"
```

Expected: `ok`

- [ ] **Step 8: 首次提交**

```bash
cd D:\Code\project\minimax-usage-dashboard
git add .
git commit -m "chore: scaffold project (uv + FastAPI + dirs)"
```

---

## Task 2: DB schema 和连接管理

**Files:**
- Create: `D:\Code\project\minimax-usage-dashboard\app\db.py`
- Create: `D:\Code\project\minimax-usage-dashboard\tests\conftest.py`
- Create: `D:\Code\project\minimax-usage-dashboard\tests\test_db.py`

- [ ] **Step 1: 写 db.py 失败的测试**

`tests/test_db.py`:
```python
def test_init_db_creates_all_tables(isolated_db):
    import sqlite3
    from app.db import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()
    assert "usage_records" in tables
    assert "import_history" in tables
    assert "settings" in tables
    assert "model_pricing" in tables
```

- [ ] **Step 2: 写 conftest.py 设置测试 DB**

`tests/conftest.py`:
```python
import pytest
import app.db as db_module


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "DB_PATH", test_db)
    db_module.init_db()
    yield
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd D:\Code\project\minimax-usage-dashboard
uv run pytest tests/test_db.py -v
```

Expected: FAIL (没有 `init_db` 或 `DB_PATH`)

- [ ] **Step 4: 实现 db.py**

`app/db.py`:
```python
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import DB_PATH as _DEFAULT_DB_PATH

DB_PATH: Path = _DEFAULT_DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account TEXT NOT NULL,
    api_key_name TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    model TEXT NOT NULL,
    cost REAL NOT NULL DEFAULT 0,
    cost_after_voucher REAL NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    bucket_start DATETIME NOT NULL,
    result TEXT NOT NULL DEFAULT 'SUCCESS',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_record_unique
    ON usage_records(account, api_key_name, endpoint, model, bucket_start, result);

CREATE INDEX IF NOT EXISTS idx_bucket_start ON usage_records(bucket_start);
CREATE INDEX IF NOT EXISTS idx_model ON usage_records(model);
CREATE INDEX IF NOT EXISTS idx_endpoint ON usage_records(endpoint);

CREATE TABLE IF NOT EXISTS import_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    total_rows INTEGER NOT NULL,
    inserted_rows INTEGER NOT NULL,
    skipped_rows INTEGER NOT NULL,
    error_rows INTEGER NOT NULL,
    error_detail TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_pricing (
    model TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    input_price REAL NOT NULL DEFAULT 0,
    output_price REAL NOT NULL DEFAULT 0,
    cache_read_price REAL NOT NULL DEFAULT 0,
    cache_write_price REAL NOT NULL DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (model, endpoint)
);
"""


def init_db(path: Path | None = None) -> None:
    target = path or DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def get_conn(path: Path | None = None):
    target = path or DB_PATH
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd D:\Code\project\minimax-usage-dashboard
uv run pytest tests/test_db.py -v
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd D:\Code\project\minimax-usage-dashboard
git add app/db.py tests/
git commit -m "feat(db): schema for usage_records, import_history, settings, model_pricing"
```

---

## Task 3: CSV 解析器

**Files:**
- Create: `D:\Code\project\minimax-usage-dashboard\app\parser.py`
- Create: `D:\Code\project\minimax-usage-dashboard\tests\test_parser.py`
- Create: `D:\Code\project\minimax-usage-dashboard\tests\fixtures\sample.csv`

- [ ] **Step 1: 创建测试 fixture CSV**

`tests/fixtures/sample.csv`:
```csv
消费账号,接口密钥名称,消费接口,消费模型,消费金额,代金券后消费金额,输入消费数,输出消费数,总消费数,消费时间,消费结果
主账号,k1,chatcompletion-v2(Text API),MiniMax-M2.7,0.0000,0.0000,100,50,150,2026-05-04 19:00-20:00,SUCCESS
主账号,k1,cache-read(Text API),MiniMax-M2.7,0.0000,0.0000,500,0,500,2026-05-04 19:00-20:00,SUCCESS
主账号,k1,cache-create(Text API),MiniMax-M2.7,0.0000,0.0000,200,0,200,2026-05-04 20:00-21:00,SUCCESS
```

- [ ] **Step 2: 写 parser 失败的测试**

`tests/test_parser.py`:
```python
from pathlib import Path

from app.parser import parse_bucket, parse_csv, ParseError

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_bucket_normal():
    assert parse_bucket("2026-05-04 19:00-20:00") == "2026-05-04 19:00:00"


def test_parse_bucket_midnight():
    assert parse_bucket("2026-05-04 00:00-01:00") == "2026-05-04 00:00:00"


def test_parse_bucket_invalid():
    import pytest
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
    import pytest
    with pytest.raises(ValueError, match="缺少列"):
        parse_csv(p)
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd D:\Code\project\minimax-usage-dashboard
uv run pytest tests/test_parser.py -v
```

Expected: FAIL（没有 `parse_bucket` / `parse_csv`）

- [ ] **Step 4: 实现 parser.py**

`app/parser.py`:
```python
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
    """'2026-05-04 19:00-20:00' -> '2026-05-04 19:00:00'"""
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
    """解析 CSV，返回 (成功行, 错误行[{row_no, reason, raw}])"""
    try:
        df = pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="gbk")
    except FileNotFoundError:
        raise

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
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd D:\Code\project\minimax-usage-dashboard
uv run pytest tests/test_parser.py -v
```

Expected: 5 passed

- [ ] **Step 6: 提交**

```bash
cd D:\Code\project\minimax-usage-dashboard
git add app/parser.py tests/
git commit -m "feat(parser): CSV + bucket time parser with error row collection"
```



## Task 4: 导入器

**Files:**
- Create: D:\Code\project\minimax-usage-dashboard\app\services\importer.py
- Create: D:\Code\project\minimax-usage-dashboard\tests\test_importer.py

- [ ] **Step 1: 写 importer 失败的测试**

	ests/test_importer.py:
`python
from pathlib import Path
from app.services.importer import import_records, ImportResult
from app.db import get_conn

FIXTURES = Path(__file__).parent / "fixtures"


def test_import_records_inserts_and_dedupes(isolated_db):
    rows, errors = [], []
    r1 = import_records(
        filename="a.csv",
        file_size=100,
        rows=[
            {"account": "主", "api_key_name": "k", "endpoint": "chatcompletion-v2", "model": "M",
             "cost": 0, "cost_after_voucher": 0, "input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
             "bucket_start": "2026-05-04 19:00:00", "result": "SUCCESS"},
        ],
        errors=errors,
    )
    assert r1.inserted == 1
    assert r1.skipped == 0

    r2 = import_records(filename="a.csv", file_size=100, rows=[
            {"account": "主", "api_key_name": "k", "endpoint": "chatcompletion-v2", "model": "M",
             "cost": 0, "cost_after_voucher": 0, "input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
             "bucket_start": "2026-05-04 19:00:00", "result": "SUCCESS"},
        ], errors=[])
    assert r2.inserted == 0
    assert r2.skipped == 1


def test_import_records_writes_history(isolated_db):
    r = import_records(
        filename="x.csv", file_size=200, rows=[
            {"account": "主", "api_key_name": "k", "endpoint": "e", "model": "M",
             "cost": 0.01, "cost_after_voucher": 0.01, "input_tokens": 1, "output_tokens": 0, "total_tokens": 1,
             "bucket_start": "2026-05-05 00:00:00", "result": "SUCCESS"},
        ], errors=[],
    )
    with get_conn() as conn:
        cur = conn.execute("SELECT filename, inserted_rows FROM import_history")
        row = cur.fetchone()
    assert row["filename"] == "x.csv"
    assert row["inserted_rows"] == 1


def test_import_records_error_rows(isolated_db):
    r = import_records(
        filename="y.csv", file_size=50, rows=[],
        errors=[{"row_no": 2, "reason": "bad time", "raw": {}}],
    )
    assert r.error_rows == 1
    with get_conn() as conn:
        row = conn.execute("SELECT error_rows FROM import_history").fetchone()
    assert row["error_rows"] == 1
`

> 在 	ests/conftest.py 里把 isolated_db fixture 改名为直接 yield（不用 utouse），让测试显式声明依赖。

更新 	ests/conftest.py:
`python
import pytest
import app.db as db_module


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "DB_PATH", test_db)
    db_module.init_db()
    yield
`

同时更新 	ests/test_db.py 用 isolated_db fixture（去掉 utouse 依赖，改为显式声明）。

- [ ] **Step 2: 运行测试确认失败**

`ash
cd D:\Code\project\minimax-usage-dashboard
uv run pytest tests/test_importer.py -v
`

Expected: FAIL（没有 import_records）

- [ ] **Step 3: 实现 importer.py**

pp/services/importer.py:
`python
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
`

- [ ] **Step 4: 运行测试确认通过**

`ash
cd D:\Code\project\minimax-usage-dashboard
uv run pytest tests/test_importer.py -v
`

Expected: 3 passed

- [ ] **Step 5: 提交**

`ash
cd D:\Code\project\minimax-usage-dashboard
git add app/services/importer.py tests/
git commit -m "feat(importer): batch insert with dedupe + history logging"
`

---

## Task 5: 计费服务（价格 + auto 判定 + 估算）

**Files:**
- Create: D:\Code\project\minimax-usage-dashboard\app\services\billing.py
- Create: D:\Code\project\minimax-usage-dashboard\tests\test_billing.py

- [ ] **Step 1: 写 billing 失败的测试**

	ests/test_billing.py:
`python
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
    # (1000*0.001 + 500*0.002) / 1000 = 0.002
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
`

- [ ] **Step 2: 运行测试确认失败**

`ash
cd D:\Code\project\minimax-usage-dashboard
uv run pytest tests/test_billing.py -v
`

Expected: FAIL

- [ ] **Step 3: 实现 billing.py**

pp/services/billing.py:
`python
from decimal import Decimal

from app.db import get_conn, DB_PATH
from app.config import DB_PATH as _DEFAULT_DB_PATH  # noqa: F401  (re-export)
from typing import Any


def list_pricing() -> list[dict]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT model, endpoint, input_price, output_price, cache_read_price, cache_write_price "
            "FROM model_pricing ORDER BY model, endpoint"
        )
        return [dict(r) for r in cur.fetchall()]


def upsert_pricing(model: str, endpoint: str,
                   input_price: float, output_price: float,
                   cache_read_price: float, cache_write_price: float) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO model_pricing
               (model, endpoint, input_price, output_price, cache_read_price, cache_write_price)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(model, endpoint) DO UPDATE SET
                 input_price=excluded.input_price,
                 output_price=excluded.output_price,
                 cache_read_price=excluded.cache_read_price,
                 cache_write_price=excluded.cache_write_price,
                 updated_at=CURRENT_TIMESTAMP""",
            (model, endpoint, input_price, output_price, cache_read_price, cache_write_price),
        )


def sync_pricing_from_data() -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT DISTINCT model, endpoint FROM usage_records"
        )
        pairs = [(r["model"], r["endpoint"]) for r in cur.fetchall()]
        added = 0
        for m, e in pairs:
            exists = conn.execute(
                "SELECT 1 FROM model_pricing WHERE model=? AND endpoint=?",
                (m, e),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                "INSERT INTO model_pricing (model, endpoint) VALUES (?, ?)",
                (m, e),
            )
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
    # auto
    with get_conn() as conn:
        row = conn.execute("SELECT COALESCE(SUM(cost), 0) AS s FROM usage_records").fetchone()
    return "token_plan" if (row["s"] or 0) == 0 else "pay_as_you_go"


def estimate_cost(record: dict, pricing: dict[tuple[str, str], dict]) -> float:
    key = (record["model"], record["endpoint"])
    p = pricing.get(key)
    if not p:
        return 0.0
    ep = record["endpoint"]
    in_t = record.get("input_tokens", 0) or 0
    out_t = record.get("output_tokens", 0) or 0
    if ep.startswith("chatcompletion"):
        raw = in_t * p["input_price"] + out_t * p["output_price"]
    elif ep.startswith("cache-read"):
        raw = in_t * p["cache_read_price"]
    elif ep.startswith("cache-create"):
        raw = in_t * p["cache_write_price"]
    else:
        raw = in_t * p["input_price"]
    return float(Decimal(str(raw)) / Decimal("1000"))


def estimate_for_records(records: list[dict], pricing: dict[tuple[str, str], dict]) -> float:
    total = Decimal("0")
    for r in records:
        total += Decimal(str(estimate_cost(r, pricing)))
    return float(total.quantize(Decimal("0.0001")))


def pricing_dict() -> dict[tuple[str, str], dict]:
    out = {}
    for row in list_pricing():
        key = (row["model"], row["endpoint"])
        out[key] = row
    return out
`

- [ ] **Step 4: 运行测试确认通过**

`ash
cd D:\Code\project\minimax-usage-dashboard
uv run pytest tests/test_billing.py -v
`

Expected: 9 passed

- [ ] **Step 5: 提交**

`ash
cd D:\Code\project\minimax-usage-dashboard
git add app/services/billing.py tests/test_billing.py
git commit -m "feat(billing): pricing CRUD, sync, auto-mode resolution, cost estimation"
`

---

## Task 6: 看板聚合 SQL

**Files:**
- Create: D:\Code\project\minimax-usage-dashboard\app\services\analytics.py
- Create: D:\Code\project\minimax-usage-dashboard\tests\test_analytics.py

- [ ] **Step 1: 写 analytics 失败的测试**

	ests/test_analytics.py:
`python
from app.services.analytics import (
    summary, daily_series, by_model, by_endpoint, heatmap, list_records, paged_records
)


def _seed(isolated_db):
    from app.db import get_conn
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
    assert s["total_input"] == 800
    assert s["total_output"] == 30
    assert s["earliest"] == "2026-05-04T19:00:00"


def test_daily_series(isolated_db):
    _seed(isolated_db)
    d = daily_series()
    assert len(d) == 2
    assert d[0]["day"] == "2026-05-04"
    assert d[0]["total_tokens"] == 610


def test_by_model(isolated_db):
    _seed(isolated_db)
    m = by_model()
    assert m[0]["model"] == "M1"
    assert m[0]["tokens"] == 610


def test_by_endpoint(isolated_db):
    _seed(isolated_db)
    e = by_endpoint()
    assert e[0]["endpoint"] == "chatcompletion-v2"


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
`

- [ ] **Step 2: 运行测试确认失败**

`ash
cd D:\Code\project\minimax-usage-dashboard
uv run pytest tests/test_analytics.py -v
`

Expected: FAIL

- [ ] **Step 3: 实现 analytics.py**

pp/services/analytics.py:
`python
from app.db import get_conn


def summary() -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT
                COUNT(*) AS total_buckets,
                COALESCE(SUM(cost), 0) AS actual_cost,
                COALESCE(SUM(cost_after_voucher), 0) AS cost_after_voucher,
                COALESCE(SUM(input_tokens), 0) AS total_input,
                COALESCE(SUM(output_tokens), 0) AS total_output,
                MIN(bucket_start) AS earliest,
                MAX(bucket_start) AS latest
            FROM usage_records"""
        ).fetchone()
    return {
        "total_buckets": row["total_buckets"] or 0,
        "actual_cost": float(row["actual_cost"] or 0),
        "cost_after_voucher": float(row["cost_after_voucher"] or 0),
        "total_input": int(row["total_input"] or 0),
        "total_output": int(row["total_output"] or 0),
        "earliest": row["earliest"],
        "latest": row["latest"],
    }


def daily_series() -> list[dict]:
    with get_conn() as conn:
        cur = conn.execute(
            """SELECT
                DATE(bucket_start) AS day,
                SUM(input_tokens) AS input_tokens,
                SUM(output_tokens) AS output_tokens,
                SUM(total_tokens) AS total_tokens,
                SUM(cost) AS actual_cost
            FROM usage_records
            GROUP BY DATE(bucket_start)
            ORDER BY day"""
        )
        return [
            {
                "day": r["day"],
                "input_tokens": int(r["input_tokens"] or 0),
                "output_tokens": int(r["output_tokens"] or 0),
                "total_tokens": int(r["total_tokens"] or 0),
                "actual_cost": float(r["actual_cost"] or 0),
            }
            for r in cur.fetchall()
        ]


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
`

- [ ] **Step 4: 运行测试确认通过**

`ash
cd D:\Code\project\minimax-usage-dashboard
uv run pytest tests/test_analytics.py -v
`

Expected: 6 passed

- [ ] **Step 5: 提交**

`ash
cd D:\Code\project\minimax-usage-dashboard
git add app/services/analytics.py tests/test_analytics.py
git commit -m "feat(analytics): dashboard aggregations (summary, daily, model, endpoint, heatmap, paged records)"
`

---

## Task 7: API 路由

**Files:**
- Create: D:\Code\project\minimax-usage-dashboard\app\routes\api.py
- Create: D:\Code\project\minimax-usage-dashboard\tests\test_api.py
- Create: D:\Code\project\minimax-usage-dashboard\app\main.py (最小入口，把 api router 挂上)

- [ ] **Step 1: 写 API 测试**

	ests/test_api.py:
`python
import io
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
`

- [ ] **Step 2: 运行测试确认失败**

`ash
cd D:\Code\project\minimax-usage-dashboard
uv run pytest tests/test_api.py -v
`

Expected: FAIL（没有 app.main）

- [ ] **Step 3: 实现 main.py（最小骨架）**

pp/main.py:
`python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR

app = FastAPI(title="MiniMax 用量看板")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@app.get("/")
def index():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard")
def dashboard_page():
    from fastapi.responses import HTMLResponse
    from pathlib import Path
    html = (Path(__file__).parent / "templates" / "dashboard.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/settings")
def settings_page():
    from fastapi.responses import HTMLResponse
    from pathlib import Path
    html = (Path(__file__).parent / "templates" / "settings.html").read_text(encoding="utf-8")
    return HTMLResponse(html)
`

> 先用最朴素的方式返回 HTML（无模板变量）。Task 8 会替换成完整的 Jinja2 模板渲染。

- [ ] **Step 4: 创建占位模板**

pp/templates/dashboard.html:
`html
<!doctype html><html><body><h1>Dashboard (placeholder)</h1></body></html>
`

pp/templates/settings.html:
`html
<!doctype html><html><body><h1>Settings (placeholder)</h1></body></html>
`

- [ ] **Step 5: 创建占位静态目录**

`ash
mkdir -p D:\Code\project\minimax-usage-dashboard\app\static\css D:\Code\project\minimax-usage-dashboard\app\static\js
echo. > D:\Code\project\minimax-usage-dashboard\app\static\.gitkeep
`

- [ ] **Step 6: 实现 api.py**

pp/routes/api.py:
`python
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.config import MAX_UPLOAD_SIZE
from app.db import get_conn
from app.parser import parse_csv
from app.services.importer import import_records
from app.services import billing, analytics

router = APIRouter(prefix="/api")


@router.get("/dashboard")
def dashboard_data():
    s = analytics.summary()
    daily = analytics.daily_series()
    pricing = billing.pricing_dict()
    records = analytics.list_records()
    estimated_total = billing.estimate_for_records(records, pricing)
    daily_with_estimate = []
    by_day: dict[str, dict] = {d["day"]: dict(d, estimated_cost=0.0) for d in daily}
    for r in records:
        day = r["bucket_start"][:10]
        if day in by_day:
            by_day[day]["estimated_cost"] += billing.estimate_cost(r, pricing)
    for d in by_day.values():
        d["estimated_cost"] = round(d["estimated_cost"], 4)

    configured_mode = billing.get_setting("billing_mode", "auto") or "auto"
    resolved_mode = billing.resolve_mode(configured_mode)

    used_keys = {(r["model"], r["endpoint"]) for r in records}
    unconfigured = [
        {"model": m, "endpoint": e}
        for (m, e) in used_keys
        if (m, e) not in pricing or all(
            pricing[(m, e)].get(k, 0) == 0
            for k in ("input_price", "output_price", "cache_read_price", "cache_write_price")
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
async def import_csv(file: UploadFile = File(...)):
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
    result = import_records(file.filename or "upload.csv", len(content), rows, errors)
    return {
        "filename": result.filename,
        "total_rows": result.total_rows,
        "inserted": result.inserted,
        "skipped": result.skipped,
        "error_rows": result.error_rows,
    }


@router.get("/settings")
def get_settings():
    return {
        "billing_mode": billing.get_setting("billing_mode", "auto") or "auto",
        "theme": billing.get_setting("theme", "system") or "system",
    }


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
            p["model"], p["endpoint"],
            float(p.get("input_price", 0)),
            float(p.get("output_price", 0)),
            float(p.get("cache_read_price", 0)),
            float(p.get("cache_write_price", 0)),
        )
    return {"ok": True, "count": len(payload)}


@router.post("/pricing/sync")
def pricing_sync():
    added = billing.sync_pricing_from_data()
    return {"added": added}


@router.get("/stats")
def stats_api():
    s = analytics.summary()
    db_size = 0
    from app.config import DB_PATH
    if DB_PATH.exists():
        db_size = DB_PATH.stat().st_size
    return {
        **s,
        "db_size_bytes": db_size,
    }


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
`

- [ ] **Step 7: 在 main.py 挂载 api router**

更新 pp/main.py:
`python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.config import BASE_DIR
from app.routes.api import router as api_router

app = FastAPI(title="MiniMax 用量看板")
app.include_router(api_router)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def _render(name: str) -> HTMLResponse:
    html = (BASE_DIR / "app" / "templates" / name).read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/")
def index():
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard")
def dashboard_page():
    return _render("dashboard.html")


@app.get("/settings")
def settings_page():
    return _render("settings.html")
`

- [ ] **Step 8: 运行测试确认通过**

`ash
cd D:\Code\project\minimax-usage-dashboard
uv run pytest tests/test_api.py -v
`

Expected: 5 passed

- [ ] **Step 9: 提交**

`ash
cd D:\Code\project\minimax-usage-dashboard
git add app/
git commit -m "feat(api): all JSON endpoints (dashboard, records, import, settings, pricing, clear)"
`

---


## Task 8: 前端基础布局 + 主题 + 看板页

**Files:**
- Create: D:\Code\project\minimax-usage-dashboard\app\templates\dashboard.html
- Create: D:\Code\project\minimax-usage-dashboard\app\templates\base.html
- Create: D:\Code\project\minimax-usage-dashboard\app\static\css\base.css
- Create: D:\Code\project\minimax-usage-dashboard\app\static\js\dashboard.js
- Create: D:\Code\project\minimax-usage-dashboard\app\static\js\theme.js
- Modify: D:\Code\project\minimax-usage-dashboard\app\main.py (用 Jinja2 渲染)

- [ ] **Step 1: 写 base.css**

pp/static/css/base.css:
`css
:root {
  --bg: #f5f5f5;
  --surface: #ffffff;
  --text: #1f1f1f;
  --muted: #8c8c8c;
  --border: #e8e8e8;
  --primary: #1677ff;
  --success: #52c41a;
  --warning: #fa8c16;
  --danger: #ff4d4f;
  --input: #52c41a;
  --output: #fa8c16;
  --cache-read: #13c2c2;
  --cache-write: #722ed1;
}
[data-theme="dark"] {
  --bg: #141414;
  --surface: #1f1f1f;
  --text: #e8e8e8;
  --muted: #8c8c8c;
  --border: #303030;
  --primary: #1677ff;
}
* { box-sizing: border-box; }
body {
  margin: 0; font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: var(--bg); color: var(--text);
}
.nav {
  display: flex; align-items: center; gap: 24px;
  padding: 12px 24px; background: var(--surface); border-bottom: 1px solid var(--border);
}
.nav h1 { font-size: 18px; margin: 0; }
.nav a { color: var(--text); text-decoration: none; padding: 6px 12px; border-radius: 4px; }
.nav a.active { background: var(--primary); color: white; }
.nav .spacer { flex: 1; }
.nav button {
  background: transparent; border: 1px solid var(--border); color: var(--text);
  padding: 4px 10px; border-radius: 4px; cursor: pointer;
}
.container { max-width: 1200px; margin: 0 auto; padding: 24px; }
.cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 16px; }
@media (min-width: 768px) { .cards { grid-template-columns: repeat(2, 1fr); } }
.card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  padding: 20px;
}
.card .label { color: var(--muted); font-size: 13px; margin-bottom: 8px; }
.card .value { font-size: 28px; font-weight: 600; }
.card .sub { color: var(--muted); font-size: 12px; margin-top: 4px; }
.badge {
  display: inline-block; padding: 4px 10px; border-radius: 12px;
  background: var(--success); color: white; font-size: 12px; margin-bottom: 12px;
}
.section { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 16px; }
.section h2 { font-size: 16px; margin-top: 0; }
.row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.chart { width: 100%; height: 300px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border); }
th { color: var(--muted); font-weight: 500; }
.toast {
  position: fixed; top: 20px; right: 20px; padding: 12px 20px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1); display: none; z-index: 1000;
}
.toast.show { display: block; }
.toast.error { border-color: var(--danger); color: var(--danger); }
.toast.success { border-color: var(--success); color: var(--success); }
input, select, button {
  font: inherit; padding: 6px 10px; border: 1px solid var(--border);
  background: var(--surface); color: var(--text); border-radius: 4px;
}
button.primary { background: var(--primary); color: white; border-color: var(--primary); cursor: pointer; }
button.danger { background: var(--danger); color: white; border-color: var(--danger); cursor: pointer; }
`

- [ ] **Step 2: 写 theme.js**

pp/static/js/theme.js:
`js
(function () {
  const KEY = "theme";
  const root = document.documentElement;
  function apply(t) {
    if (t === "system") {
      const sys = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      root.setAttribute("data-theme", sys);
    } else {
      root.setAttribute("data-theme", t);
    }
  }
  function get() { return localStorage.getItem(KEY) || "system"; }
  function set(t) { localStorage.setItem(KEY, t); apply(t); updateBtn(); }
  function updateBtn() {
    const btn = document.getElementById("theme-btn");
    if (btn) btn.textContent = get() === "dark" ? "☀️" : "🌙";
  }
  apply(get());
  updateBtn();
  window.__setTheme = set;
  window.__getTheme = get;
})();
`

- [ ] **Step 3: 写 base.html 和 dashboard.html**

pp/templates/base.html:
`html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{% block title %}MiniMax 用量看板{% endblock %}</title>
  <link rel="stylesheet" href="/static/css/base.css">
  <script src="/static/js/theme.js"></script>
</head>
<body>
  <div class="nav">
    <h1>MiniMax 用量看板</h1>
    <a href="/dashboard" class="{% if request.path.startswith('/dashboard') %}active{% endif %}">看板</a>
    <a href="/settings" class="{% if request.path.startswith('/settings') %}active{% endif %}">设置</a>
    <div class="spacer"></div>
    <button id="theme-btn" onclick="cycleTheme()">🌙</button>
  </div>
  <div class="container">
    {% block content %}{% endblock %}
  </div>
  <div id="toast" class="toast"></div>
  <script>
    function cycleTheme() {
      const cur = window.__getTheme();
      const next = cur === "dark" ? "light" : cur === "light" ? "system" : "dark";
      window.__setTheme(next);
    }
    function toast(msg, type) {
      const t = document.getElementById("toast");
      t.textContent = msg;
      t.className = "toast show " + (type || "");
      setTimeout(() => t.className = "toast", 3000);
    }
  </script>
  {% block scripts %}{% endblock %}
</body>
</html>
`

pp/templates/dashboard.html:
`html
{% extends "base.html" %}
{% block title %}看板 - MiniMax 用量{% endblock %}
{% block content %}
<div class="cards">
  <div class="card">
    <div class="label">累计消费 <span id="mode-badge" class="badge"></span></div>
    <div class="value" id="actual-cost">¥0.00</div>
    <div class="sub" id="time-range">-</div>
  </div>
  <div class="card">
    <div class="label">估算价值</div>
    <div class="value" id="estimated-cost">¥0.00</div>
    <div class="sub" id="estimated-sub">按配置价格计算</div>
  </div>
</div>
<div id="saving-banner" class="section" style="display:none">
  <strong>💡 节省: <span id="saving-amount">¥0.00</span></strong>
  <span style="color:var(--muted);margin-left:8px">token_plan 模式下: 估算价值 = 实际价值</span>
</div>

<div class="section">
  <h2>每日用量</h2>
  <div id="daily-cost-line" class="chart"></div>
</div>

<div class="row-2">
  <div class="section">
    <h2>模型分布</h2>
    <div id="model-pie" class="chart"></div>
  </div>
  <div class="section">
    <h2>接口分布</h2>
    <div id="endpoint-pie" class="chart"></div>
  </div>
</div>

<div class="section">
  <h2>7×24 使用热力图</h2>
  <div id="heatmap" class="chart" style="height:240px"></div>
</div>

<div class="section">
  <h2>原始数据</h2>
  <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
    <select id="filter-model"><option value="">全部模型</option></select>
    <select id="filter-endpoint"><option value="">全部接口</option></select>
    <input type="date" id="filter-from">
    <input type="date" id="filter-to">
    <button class="primary" onclick="loadRecords()">应用</button>
  </div>
  <table id="records-table">
    <thead><tr>
      <th>时间</th><th>模型</th><th>接口</th>
      <th>输入</th><th>输出</th><th>总</th><th>实际</th>
    </tr></thead>
    <tbody></tbody>
  </table>
  <div id="pager" style="margin-top:12px;display:flex;gap:8px;align-items:center">
    <button onclick="prevPage()">上一页</button>
    <span id="page-info">1/1</span>
    <button onclick="nextPage()">下一页</button>
  </div>
</div>

{% endblock %}
{% block scripts %}
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<script src="/static/js/dashboard.js"></script>
{% endblock %}
`

- [ ] **Step 4: 写 dashboard.js**

pp/static/js/dashboard.js:
`js
let currentPage = 1;
let charts = {};

function fmt(n) {
  return "¥" + Number(n || 0).toFixed(2);
}
function fmtInt(n) {
  return Number(n || 0).toLocaleString("zh-CN");
}

function destroyCharts() {
  Object.values(charts).forEach(c => c.dispose());
  charts = {};
}

function renderDailyChart(daily) {
  const el = document.getElementById("daily-cost-line");
  charts.daily = echarts.init(el);
  charts.daily.setOption({
    tooltip: { trigger: "axis" },
    legend: { data: ["输入", "输出", "估算价值"] },
    grid: { left: 60, right: 30, top: 40, bottom: 40 },
    xAxis: { type: "category", data: daily.map(d => d.day) },
    yAxis: [
      { type: "value", name: "Tokens" },
      { type: "value", name: "¥", position: "right" },
    ],
    series: [
      { name: "输入", type: "bar", stack: "t", data: daily.map(d => d.input_tokens), itemStyle: { color: "#52c41a" } },
      { name: "输出", type: "bar", stack: "t", data: daily.map(d => d.output_tokens), itemStyle: { color: "#fa8c16" } },
      { name: "估算价值", type: "line", yAxisIndex: 1, data: daily.map(d => d.estimated_cost), itemStyle: { color: "#1677ff" } },
    ],
  });
}

function renderPie(elId, data, nameField) {
  const el = document.getElementById(elId);
  charts[elId] = echarts.init(el);
  charts[elId].setOption({
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    series: [{
      type: "pie", radius: ["40%", "70%"],
      data: data.map(d => ({ name: d[nameField], value: d.tokens })),
    }],
  });
}

function renderHeatmap(cells) {
  const el = document.getElementById("heatmap");
  charts.heatmap = echarts.init(el);
  const hours = Array.from({ length: 24 }, (_, i) => i + ":00");
  const dows = ["日", "一", "二", "三", "四", "五", "六"];
  const data = cells.map(c => [c.hour, c.dow, c.tokens]);
  charts.heatmap.setOption({
    tooltip: { position: "top", formatter: p => ${dows[p.data[1]]} :00<br> tokens },
    grid: { left: 50, right: 20, top: 20, bottom: 40 },
    xAxis: { type: "category", data: hours, splitArea: { show: true } },
    yAxis: { type: "category", data: dows, splitArea: { show: true } },
    visualMap: { min: 0, max: Math.max(1, ...cells.map(c => c.tokens)), calculable: true, orient: "horizontal", left: "center", bottom: 0 },
    series: [{ type: "heatmap", data, label: { show: false } }],
  });
}

async function loadDashboard() {
  destroyCharts();
  const r = await fetch("/api/dashboard");
  if (!r.ok) { toast("加载失败: " + r.status, "error"); return; }
  const d = await r.json();
  const s = d.summary;

  document.getElementById("actual-cost").textContent = fmt(s.actual_cost);
  document.getElementById("estimated-cost").textContent = fmt(s.estimated_cost);
  document.getElementById("mode-badge").textContent = d.billing_mode;
  document.getElementById("time-range").textContent =
    s.earliest ? ${s.earliest} ~  : "暂无数据";

  if (d.billing_mode === "token_plan") {
    const saving = (s.estimated_cost || 0) - (s.actual_cost || 0);
    document.getElementById("saving-banner").style.display = "block";
    document.getElementById("saving-amount").textContent = fmt(saving);
  }

  renderDailyChart(d.daily);
  renderPie("model-pie", d.by_model, "model");
  renderPie("endpoint-pie", d.by_endpoint, "endpoint");
  renderHeatmap(d.heatmap);

  await loadRecords();
  await loadFilterOptions();
}

async function loadFilterOptions() {
  const r = await fetch("/api/dashboard");
  const d = await r.json();
  const m = document.getElementById("filter-model");
  d.by_model.forEach(x => {
    const o = document.createElement("option");
    o.value = x.model; o.textContent = x.model;
    m.appendChild(o);
  });
  const ep = document.getElementById("filter-endpoint");
  d.by_endpoint.forEach(x => {
    const o = document.createElement("option");
    o.value = x.endpoint; o.textContent = x.endpoint;
    ep.appendChild(o);
  });
}

async function loadRecords() {
  const params = new URLSearchParams({
    page: currentPage, size: 50,
    model: document.getElementById("filter-model").value,
    endpoint: document.getElementById("filter-endpoint").value,
    date_from: document.getElementById("filter-from").value,
    date_to: document.getElementById("filter-to").value,
  });
  const r = await fetch("/api/records?" + params);
  const d = await r.json();
  const tbody = document.querySelector("#records-table tbody");
  tbody.innerHTML = "";
  d.rows.forEach(row => {
    const tr = document.createElement("tr");
    tr.innerHTML = 
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>;
    tbody.appendChild(tr);
  });
  const totalPages = Math.max(1, Math.ceil(d.total / d.size));
  document.getElementById("page-info").textContent = ${d.page}/ (共  条);
}

function prevPage() { if (currentPage > 1) { currentPage--; loadRecords(); } }
function nextPage() { currentPage++; loadRecords(); }

window.addEventListener("resize", () => {
  Object.values(charts).forEach(c => c.resize());
});
loadDashboard();
`

- [ ] **Step 5: 更新 main.py 用 Jinja2 渲染**

更新 pp/main.py:
`python
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR
from app.routes.api import router as api_router

app = FastAPI(title="MiniMax 用量看板")
app.include_router(api_router)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@app.get("/")
def index():
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return TEMPLATES.TemplateResponse(request, "dashboard.html", {})


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return TEMPLATES.TemplateResponse(request, "settings.html", {})
`

- [ ] **Step 6: 启动服务手工验证**

`ash
cd D:\Code\project\minimax-usage-dashboard
uv run uvicorn app.main:app --port 8765
`

打开浏览器：
- http://localhost:8765/dashboard → 看到 2 张卡 + 提示"暂无数据" + 表格
- 切换主题按钮工作
- 调整窗口大小图表自适应

- [ ] **Step 7: 提交**

`ash
cd D:\Code\project\minimax-usage-dashboard
git add app/
git commit -m "feat(ui): dashboard page with ECharts (5 charts, filterable table) and theme"
`

---

## Task 9: 设置页 + 计费配置

**Files:**
- Create: D:\Code\project\minimax-usage-dashboard\app\templates\settings.html
- Create: D:\Code\project\minimax-usage-dashboard\app\static\js\settings.js
- Create: D:\Code\project\minimax-usage-dashboard\app\static\js\import.js

- [ ] **Step 1: 写 settings.html**

pp/templates/settings.html:
`html
{% extends "base.html" %}
{% block title %}设置 - MiniMax 用量{% endblock %}
{% block content %}
<div class="section">
  <h2>📥 导入 CSV</h2>
  <div id="drop-zone" style="border:2px dashed var(--border);padding:40px;text-align:center;border-radius:8px;cursor:pointer">
    <p>拖拽 CSV 到这里 或 <button class="primary" onclick="document.getElementById('file-input').click()">选择文件</button></p>
    <input type="file" id="file-input" accept=".csv" style="display:none">
  </div>
  <div id="import-result" style="margin-top:12px"></div>
</div>

<div class="section">
  <h2>📋 导入历史</h2>
  <table id="history-table">
    <thead><tr>
      <th>时间</th><th>文件名</th><th>新增</th><th>跳过</th><th>错误</th>
    </tr></thead>
    <tbody></tbody>
  </table>
</div>

<div class="section">
  <h2>📊 数据概览</h2>
  <div id="stats">加载中...</div>
</div>

<div class="section">
  <h2>💰 计费配置</h2>
  <div style="margin-bottom:12px">
    模式:
    <label><input type="radio" name="bm" value="auto" onchange="saveSettings()"> 自动</label>
    <label><input type="radio" name="bm" value="pay_as_you_go" onchange="saveSettings()"> 按量计费</label>
    <label><input type="radio" name="bm" value="token_plan" onchange="saveSettings()"> Token 套餐</label>
    <span id="current-mode" style="margin-left:12px;color:var(--muted)"></span>
  </div>
  <h3 style="font-size:14px;margin-top:20px">模型价格表 (CNY / 1k tokens)</h3>
  <button onclick="syncPricing()" style="margin-bottom:12px">从数据中拉取 (model, endpoint) 组合</button>
  <table id="pricing-table" style="font-size:12px">
    <thead><tr>
      <th>模型</th><th>接口</th>
      <th>输入</th><th>输出</th><th>缓存读</th><th>缓存写</th>
    </tr></thead>
    <tbody></tbody>
  </table>
  <p style="color:var(--muted);font-size:12px;margin-top:8px">
    说明: 不同 endpoint 类型适用的字段不同:
    <code>chatcompletion-v2</code> 用输入/输出，
    <code>cache-read</code> 用缓存读，
    <code>cache-create</code> 用缓存写。
  </p>
  <button class="primary" onclick="savePricing()">保存价格</button>
</div>

<div class="section">
  <h2>🎨 外观</h2>
  <select onchange="window.__setTheme(this.value)">
    <option value="system">跟随系统</option>
    <option value="light">浅色</option>
    <option value="dark">深色</option>
  </select>
</div>

<div class="section" style="border-color:var(--danger)">
  <h2 style="color:var(--danger)">⚠️ 危险区</h2>
  <button class="danger" onclick="clearAll()">清空所有数据</button>
</div>
{% endblock %}
{% block scripts %}
<script src="/static/js/import.js"></script>
<script src="/static/js/settings.js"></script>
{% endblock %}
`

- [ ] **Step 2: 写 import.js（拖拽 + 上传）**

pp/static/js/import.js:
`js
(function () {
  const dz = document.getElementById("drop-zone");
  const fi = document.getElementById("file-input");
  const out = document.getElementById("import-result");

  function upload(file) {
    const fd = new FormData();
    fd.append("file", file);
    out.textContent = "上传中...";
    fetch("/api/import", { method: "POST", body: fd })
      .then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e)))
      .then(d => {
        out.innerHTML = <strong>导入完成</strong> 新增  / 跳过  / 错误 ;
        toast("导入成功", "success");
        if (window.loadHistory) loadHistory();
        if (window.loadStats) loadStats();
      })
      .catch(e => { out.textContent = "失败: " + (e.detail || JSON.stringify(e)); toast("导入失败", "error"); });
  }

  dz.addEventListener("click", () => fi.click());
  dz.addEventListener("dragover", e => { e.preventDefault(); dz.style.background = "var(--bg)"; });
  dz.addEventListener("dragleave", () => dz.style.background = "");
  dz.addEventListener("drop", e => {
    e.preventDefault();
    dz.style.background = "";
    const f = e.dataTransfer.files[0];
    if (f) upload(f);
  });
  fi.addEventListener("change", e => { const f = e.target.files[0]; if (f) upload(f); });
})();
`

- [ ] **Step 3: 写 settings.js（历史 + 概览 + 计费）**

pp/static/js/settings.js:
`js
async function loadHistory() {
  const r = await fetch("/api/import-history");
  const items = await r.json();
  const tbody = document.querySelector("#history-table tbody");
  tbody.innerHTML = items.map(i => 
    <tr>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
    </tr>).join("");
}

async function loadStats() {
  const r = await fetch("/api/stats");
  const s = await r.json();
  const sizeKb = (s.db_size_bytes / 1024).toFixed(1);
  document.getElementById("stats").innerHTML = 
    <div>总行数: <strong></strong></div>
    <div>时间范围:  ~ </div>
    <div>数据库大小:  KB</div>
  ;
}

async function loadSettings() {
  const r = await fetch("/api/settings");
  const s = await r.json();
  document.querySelector(input[name=bm][value=]).checked = true;
  document.getElementById("current-mode").textContent = 当前: ;
  document.querySelector(".section select").value = s.theme;
}

async function saveSettings() {
  const v = document.querySelector("input[name=bm]:checked").value;
  await fetch("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ billing_mode: v }),
  });
  toast("已保存", "success");
}

async function loadPricing() {
  const r = await fetch("/api/pricing");
  const items = await r.json();
  const tbody = document.querySelector("#pricing-table tbody");
  tbody.innerHTML = items.map((p, i) => 
    <tr>
      <td></td>
      <td></td>
      <td><input type="number" step="0.0001" data-i="" data-k="input_price" value=""></td>
      <td><input type="number" step="0.0001" data-i="" data-k="output_price" value=""></td>
      <td><input type="number" step="0.0001" data-i="" data-k="cache_read_price" value=""></td>
      <td><input type="number" step="0.0001" data-i="" data-k="cache_write_price" value=""></td>
    </tr>).join("");
  window.__pricing = items;
}

async function syncPricing() {
  const r = await fetch("/api/pricing/sync", { method: "POST" });
  const d = await r.json();
  toast(新增  条, "success");
  await loadPricing();
}

async function savePricing() {
  const items = window.__pricing || [];
  const updated = items.map((p, i) => {
    const out = { ...p };
    ["input_price", "output_price", "cache_read_price", "cache_write_price"].forEach(k => {
      const inp = document.querySelector(input[data-i=""][data-k=""]);
      if (inp) out[k] = parseFloat(inp.value || 0);
    });
    return out;
  });
  await fetch("/api/pricing", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updated),
  });
  toast("价格已保存", "success");
}

async function clearAll() {
  if (!confirm("确定清空所有用量数据？此操作不可恢复。")) return;
  if (!confirm("再次确认: 所有记录和导入历史都会删除")) return;
  const r = await fetch("/api/clear?confirm=yes", { method: "POST" });
  if (r.ok) { toast("已清空", "success"); loadHistory(); loadStats(); }
  else toast("清空失败", "error");
}

(async () => {
  await loadSettings();
  await loadHistory();
  await loadStats();
  await loadPricing();
})();
`

- [ ] **Step 4: 启动手工验证**

`ash
cd D:\Code\project\minimax-usage-dashboard
uv run uvicorn app.main:app --port 8765
`

打开 http://localhost:8765/settings 验证：
- 拖拽 xport_bill_1780590422.csv 进 drop-zone → 看到新增 / 跳过 / 错误数
- "从数据中拉取" 按钮 → 价格表出现 5+ 行
- 填几个价格 → "保存价格" → toast 成功
- 切到 /dashboard → "估算价值" 卡片有数字
- 切回 /settings → 模式选择 / 主题下拉 / 清空按钮 都工作

- [ ] **Step 5: 提交**

`ash
cd D:\Code\project\minimax-usage-dashboard
git add app/
git commit -m "feat(ui): settings page (import, history, stats, billing config, theme, clear)"
`

---

## Task 10: 端到端验证

- [ ] **Step 1: 跑全部测试**

`ash
cd D:\Code\project\minimax-usage-dashboard
uv run pytest -v
`

Expected: 全部通过（~30 tests）

- [ ] **Step 2: 端到端手工流程**

`ash
# 清掉 db 重新开始
rm -f D:\Code\project\minimax-usage-dashboard\data\usage.db
uv run uvicorn app.main:app --port 8765
`

走一遍：
1. 打开 /settings
2. 拖入 xport_bill_1780590422.csv
3. 看到导入结果: 新增 131 / 跳过 0 / 错误 0
4. 看到导入历史有一条
5. 数据概览显示 131 行，5/4 ~ 6/1
6. 点"从数据中拉取" → 价格表出现
7. 填几个价格（输入/输出）
8. 保存价格
9. 切到 /dashboard
10. "累计消费 ¥0.00"（token_plan 模式）
11. "估算价值 ¥X.XX"（按填的价格算的）
12. 节省徽章显示 ¥X.XX
13. 每日用量柱状图渲染
14. 模型分布 / 接口分布 饼图渲染
15. 7×24 热力图渲染
16. 原始数据表显示，过滤器工作
17. 切到深色主题 → 所有图表和页面正常
18. 回 /settings → 改模式为 "按量计费" → /dashboard 上节省徽章消失

- [ ] **Step 3: 重复导入测试**

`ash
# 不关服务，再拖一次同一份 CSV
`

Expected: 跳过 131 / 错误 0 / 新增 0

- [ ] **Step 4: 提交（如有 fix）**

`ash
cd D:\Code\project\minimax-usage-dashboard
git add -A
git diff --cached --quiet || git commit -m "chore: e2e verification fixes"
`

---

## Task 11: README

**Files:**
- Create: D:\Code\project\minimax-usage-dashboard\README.md

- [ ] **Step 1: 写 README**

`markdown
# MiniMax 用量看板

本地 Web 看板，把 MiniMax 平台导出的 CSV 用量明细做可视化，支持按量计费 / Token 套餐两种模式。

## 特性

- 拖拽导入 MiniMax 导出的 CSV，自动去重
- 累计消费 / 估算价值 / 节省 三大金额卡
- 每日用量趋势 + 模型分布 + 接口分布 + 7×24 热力图 + 原始数据表
- 模型价格表按 (模型, 接口) 配置，cache 读 / 写 和普通 chat 单价分开
- 浅色 / 深色 / 跟随系统主题
- 单文件 SQLite，无需安装数据库

## 环境要求

- Python 3.10+
- [uv](https://github.com/astral-sh/uv)

## 启动

### Windows

双击 start.bat

### 命令行

`ash
uv sync
uv run uvicorn app.main:app --port 8765
`

打开 http://localhost:8765

## 使用流程

1. 打开 [MiniMax 平台](https://platform.minimaxi.com/console/consumption-detail?tab=api-keys)，导出 CSV（最多 3 个月）
2. 打开 http://localhost:8765/settings
3. 拖入 CSV
4. 点"从数据中拉取"→ 填入模型价格（CNY / 1k tokens）
5. 打开 http://localhost:8765/dashboard 查看图表

## 数据存储

- 数据库：data/usage.db（SQLite）
- 建议定期备份此文件

## 多次导入

MiniMax 限制单次最多导出 3 个月。每月导出一次，看板会自动合并去重（按 11 字段唯一键）。

## 测试

`ash
uv run pytest -v
`

## 目录结构

`
app/
├── main.py         # FastAPI 入口
├── config.py       # 配置
├── db.py           # SQLite schema
├── parser.py       # CSV 解析
├── routes/
│   └── api.py      # JSON API
├── services/
│   ├── importer.py
│   ├── billing.py
│   └── analytics.py
├── templates/      # Jinja2 模板
└── static/         # CSS / JS
tests/
└── ...             # pytest 测试
`

## 许可

仅供个人使用。
`

- [ ] **Step 2: 提交**

`ash
cd D:\Code\project\minimax-usage-dashboard
git add README.md
git commit -m "docs: README with usage and structure"
`

---

## 完成

11 个任务完成后，本地看板就完整可用了。

- [ ] **Step 3: 跑一次全测试确认**

`ash
cd D:\Code\project\minimax-usage-dashboard
uv run pytest -v
`

Expected: 全部通过

