# MiniMax 用量看板 - 设计文档

- 日期：2026-06-05
- 状态：待用户审阅
- 范围：本地单用户 Web 看板，复刻 DeepSeek 用量页的体验，喂入 MiniMax 用量明细 CSV

## 1. 背景与目标

### 1.1 现状
- MiniMax 开放平台（`https://platform.minimaxi.com/console/consumption-detail?tab=api-keys`）的用量明细页受限于 3 个月导出窗口
- 用户希望像 DeepSeek 用量页（`https://platform.deepseek.com/usage`）那样直接看图、看趋势、看分布
- MiniMax 没有开放给普通用户的 API，只能手动从页面导出 CSV
- 用户当前在 `coding_plan` 套餐下，所有金额为 0，但希望知道"如果按量计费大概要花多少"

### 1.2 目标
- 本地起一个轻量 Web 服务，把 MiniMax 导出的 CSV 导入后做可视化
- 支持多次导入增量追加，绕开 3 个月导出窗口
- 支持两种计费模式：按量计费（用 CSV 实际金额）和 Token 套餐（用配置价格估算"价值"）
- 单用户、单机使用，无需登录
- 双击启动，看到数据，结束

### 1.3 非目标
- 不做用户系统、登录、权限
- 不做实时刷新（按 F5 即可）
- 不做从网站自动拉数据（手动导出 + 拖入导入）
- 不做多账号 UI（数据模型支持但不暴露）
- 不做数据再导出（需要时再说）
- 不做套餐成本核算（只看按量价值）

## 2. 数据来源

### 2.1 样本文件
- 路径：`export_bill_1780590422.csv`
- 大小：15.5 KB
- 行数：132（含表头 = 131 条数据）
- 时间跨度：2026-05-04 ~ 2026-06-01

### 2.2 字段
中文表头（11 列）：

| 列名 | 类型 | 含义 |
|------|------|------|
| 消费账号 | TEXT | 消费账号（当前样本：主账号） |
| 接口密钥名称 | TEXT | API 密钥名（当前样本：coding_plan） |
| 消费接口 | TEXT | 调用的 endpoint（chatcompletion-v2、cache-read、cache-create、code_plan_resource_package） |
| 消费模型 | TEXT | 模型名（MiniMax-M3-512k、MiniMax-M2.7、coding-plan-vlm） |
| 消费金额 | REAL | 消费金额（当前样本全部为 0） |
| 代金券后消费金额 | REAL | 代金券后金额 |
| 输入消费数 | INTEGER | 输入 token 数 |
| 输出消费数 | INTEGER | 输出 token 数 |
| 总消费数 | INTEGER | 总 token 数 |
| 消费时间 | TEXT | 时间段，格式 `YYYY-MM-DD HH:00-HH+1:00`，每小时一个桶 |
| 消费结果 | TEXT | SUCCESS / FAILED |

### 2.3 已知数据特征
- 金额全部为 0：用户是 coding_plan 套餐用户，按调用次数而非 token 计费
- 存在 cache-read、cache-create、code_plan_resource_package 等多种接口类型
- 时间字段是 hourly bucket，不是精确时间戳
- 当前样本里只有 SUCCESS，没有 FAILED 记录（但表结构需要保留 result 字段以便未来遇到失败数据）

## 3. 技术栈

| 层 | 选型 | 理由 |
|---|------|------|
| 后端 | Python 3.10+ / FastAPI | 启动快、文档好、单文件可跑 |
| 环境管理 | `uv` | 防止污染全局 Python，自带 venv / lock / 脚本运行 |
| CSV 解析 | pandas | 处理脏数据、分块、类型推断都很方便 |
| 数据库 | SQLite | 文件型、零配置、单用户场景够用 |
| ORM | 原生 SQL + sqlite3 标准库 | 表结构简单、避免引入 SQLAlchemy |
| 前端渲染 | Jinja2 模板 + 原生 JS | 服务端渲染首屏，避免引入构建链 |
| 图表库 | ECharts（CDN） | 中文友好、社区活跃、文档全 |
| 样式 | 原生 CSS + CSS 变量（主题） | 无需 Tailwind/PostCSS 编译 |
| 启动 | `start.bat`（双击） + `uv run uvicorn` | 零命令启动 |

不引入：
- npm / Vite / Webpack
- Docker
- React / Vue / Svelte

## 4. 数据模型

### 4.1 表结构

```sql
CREATE TABLE usage_records (
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

CREATE UNIQUE INDEX idx_record_unique
    ON usage_records(account, api_key_name, endpoint, model, bucket_start, result);

CREATE INDEX idx_bucket_start ON usage_records(bucket_start);
CREATE INDEX idx_model ON usage_records(model);
CREATE INDEX idx_endpoint ON usage(endpoint);
```

### 4.2 唯一键去重
- 业务唯一键 = (account, api_key_name, endpoint, model, bucket_start, result)
- 重复导入同一份 CSV：`INSERT OR IGNORE` 静默跳过
- 数据库约束兜底，即使应用层漏判也写不进去

### 4.3 导入历史表

```sql
CREATE TABLE import_history (
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
```

### 4.4 设置表（key-value 通用配置）

```sql
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

存储项：
- `billing_mode` = `auto` | `pay_as_you_go` | `token_plan`（默认 `auto`）
- `theme` = `system` | `light` | `dark`（默认 `system`）
- `currency` = `CNY`（固定，仅展示用）

### 4.5 价格表（结构化）

价格维度是 `(model, endpoint)`：不同模型在不同的 endpoint 上的单价可能不同，cache 读写的单价和普通 chat 单价不一样。

```sql
CREATE TABLE model_pricing (
    model TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    input_price REAL NOT NULL DEFAULT 0,        -- CNY / 1k tokens, 普通 chat 输入
    output_price REAL NOT NULL DEFAULT 0,       -- CNY / 1k tokens, 普通 chat 输出
    cache_read_price REAL NOT NULL DEFAULT 0,   -- CNY / 1k tokens, cache-read
    cache_write_price REAL NOT NULL DEFAULT 0,  -- CNY / 1k tokens, cache-create
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (model, endpoint)
);
```

### 4.6 计费模式设计

三种模式，对应用户在 MiniMax 上的不同账户形态：

| 模式 | 适用场景 | 实际成本 | 估算成本 | "节省"指标 |
|------|----------|----------|----------|------------|
| `pay_as_you_go` 按量计费 | 余额扣费 | 取 CSV 的 `消费金额` | 用配置价格算（可选对照） | N/A |
| `token_plan` 套餐制 | 套餐用户 | 0 | 用配置价格算 | 估算成本（=价值） |
| `auto` 自动 | 默认 | 看数据判断 | 同上 | 视模式决定 |

**`auto` 判定规则**：当 `SUM(cost) = 0` 时按 `token_plan` 显示，否则按 `pay_as_you_go` 显示。

**"节省"语义**：
- 在 `token_plan` 模式下，"节省" = 估算成本 - 实际成本 = 估算成本
  - 表示"如果按量计费，你本来要花这么多钱"
- 在 `pay_as_you_go` 模式下，不显示"节省"卡片

**价格配置**：
- 设置页"模型价格表"自动从导入数据中拉取所有出现过的 `(model, endpoint)` 组合
- 每个组合 4 个输入框：输入 / 输出 / 缓存读 / 缓存写（CNY / 1k tokens）
- 不同 endpoint 类型填不同的字段：
  - `chatcompletion-v2(Text API)`：填 input / output
  - `cache-read(Text API)`：填 cache_read
  - `cache-create(Text API)`：填 cache_write
  - `code_plan_resource_package` 等其他：填 input（按"次"计费时把 1 视作 1 token）
- 没填 = 该组合不参与估算（在 UI 上标"未配置"）

**估算公式**（按行）：
```
根据 endpoint 类型选择对应的单价字段：
  chatcompletion-v2 : cost = (input_tokens  * input_price
                           + output_tokens * output_price) / 1000
  cache-read        : cost = (input_tokens  * cache_read_price)  / 1000
  cache-create      : cost = (input_tokens  * cache_write_price) / 1000
  其他              : cost = (input_tokens  * input_price) / 1000

未配置价格的 (model, endpoint) 该行 cost = 0
总估算 = SUM(cost)
```

## 5. 页面与路由

参考 DeepSeek 用量页（`https://platform.deepseek.com/usage`）的简洁风格：
顶部 2 张关键金额卡 + 1 个主图 + 时间范围选择 + 导出。
我们在此基础上做扩展（多图表、明细、配置）。

### 5.1 路由

| 路径 | 方法 | 用途 |
|------|------|------|
| `GET /` | 看板页 | 渲染看板 |
| `GET /settings` | 设置页 | 渲染设置 |
| `POST /api/import` | 上传 CSV | 解析、写入、返回结果 |
| `GET /api/dashboard` | 看板数据 | 返回所有聚合 JSON |
| `GET /api/records` | 原始数据 | 分页、过滤、排序 |
| `GET /api/settings` | 获取所有设置 | 返回 settings 表 |
| `PUT /api/settings` | 批量更新设置 | 写回 settings 表 |
| `GET /api/pricing` | 获取所有价格 | 列出 model_pricing 表 |
| `PUT /api/pricing` | 批量更新价格 | 写回 model_pricing 表 |
| `GET /api/pricing/sync` | 拉取数据中存在的 (model, endpoint) 组合 | 自动补全价格表 |
| `POST /api/clear` | 清空数据 | 删除所有记录（带 confirm token） |
| `GET /api/stats` | 概览数据 | 总行数、时间范围、db 大小 |

### 5.2 看板页布局

```
┌────────────────────────────────────────────────────────┐
│  MiniMax 用量看板                       [看板] [设置]  │  <- 顶栏
│  数据来源: MiniMax 平台导出的 CSV · 按小时聚合           │
├────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐  ┌──────────────────────┐    │
│  │ 累计消费              │  │ 估算价值              │    │  <- 2 张主卡
│  │ ¥0.00 CNY            │  │ ¥X.XX CNY            │    │     (DeepSeek 同款)
│  │ [token_plan]         │  │ (按配置价格)          │    │
│  └──────────────────────┘  └──────────────────────┘    │
│  💡 节省: ¥X.XX  (套餐制下: 等同于估算价值)              │  <- 节省徽章
├────────────────────────────────────────────────────────┤
│  每日用量                          [时段▼] [导入 CSV]   │  <- DeepSeek 同款
│  消费金额 ¥0.00 · 估算 ¥X.XX                           │
│  ┌──────────────────────────────────────────────────┐  │
│  │   折线图: 每日 token / cost                       │  │  <- DeepSeek 同款
│  └──────────────────────────────────────────────────┘  │
├────────────────────────────────────────────────────────┤
│  模型分布 (饼图)        │  接口分布 (环形图)            │  <- 我们的扩展
│  MiniMax-M3-512k: 60%  │  chatcompletion: 50%        │
│  MiniMax-M2.7: 35%      │  cache-read: 30%            │
│  coding-plan-vlm: 5%    │  cache-create: 18%          │
│                        │  code_plan_resource: 2%     │
├────────────────────────────────────────────────────────┤
│  7×24 使用热力图                                       │  <- 我们的扩展
│  ┌──────────────────────────────────────────────────┐  │
│  │   横轴: 周一~周日, 纵轴: 0~23 时                  │  │
│  └──────────────────────────────────────────────────┘  │
├────────────────────────────────────────────────────────┤
│  原始数据 (表格 + 过滤 + 排序)                          │  <- 我们的扩展
│  [模型▼] [接口▼] [日期范围] [搜索]                       │
│  ┌──────────────────────────────────────────────────┐  │
│  │  时间 | 模型 | 接口 | 输入 | 输出 | 总 | 金额    │  │
│  │  ...                                            │  │
│  │  [上一页] 1/3 [下一页]                           │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

### 5.3 设置页布局

```
┌────────────────────────────────────────────────────────┐
│  顶栏                                                    │
├────────────────────────────────────────────────────────┤
│  📥 导入 CSV                                             │
│  ┌──────────────────────────────────────────┐           │
│  │   拖拽 CSV 到这里 或 [选择文件]            │           │
│  └──────────────────────────────────────────┘           │
│  导入结果: 新增 X 行 / 跳过 Y 行 / 错误 Z 行             │
├────────────────────────────────────────────────────────┤
│  📋 导入历史                                             │
│  时间 | 文件名 | 新增 | 跳过 | 错误                      │
├────────────────────────────────────────────────────────┤
│  📊 数据概览                                             │
│  总行数 / 时间范围 / 最早 / 最新 / 数据库大小             │
├────────────────────────────────────────────────────────┤
│  💰 计费配置          [当前模式: token_plan (自动)]     │
│  ◉ 自动   ○ 按量计费   ○ Token 套餐                     │
│                                                         │
│  模型价格表 (CNY / 1k tokens):                           │
│  ┌───────────────┬─────────────────┬──────┬──────┬──────┬──────┐
│  │ 模型           │ 接口             │ 输入 │ 输出 │ 缓存读│ 缓存写│
│  ├───────────────┼─────────────────┼──────┼──────┼──────┼──────┤
│  │MiniMax-M3-512k│chatcompletion-v2│ 0.001│ 0.002│  -   │  -   │
│  │MiniMax-M3-512k│cache-read       │  -   │  -   │0.0005│  -   │
│  │MiniMax-M3-512k│cache-create     │  -   │  -   │  -   │ 0.001│
│  │MiniMax-M2.7   │chatcompletion-v2│0.0001│0.0002│  -   │  -   │
│  │MiniMax-M2.7   │cache-read       │  -   │  -   │0.0000│  -   │
│  │MiniMax-M2.7   │cache-create     │  -   │  -   │  -   │0.0000│
│  │coding-plan-vlm│code_plan_res_pkg│ (未填)│  -  │  -   │  -   │
│  └───────────────┴─────────────────┴──────┴──────┴──────┴──────┘
│  [保存]                                                  │
│  说明: 灰色 "-" = 该 endpoint 类型不适用此字段            │
├────────────────────────────────────────────────────────┤
│  🎨 外观                                                 │
│  ◉ 跟随系统  ○ 浅色  ○ 深色                              │
├────────────────────────────────────────────────────────┤
│  ⚠️ 危险区                                               │
│  [清空所有数据] (需二次确认)                              │
└────────────────────────────────────────────────────────┘
```

价格表 UX 细节：
- 表格的列根据 endpoint 类型动态变化会更友好，但实现复杂。**先做统一 4 列**，不用的字段用 `-` 占位不可编辑（视觉上灰掉）
- 顶部"模型价格表"上方有一个"从数据中拉取"按钮（导入后自动出现），用户点了之后才生成价格表行
- 未配置的 (model, endpoint) 在价格表里显示 0.0000，但在看板里会标记为"未配置"

## 6. 关键流程

### 6.1 导入流程

```
1. 用户拖拽或选择 CSV
   ↓
2. 前端 POST /api/import (multipart/form-data)
   ↓
3. 后端 pandas.read_csv → DataFrame
   ↓
4. 解析 bucket_start:
     parse_bucket("2026-06-01 22:00-23:00") → "2026-06-01 22:00:00"
     失败: 计入 error_rows
   ↓
5. 批量 INSERT OR IGNORE
     依赖唯一索引去重
   ↓
6. 写入 import_history
   ↓
7. 返回 {inserted, skipped, errors, error_details}
   ↓
8. 前端 Toast 显示，前端刷新看板
```

### 6.2 看板查询

- 一次 `GET /api/dashboard` 返回所有聚合数据，前端分发到各图表
- 后端用一个 SQL 拼出所有需要的聚合：

```sql
-- 2 张主卡：累计消费 + 时间范围
SELECT
    COUNT(*) AS total_buckets,
    SUM(cost) AS actual_cost,
    SUM(cost_after_voucher) AS cost_after_voucher,
    SUM(input_tokens) AS total_input,
    SUM(output_tokens) AS total_output,
    MIN(bucket_start) AS earliest,
    MAX(bucket_start) AS latest
FROM usage_records;

-- 每日趋势
SELECT
    DATE(bucket_start) AS day,
    SUM(input_tokens) AS input_tokens,
    SUM(output_tokens) AS output_tokens,
    SUM(total_tokens) AS total_tokens,
    SUM(cost) AS actual_cost
FROM usage_records
GROUP BY DATE(bucket_start)
ORDER BY day;

-- 模型分布
SELECT model, SUM(total_tokens) AS tokens
FROM usage_records GROUP BY model ORDER BY tokens DESC;

-- 接口分布
SELECT endpoint, SUM(total_tokens) AS tokens
FROM usage_records GROUP BY endpoint ORDER BY tokens DESC;

-- 7×24 热力图
SELECT
    CAST(strftime('%w', bucket_start) AS INTEGER) AS dow,
    CAST(strftime('%H', bucket_start) AS INTEGER) AS hour,
    SUM(total_tokens) AS tokens
FROM usage_records
GROUP BY dow, hour;
```

**估算成本计算**（在 Python 层完成，SQL 拉明细再算）：

```python
# 伪代码
def estimate_cost(records: list[dict], pricing: dict[tuple[str, str], dict]) -> Decimal:
    total = Decimal("0")
    for r in records:
        key = (r["model"], r["endpoint"])
        p = pricing.get(key)
        if not p:
            continue  # 未配置
        endpoint = r["endpoint"]
        in_t = r["input_tokens"]
        out_t = r["output_tokens"]
        if endpoint.startswith("chatcompletion"):
            cost = in_t * p["input_price"] + out_t * p["output_price"]
        elif endpoint.startswith("cache-read"):
            cost = in_t * p["cache_read_price"]
        elif endpoint.startswith("cache-create"):
            cost = in_t * p["cache_write_price"]
        else:
            cost = in_t * p["input_price"]
        total += Decimal(cost) / 1000
    return total.quantize(Decimal("0.0001"))
```

每日趋势里的 `estimated_cost` 用同样公式对每日分组求和。

**前端接收的数据结构**：

```json
{
  "summary": {
    "total_buckets": 131,
    "actual_cost": 0.0,
    "estimated_cost": 12.34,
    "total_input_tokens": 12345678,
    "total_output_tokens": 234567,
    "earliest": "2026-05-04T19:00:00",
    "latest": "2026-06-01T22:59:59",
    "billing_mode": "token_plan",
    "billing_mode_source": "auto"
  },
  "daily": [
    {"day": "2026-05-04", "input_tokens": 12345, "output_tokens": 1234, "total_tokens": 13579, "actual_cost": 0, "estimated_cost": 0.05}
  ],
  "by_model": [{"model": "MiniMax-M2.7", "tokens": 1234567}],
  "by_endpoint": [{"endpoint": "chatcompletion-v2(Text API)", "tokens": 2345678}],
  "heatmap": [{"dow": 0, "hour": 14, "tokens": 12345}],
  "unconfigured_pricing": [
    {"model": "coding-plan-vlm", "endpoint": "code_plan_resource_package"}
  ]
}
```

### 6.3 原始数据表

- `GET /api/records?page=1&size=50&model=X&endpoint=Y&date_from=...&date_to=...`
- 默认按 bucket_start DESC 排序
- 不返回全表，前端分页

## 7. 项目结构

```
minimax-usage-dashboard/
├── start.bat                  # 双击启动
├── README.md                  # 使用说明
├── requirements.txt           # Python 依赖
├── pyproject.toml             # 项目元数据（可选）
├── data/
│   └── usage.db               # SQLite 文件（首次运行自动创建）
├── exports/                   # 放待导入的 CSV（可选，用户从网站下载到这里）
│   └── .gitkeep
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI 入口
│   ├── config.py              # 配置（端口、db 路径）
│   ├── db.py                  # SQLite 初始化、连接管理
│   ├── parser.py              # CSV 解析、bucket_start 解析
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── pages.py           # 页面渲染
│   │   └── api.py             # JSON API
│   ├── services/
│   │   ├── __init__.py
│   │   ├── importer.py        # 导入逻辑
│   │   ├── billing.py         # 价格配置、auto 模式判定、估算成本
│   │   └── analytics.py       # 看板聚合 SQL
│   ├── templates/
│   │   ├── base.html          # 布局、主题
│   │   ├── dashboard.html
│   │   └── settings.html
│   └── static/
│       ├── css/
│       │   ├── base.css
│       │   └── themes.css
│       └── js/
│           ├── dashboard.js   # ECharts 图表初始化
│           ├── settings.js    # 导入、设置、价格表交互
│           └── theme.js       # 主题切换
├── tests/
│   ├── test_parser.py
│   ├── test_importer.py
│   ├── test_billing.py
│   └── test_api.py
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-06-05-minimax-usage-dashboard-design.md  # 本文件
└── .gitignore
```

## 8. 错误处理

| 场景 | 处理 |
|------|------|
| CSV 文件不是 UTF-8 | 尝试 `gbk` 编码，失败提示用户转换 |
| CSV 缺少必要列 | 拒绝导入，列出缺失的列名 |
| `消费时间` 格式不识别 | 该行计入 error_rows，前端展示错误样例 |
| 文件过大 (>50MB) | 拒绝导入，提示分批 |
| 数据库写失败 | 整个事务回滚，提示用户重试 |
| 重复导入 | 静默跳过（不报错），仅计数 |
| 看板无数据 | 显示空状态：引导去设置页导入 |

## 9. 主题与样式

- 三种主题：light / dark / system（跟随 prefers-color-scheme）
- 主题存储在 `localStorage`
- CSS 变量管理颜色，主题切换仅切换 class
- 关键色：
  - 主色：#1677ff（蓝）
  - 输入 token：#52c41a（绿）
  - 输出 token：#fa8c16（橙）
  - 失败：#ff4d4f（红）

## 10. 启动与使用

使用 `uv` 管理 Python 环境（防止污染全局 Python）：

```bash
# 首次安装（uv 会自动创建 .venv 并解析依赖）
uv sync

# 启动（开发模式）
uv run uvicorn app.main:app --reload --port 8765

# 启动（生产模式 / 普通用户）
start.bat   # 等价于 uv run uvicorn app.main:app --port 8765

# 访问
http://localhost:8765/
```

使用流程：
1. 打开 MiniMax 平台，导出 CSV
2. 打开 http://localhost:8765/settings
3. 拖入 CSV
4. （可选）填模型价格，配置计费模式
5. 跳到 http://localhost:8765/ 看图表

## 11. 测试策略

| 层 | 测试 | 工具 |
|---|------|------|
| 解析 | `parse_bucket()` 各种格式、脏数据 | pytest |
| 解析 | CSV 读取、空文件、缺列 | pytest + tmp CSV |
| 导入 | 去重逻辑、错误行处理、事务回滚 | pytest + 内存 SQLite |
| API | 每个端点的正常/异常路径 | pytest + FastAPI TestClient |
| 端到端 | 启动服务，curl 关键路径，浏览器手工验证 | 手工 |

不做：
- 浏览器自动化测试（一次性工具）
- 性能/压力测试
- 多用户并发

## 12. 风险与权衡

| 风险 | 缓解 |
|------|------|
| MiniMax 改 CSV 列名 | parser 层做严格校验，缺列明确报错 |
| 多次导入跨 3 个月窗口 | 数据去重 + 增量追加可以无限累积 |
| SQLite 单文件损坏 | 每次启动 WAL checkpoint；建议定期备份 `data/usage.db` |
| 中文列名解析 | 全程 UTF-8，避免编码问题 |
| ECharts CDN 不可达 | 暂不考虑内联（首次实现可接受）；如需可改本地 vendored |

## 13. 实现顺序（高层）

1. 项目脚手架（`requirements.txt`、目录结构、`.gitignore`、`start.bat`）
2. `db.py`：建表（含 `usage_records` / `import_history` / `settings` / `model_pricing`）、连接
3. `parser.py` + 测试：CSV 解析、bucket 解析
4. `importer.py` + 测试：批量写入、去重
5. `services/billing.py` + 测试：价格 CRUD、auto 模式判定、估算成本
6. `analytics.py` + 测试：所有看板聚合 SQL（不含估算，由 billing 层做）
7. `routes/api.py`：所有 JSON 端点（import / dashboard / records / settings / pricing / clear / stats）
8. `templates/base.html` + `static/css`：布局与主题（CNY 货币符号）
9. `templates/dashboard.html` + `dashboard.js`：看板（2 张主卡 + 节省徽章 + 折线 + 饼图×2 + 热力图 + 表格）
10. `templates/settings.html` + `settings.js`：设置（导入 / 历史 / 概览 / 计费（含价格矩阵） / 外观 / 清空）
11. 手工端到端验证（导入 sample CSV、填价格、看节省 / 模式切换）
12. 写 README

## 14. 后续可扩展（不在本次范围）

- 多账号 / 多密钥视图切换
- 数据再导出（CSV / JSON）
- 浏览器自动化拉取（用户授权后）
- 实时刷新（WebSocket）
- 月度对比 / 同比环比
- 预算告警（按模型/总额设阈值）
- 历史价格表（价格调整后保留旧估算）
