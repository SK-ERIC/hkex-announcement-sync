# HKEX 公告同步服务

[English](README.md)

独立的后台数据同步服务，自动从港交所披露易平台获取指定港股代码的所有历史及增量公告（PDF + 元数据），并提供 REST API 供官网后台集成。适用于投资者关系模块。

## 功能特性

- **按股票代码同步** — 配置一个或多个港股代码（如 `00700`、`09988`），自动从港交所披露易获取所有公告元数据
- **全量 + 增量同步** — 首次运行拉取全部历史公告（从上市日期至今），后续仅拉取上次同步后的新公告
- **并发 PDF 下载** — 可配置并发数（默认 5 个 worker）下载公告 PDF 文件，支持失败重试
- **自动去重** — 基于公告唯一链接（`stock_code` + `hkex_url`）自动跳过已同步的公告
- **数据库持久化** — 将公告元数据存储到 MySQL 或 PostgreSQL，通过 SQLAlchemy ORM 管理
- **定时自动同步** — 通过 Celery Beat 实现定时增量同步（默认每小时一次，可配置）
- **手动触发 API** — 调用 `POST /api/sync` 按需触发同步，支持指定股票代码和时间范围
- **任务状态追踪** — 通过 `GET /api/sync/status/{task_id}` 实时查询同步进度
- **REST API 接口** — 提供分页列表、详情查询、PDF 下载等接口，供官网后台集成调用
- **双数据库支持** — MySQL（asyncmy）和 PostgreSQL（asyncpg），通过配置切换
- **双存储支持** — 本地文件系统或 S3 兼容存储（阿里云 OSS、MinIO、AWS S3 等）
- **Docker Compose 部署** — 一键启动 API、Celery Worker、Celery Beat、MySQL、Redis

## 系统架构

```
┌──────────────────────────────────────────────────────────┐
│                    REST API (FastAPI)                     │
│  /api/sync  /api/sync/status/{id}  /api/announcements    │
└──────────────┬─────────────────────────────┬─────────────┘
               │                             │
       ┌───────▼───────┐            ┌────────▼────────┐
       │  Celery Worker │            │   查询服务       │
       │  （同步任务）    │            │  （CRUD + 列表） │
       └───────┬───────┘            └────────┬─────────┘
               │                             │
    ┌──────────▼──────────┐        ┌─────────▼──────────┐
    │      同步服务         │        │    SQLAlchemy      │
    │  ┌───────────────┐  │        │    （异步 ORM）      │
    │  │ HKEX 客户端    │  │        └─────────┬──────────┘
    │  │ （API 爬取）   │  │                  │
    │  └───────┬───────┘  │        ┌─────────▼──────────┐
    │  ┌───────▼───────┐  │        │  MySQL / PostgreSQL │
    │  │ PDF 下载器     │  │        └────────────────────┘
    │  │ （并发下载）    │  │
    │  └───────┬───────┘  │
    │  ┌───────▼───────┐  │
    │  │    存储层      │  │
    │  │  本地 / S3     │  │
    │  └───────────────┘  │
    └─────────────────────┘
               │
       ┌───────▼───────┐
       │  Celery Beat   │
       │ （定时同步调度） │
       └───────────────┘
```

## 项目结构

```
hkex-announcement-sync/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI 应用入口
│   ├── config.py                   # 配置管理（pydantic-settings）
│   ├── database.py                 # SQLAlchemy 异步引擎与会话
│   ├── models/
│   │   ├── __init__.py             # ORM 模型与 Base
│   │   └── announcement.py         # 公告模型导出
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── announcement.py         # 公告 Pydantic 数据模型
│   │   └── sync.py                 # 同步请求/响应数据模型
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py               # API 路由汇总
│   │   ├── announcements.py        # 公告查询接口
│   │   └── sync.py                 # 同步触发接口
│   ├── services/
│   │   ├── __init__.py
│   │   ├── sync_service.py         # 同步编排逻辑
│   │   └── announcement_service.py # 公告 CRUD 操作
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── hkex_client.py          # 港交所 API 客户端
│   │   └── pdf_downloader.py       # 并发 PDF 下载器
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── base.py                 # 存储抽象基类
│   │   ├── local.py                # 本地文件系统存储
│   │   ├── s3.py                   # S3 兼容存储
│   │   └── factory.py              # 存储后端工厂
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py           # Celery 实例与 Beat 调度配置
│   │   └── sync_tasks.py           # 同步 Celery 任务
│   └── utils/
│       ├── __init__.py
│       └── logging.py              # 日志配置
├── migrations/                     # Alembic 数据库迁移脚本
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── .env.example
└── .mise.toml                      # mise Python 版本配置
```

## 快速开始

### 环境要求

- [Python 3.12+](https://www.python.org/)（通过 [mise](https://mise.jdx.dev/) 或系统安装）
- [uv](https://docs.astral.sh/uv/) 包管理器
- [Docker](https://www.docker.com/) 和 Docker Compose（容器化部署时需要）

### 方式一：Docker Compose 部署（推荐）

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/hkex-announcement-sync.git
cd hkex-announcement-sync

# 复制并编辑配置文件
cp .env.example .env
# 编辑 .env 文件，设置 SYNC_STOCK_CODES、DATABASE_URL 等参数

# 启动所有服务
docker compose up -d

# 执行数据库迁移
docker compose exec api alembic upgrade head
```

启动后包含 5 个服务：

| 服务     | 说明                            | 端口      |
|----------|---------------------------------|-----------|
| `api`    | FastAPI 应用（uvicorn）          | `8000`    |
| `worker` | Celery Worker（执行同步任务）     | —         |
| `beat`   | Celery Beat（定时调度同步）       | —         |
| `db`     | MySQL 8.0                       | `3306`    |
| `redis`  | Redis 7（消息队列）              | `6379`    |

### 方式二：本地开发

```bash
# 安装 Python 版本（如使用 mise）
mise install

# 安装依赖
uv sync

# 复制并编辑配置文件
cp .env.example .env

# 确保 MySQL 和 Redis 在本地运行，然后执行数据库迁移
alembic upgrade head

# 启动 API 服务
uvicorn app.main:app --reload

# 在另一个终端启动 Celery Worker
celery -A app.tasks.celery_app:celery_app worker --loglevel=info

# 在另一个终端启动 Celery Beat 调度器
celery -A app.tasks.celery_app:celery_app beat --loglevel=info
```

启动后访问 `http://localhost:8000/docs` 可查看 Swagger 交互式 API 文档。

## API 接口文档

### 触发同步

**`POST /api/sync`**

异步触发同步任务，立即返回任务 ID。

**请求体：**

| 字段          | 类型           | 默认值           | 说明                                              |
|---------------|----------------|------------------|---------------------------------------------------|
| `stock_codes` | `list[string]` | 配置文件默认值    | 要同步的股票代码列表（如 `["00700", "09988"]`）     |
| `mode`        | `string`       | `"incremental"`  | 同步模式：`"full"`（全量）或 `"incremental"`（增量） |
| `date_from`   | `date`         | 自动计算          | 起始日期                                           |
| `date_to`     | `date`         | 今天              | 截止日期                                           |

**请求示例：**

```bash
curl -X POST http://localhost:8000/api/sync \
  -H "Content-Type: application/json" \
  -d '{
    "stock_codes": ["00700"],
    "mode": "incremental"
  }'
```

**响应：**

```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 查询同步状态

**`GET /api/sync/status/{task_id}`**

**响应：**

```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "success",
  "progress": {
    "total": 150,
    "synced": 142,
    "skipped": 5,
    "failed": 3
  },
  "error": null
}
```

**`status` 可能的值：** `pending`（等待中）| `running`（执行中）| `success`（成功）| `failed`（失败）

### 获取公告列表

**`GET /api/announcements`**

**查询参数：**

| 参数         | 类型     | 默认值  | 说明                          |
|--------------|----------|---------|-------------------------------|
| `stock_code` | `string` | —       | 按股票代码过滤                 |
| `date_from`  | `string` | —       | 起始日期（YYYY-MM-DD）         |
| `date_to`    | `string` | —       | 截止日期（YYYY-MM-DD）         |
| `page`       | `int`    | `1`     | 页码（>= 1）                   |
| `page_size`  | `int`    | `20`    | 每页数量（1-100）              |

**请求示例：**

```bash
curl "http://localhost:8000/api/announcements?stock_code=00700&page=1&page_size=10"
```

**响应：**

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "stock_code": "00700",
      "stock_name": "TENCENT HOLDINGS LTD",
      "title": "MONTHLY RETURN OF EQUITY ISSUER...",
      "announcement_date": "2026-04-30",
      "filing_type": "Monthly Return",
      "hkex_url": "https://www1.hkexnews.hk/listedco/...",
      "file_path": "/app/data/pdfs/00700/550e8400....pdf",
      "file_size": 102400,
      "source": "auto",
      "is_visible": true,
      "download_url": "/api/announcements/550e8400.../download",
      "created_at": "2026-05-01T10:00:00",
      "updated_at": "2026-05-01T10:00:00"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 10
}
```

### 获取公告详情

**`GET /api/announcements/{id}`**

```bash
curl http://localhost:8000/api/announcements/550e8400-e29b-41d4-a716-446655440000
```

返回完整的公告记录，包括 `file_hash` 和 `last_synced_at` 字段。

### 下载公告 PDF

**`GET /api/announcements/{id}/download`**

```bash
curl -O http://localhost:8000/api/announcements/550e8400-e29b-41d4-a716-446655440000/download
```

以文件流方式返回 PDF 文件，包含 `Content-Disposition` 下载头。

### 健康检查

**`GET /health`**

```json
{ "status": "ok" }
```

## 数据库表结构

### `announcements` 公告表

| 字段                 | 类型          | 说明                                         |
|----------------------|---------------|----------------------------------------------|
| `id`                 | UUID（主键）   | 主键                                         |
| `stock_code`         | VARCHAR(10)   | 股票代码（如 "00700"）                        |
| `stock_name`         | VARCHAR(100)  | 公司名称                                      |
| `title`              | TEXT          | 公告标题                                      |
| `announcement_date`  | DATETIME      | 发布日期                                      |
| `filing_type`        | VARCHAR(50)   | 公告类型（可选）                               |
| `hkex_url`           | TEXT          | 港交所原始链接                                 |
| `file_path`          | TEXT          | 本地存储路径或 S3 Key                          |
| `file_size`          | BIGINT        | 文件大小（字节）                               |
| `file_hash`          | VARCHAR(64)   | 文件 MD5 哈希，用于去重                         |
| `source`             | ENUM          | 同步来源：`"auto"`（自动同步）或 `"manual"`（手动上传） |
| `is_visible`         | BOOLEAN       | 是否显示（默认 `true`）                        |
| `last_synced_at`     | DATETIME      | 最近一次同步时间                               |
| `created_at`         | DATETIME      | 记录创建时间                                   |
| `updated_at`         | DATETIME      | 记录更新时间                                   |

**唯一约束：** `(stock_code, hkex_url)` — 防止同一公告重复入库。

## 配置说明

所有配置项通过环境变量或 `.env` 文件设置。复制 `.env.example` 为 `.env` 并根据需要修改。

### 数据库配置

| 变量           | 默认值                                            | 说明                       |
|----------------|---------------------------------------------------|----------------------------|
| `DATABASE_URL` | `mysql+asyncmy://root:root@localhost:3306/hkex_sync` | SQLAlchemy 异步连接字符串  |

**MySQL 示例：**

```
DATABASE_URL=mysql+asyncmy://user:password@localhost:3306/hkex_sync
```

**PostgreSQL 示例：**

```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/hkex_sync
```

### 存储配置

| 变量                  | 默认值         | 说明                                          |
|-----------------------|----------------|-----------------------------------------------|
| `STORAGE_BACKEND`     | `local`        | 存储方式：`local`（本地）或 `s3`               |
| `STORAGE_LOCAL_PATH`  | `./data/pdfs`  | PDF 文件本地存储目录（`local` 模式时生效）      |
| `S3_ENDPOINT`         | —              | S3 兼容存储端点 URL                            |
| `S3_BUCKET`           | —              | S3 存储桶名称                                  |
| `S3_ACCESS_KEY`       | —              | S3 访问密钥                                    |
| `S3_SECRET_KEY`       | —              | S3 密钥                                        |
| `S3_REGION`           | —              | S3 区域                                        |

### 同步配置

| 变量                  | 默认值        | 说明                                       |
|-----------------------|---------------|--------------------------------------------|
| `SYNC_STOCK_CODES`    | `00700`       | 逗号分隔的股票代码列表                       |
| `SYNC_CONCURRENCY`    | `5`           | PDF 并发下载数量                             |
| `SYNC_CRON_SCHEDULE`  | `0 * * * *`   | Celery Beat 定时同步 cron 表达式（默认每小时） |

### Celery / Redis 配置

| 变量                    | 默认值                             | 说明                  |
|-------------------------|------------------------------------|-----------------------|
| `REDIS_URL`             | `redis://localhost:6379/0`         | Redis 连接 URL         |
| `CELERY_BROKER_URL`     | `redis://localhost:6379/1`         | Celery 消息代理 URL    |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/2`         | Celery 结果后端 URL    |

### HTTP 客户端配置

| 变量                  | 默认值 | 说明                         |
|-----------------------|--------|------------------------------|
| `HTTP_TIMEOUT`        | `60`   | 请求超时时间（秒）            |
| `HTTP_MAX_RETRIES`    | `3`    | 请求最大重试次数              |
| `HTTP_RETRY_BACKOFF`  | `1.0`  | 指数退避乘数（秒）            |

### API 配置

| 变量                | 默认值  | 说明               |
|---------------------|---------|--------------------|
| `API_PREFIX`        | `/api`  | API 路由前缀        |
| `PAGE_SIZE_DEFAULT` | `20`    | 默认分页大小        |
| `PAGE_SIZE_MAX`     | `100`   | 最大分页大小        |

## 同步流程说明

### 全量同步（首次运行）

1. 通过港交所 `prefix.do` API 将股票代码解析为内部 Stock ID
2. 从 `2000-01-01` 至今天按月分块查询公告（港交所 API 限制单次查询约 1 个月）
3. 每个月分块内分页拉取（每页 5000 条），直到获取所有结果
4. 将原始 JSON 记录解析为标准化的公告数据
5. 与数据库已有记录去重（基于 `stock_code` + `hkex_url`）
6. 将新公告元数据写入数据库
7. 并发下载 PDF 文件（可配置并发数，默认 5）
8. 更新记录的文件路径、文件大小和 MD5 哈希

### 增量同步（后续运行）

流程与全量同步相同，但日期范围从数据库中该股票代码最近一条公告的 `announcement_date` 开始，大幅减少 API 调用次数和处理时间。

### 定时同步

Celery Beat 默认每小时触发一次 `scheduled_incremental_sync`，对所有已配置的股票代码执行增量同步。

## 开发指南

### 运行测试

```bash
uv run pytest
```

### 代码格式化

```bash
uv run ruff check app/
uv run ruff format app/
```

### 数据库迁移

```bash
# 修改模型后生成新的迁移脚本
alembic revision --autogenerate -m "迁移描述"

# 执行迁移
alembic upgrade head

# 回退一个版本
alembic downgrade -1
```

## 许可证

[MIT](LICENSE)
