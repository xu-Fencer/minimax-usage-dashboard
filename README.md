# MiniMax 用量看板

本地 Web 看板，把 MiniMax 平台导出的 CSV 用量明细做可视化，支持按量计费 / Token 套餐两种模式。

## 特性

- 拖拽导入 MiniMax 导出的 CSV，自动去重（按 11 字段唯一键）
- 累计消费 / 估算价值 / 节省 三大金额卡
- 每日用量趋势 + 模型分布 + 接口分布 + 7×24 热力图 + 原始数据表
- 模型价格表按 `(模型, 接口)` 配置，cache 读 / 写 和普通 chat 单价分开
- 浅色 / 深色 / 跟随系统主题
- 单文件 SQLite，无需安装数据库
- 用 `uv` 管理环境，不污染全局 Python

## 环境要求

- Python 3.10+
- [uv](https://github.com/astral-sh/uv)

## 启动

### Windows（双击）

双击 `start.bat`

### 命令行

```bash
uv sync
uv run uvicorn app.main:app --port 8765
```

打开 http://localhost:8765

## 使用流程

1. 打开 [MiniMax 平台](https://platform.minimaxi.com/console/consumption-detail?tab=api-keys)，导出 CSV（最多 3 个月）
2. 打开 http://localhost:8765/settings
3. 拖入 CSV
4. 点"从数据中拉取模型" → 填入价格（**元 / 百万 tokens**）
5. 打开 http://localhost:8765/dashboard 查看图表

## 计费模式

- **auto**（默认）：自动判断，全 0 → token_plan，否则 → pay_as_you_go
- **pay_as_you_go**：用 CSV 中的实际消费金额
- **token_plan**：用配置价格估算价值，"节省" = 估算价值 - 实际（通常等于估算价值）

## 价格表

按 `(model, endpoint)` 不再分维度，**只按 model**，每个模型 5 个价格字段：

| 字段 | 单位 | 适用 endpoint |
|------|------|---------------|
| **输入价格** | 元 / 百万 tokens | `chatcompletion-v2` 的 input |
| **输出价格** | 元 / 百万 tokens | `chatcompletion-v2` 的 output |
| **缓存读取** | 元 / 百万 tokens | `cache-read` |
| **缓存写入** | 元 / 百万 tokens | `cache-create` |
| **按次价格** | 元 / 次 | 其他（`code_plan_resource_package`、`generate_lyrics`、`image-generation`、`t2a-v2` 等） |

计算时按 endpoint 类型自动选择对应字段；按次计费场景下用 `input_tokens` 字段作为调用次数。

## 数据存储

- 数据库：`data/usage.db`（SQLite）
- 建议定期备份此文件

## 多次导入

MiniMax 限制单次最多导出 3 个月。每月导出一次，看板会自动合并去重。

## 测试

```bash
uv run pytest -v
```

29 个测试覆盖：
- DB schema
- CSV + 时间桶解析
- 批量导入 + 去重
- 价格 CRUD + auto 模式判定 + 估算公式
- 看板聚合 SQL
- 所有 API 端点

## 目录结构

```
app/
├── main.py         # FastAPI 入口
├── config.py       # 配置
├── db.py           # SQLite schema
├── parser.py       # CSV 解析
├── routes/
│   └── api.py      # JSON API
├── services/
│   ├── importer.py # 批量写入 + 去重
│   ├── billing.py  # 价格 + 估算
│   └── analytics.py# 看板聚合
├── templates/      # Jinja2 模板
└── static/         # CSS / JS
tests/
└── ...             # pytest 测试
```

## API

| Method | Path | 用途 |
|--------|------|------|
| GET | `/api/dashboard` | 看板所有数据（一次返回） |
| GET | `/api/records` | 原始数据分页 + 过滤 |
| POST | `/api/import` | 上传 CSV |
| GET / PUT | `/api/settings` | 通用设置（billing_mode, theme） |
| GET / PUT | `/api/pricing` | 价格表 |
| POST | `/api/pricing/sync` | 从数据中拉取 (model, endpoint) 组合 |
| GET | `/api/stats` | 数据概览 |
| GET | `/api/import-history` | 导入历史 |
| POST | `/api/clear?confirm=yes` | 清空所有数据 |

## 许可

仅供个人使用。
