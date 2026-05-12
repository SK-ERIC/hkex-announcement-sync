# HKEX 公告同步服务

[English](README.md)

独立的后台数据同步服务，自动从港交所披露易平台获取指定港股代码的所有历史及增量公告（PDF + 元数据），并提供 REST API 供官网后台集成。适用于投资者关系模块。

## 功能特性

- **多语言支持** -- 公告数据以三种语言存储：英文（EN）、繁体中文（ZH）、简体中文（CN，通过 OpenCC 自动生成）
- **公告查询 API** -- 专用 `GET /api/bulletin` 接口，支持按语言查询港交所公告
- **语言参数** -- 所有公告接口均支持 `language` 查询参数（`en|zh|cn`），按指定语言返回数据
- **零配置本地开发** -- 默认使用 SQLite，无需任何外部服务即可开始
- **Redis 可选** -- 无 Redis 时同步任务在进程内执行；有 Redis 时通过 Celery 异步执行
- **按股票代码同步** -- 配置一个或多个港股代码（如 `00700`、`09988`），自动获取所有公告元数据
- **全量 + 增量同步** -- 首次运行拉取最近 90 天；后续仅拉取上次同步后的新公告
- **并发 PDF 下载** -- 可配置并发数（默认 5 个 worker）下载英文和中文版公告 PDF，支持失败重试
- **自动去重** -- 基于唯一 `news_id` 自动跳过已同步的公告
- **数据库持久化** -- 支持 SQLite、MySQL、PostgreSQL，通过 SQLAlchemy ORM 管理
- **定时自动同步** -- 通过 Celery Beat 实现定时增量同步（默认每小时，可配置）
- **手动触发 API** -- `POST /api/sync` 按需触发同步，支持指定股票代码和时间范围
- **任务状态追踪** -- 通过 `GET /api/sync/status/{task_id}` 实时查询同步进度
- **REST API 接口** -- 分页列表、详情、公告查询、PDF 下载等接口，供官网后台集成调用
- **三重数据库支持** -- SQLite（默认）、MySQL、PostgreSQL，可通过配置切换
- **双存储支持** -- 本地文件系统或 S3 兼容存储（阿里云 OSS、MinIO、AWS S3 等）
- **Web UI** -- 内置公告浏览界面，支持搜索、分页和语言切换
- **Docker Compose 部署** -- 单容器独立模式或五服务生产模式

## 快速开始

### 方式一：Docker 独立模式（推荐）

最快上手方式 -- 单个容器，无需任何外部依赖。

```bash
# 克隆仓库
git clone https://github.com/SK-ERIC/hkex-announcement-sync.git
cd hkex-announcement-sync

# 创建数据目录
mkdir -p data

# （可选）自定义股票代码和默认语言
# 创建 .env 文件：
# SYNC_STOCK_CODES=00700,09988
# DEFAULT_LANGUAGE=zh

# 启动服务
docker compose -f docker-compose.standalone.yml up -d
```

访问 `http://localhost:8000` 打开 Web UI，或访问 `http://localhost:8000/docs` 查看 API 文档。

**环境变量：**

| 变量                 | 默认值               | 说明                                       |
|----------------------|----------------------|--------------------------------------------|
| `SYNC_STOCK_CODES`   | `00700,09988`        | 逗号分隔的股票代码                          |
| `DEFAULT_LANGUAGE`   | `en`                 | 默认 UI/API 语言（`en`、`zh` 或 `cn`）     |
| `PORT`               | `8000`               | 暴露到宿主机的端口                          |

### 方式二：本地开发（零配置）

无需 MySQL、Redis 或任何外部服务，只需 Python。

```bash
# 安装依赖
uv sync

# 复制配置文件（默认配置可直接使用）
cp .env.example .env

# 启动 API 服务 -- SQLite 数据库自动创建
uvicorn app.main:app --reload
```

访问 `http://localhost:8000` 打开 Web UI，或访问 `http://localhost:8000/docs` 查看 Swagger API 文档。

**触发首次同步：**

```bash
curl -X POST http://localhost:8000/api/sync \
  -H "Content-Type: application/json" \
  -d '{"stock_codes": ["00700"], "mode": "incremental"}'
```

或者在 Web UI 中点击 **Sync Now** 按钮。

### 方式三：Docker Compose（生产部署）

```bash
# 克隆仓库
git clone https://github.com/SK-ERIC/hkex-announcement-sync.git
cd hkex-announcement-sync

# 复制并编辑配置
cp .env.example .env
# 编辑 .env：设置 DATABASE_URL、CELERY_ENABLED=true、股票代码等

# 启动所有服务
docker compose up -d

# 执行数据库迁移（仅 MySQL/PostgreSQL 需要）
docker compose exec api alembic upgrade head
```

启动后包含 5 个服务：

| 服务     | 说明                            | 端口      |
|----------|---------------------------------|-----------|
| `api`    | FastAPI 应用（uvicorn）          | `8000`    |
| `worker` | Celery Worker（执行同步任务）     | --        |
| `beat`   | Celery Beat（定时调度同步）       | --        |
| `db`     | MySQL 8.0                       | `3306`    |
| `redis`  | Redis 7（消息队列）              | `6379`    |

## 系统架构

```text
+---------------------------------------------------------------------+
|                         REST API (FastAPI)                           |
|  /api/sync  /api/sync/status/{id}  /api/announcements  /api/bulletin|
+-----------------------+----------------------------+----------------+
                        |                            |
            +-----------v-----------+     +----------v---------+
            |       同步服务         |     |     查询服务       |
            |                       |     |   （CRUD + 列表）  |
            |   Celery 模式：       |     +----------+---------+
            |   委派到 Worker       |                |
            |                       |     +----------v---------+
            |   内联模式：           |     |   SQLAlchemy       |
            |   进程内直接执行       |     |   （异步 ORM）      |
            +-----------+-----------+     +----------+---------+
                        |                            |
             +----------v-----------+   +------------v---------+
             | +------------------+ |   | SQLite / MySQL /     |
             | |  HKEX 客户端     | |   | PostgreSQL           |
             | |（EN + ZH,        | |   +----------------------+
             | |  JSF 会话）      | |
             | +--------+---------+ |
             | +--------v---------+ |
             | | OpenCC           | |
             | | 繁体 -> 简体转换  | |
             | +--------+---------+ |
             | +--------v---------+ |
             | | PDF 下载器       | |
             | | （EN + ZH）      | |
             | +--------+---------+ |
             | +--------v---------+ |
             | |     存储层       | |
             | |   本地 / S3      | |
             | +------------------+ |
             +----------------------+
```

**两种同步模式：**

| 模式         | 条件                            | 执行方式                                           |
|--------------|---------------------------------|----------------------------------------------------|
| **内联模式** | `CELERY_ENABLED=false`（默认）  | 同步在 API 进程内直接执行                           |
| **Celery**   | `CELERY_ENABLED=true`           | 同步通过 Redis 分发给 Celery Worker                 |

## 项目结构

```text
hkex-announcement-sync/
+-- app/
|   +-- __init__.py
|   +-- main.py                     # FastAPI 应用入口
|   +-- config.py                   # 配置管理（pydantic-settings）
|   +-- database.py                 # SQLAlchemy 异步引擎与会话
|   +-- models/
|   |   +-- __init__.py             # ORM 模型与 Base
|   |   +-- announcement.py         # 公告模型导出
|   +-- schemas/
|   |   +-- __init__.py
|   |   +-- announcement.py         # 公告 Pydantic 数据模型
|   |   +-- sync.py                 # 同步请求/响应数据模型
|   +-- api/
|   |   +-- __init__.py
|   |   +-- router.py               # API 路由汇总
|   |   +-- announcements.py        # 公告查询接口
|   |   +-- bulletin.py             # 公告查询专用接口
|   |   +-- sync.py                 # 同步触发接口
|   +-- services/
|   |   +-- __init__.py
|   |   +-- sync_service.py         # 同步编排逻辑
|   |   +-- announcement_service.py # 公告 CRUD 操作
|   +-- scraper/
|   |   +-- __init__.py
|   |   +-- hkex_client.py          # 港交所 API 客户端（JSF 会话 + JSON，EN & ZH）
|   |   +-- pdf_downloader.py       # 并发 PDF 下载器（EN + ZH）
|   +-- storage/
|   |   +-- __init__.py
|   |   +-- base.py                 # 存储抽象基类
|   |   +-- local.py                # 本地文件系统存储
|   |   +-- s3.py                   # S3 兼容存储
|   |   +-- factory.py              # 存储后端工厂
|   +-- tasks/
|   |   +-- __init__.py
|   |   +-- celery_app.py           # Celery 实例与 Beat 调度配置
|   |   +-- sync_tasks.py           # 同步 Celery 任务
|   +-- static/
|   |   +-- index.html              # Web UI 入口
|   |   +-- style.css               # Web UI 样式
|   |   +-- app.js                  # Web UI 逻辑
|   +-- utils/
|       +-- __init__.py
|       +-- logging.py              # 日志配置
+-- migrations/                     # Alembic 数据库迁移脚本
+-- docker-compose.yml              # 生产部署（5 个服务）
+-- docker-compose.standalone.yml   # 独立部署（单容器）
+-- Dockerfile
+-- pyproject.toml
+-- alembic.ini
+-- .env.example
+-- .mise.toml                      # mise Python 版本配置
```

## API 接口文档

> **API 版本：** 0.1.0

所有公告接口均支持 `language` 查询参数，控制返回数据的语言。

### 触发同步

**`POST /api/sync`**

异步触发同步任务，立即返回任务 ID。

**请求体：**

| 字段          | 类型           | 默认值           | 说明                                               |
|---------------|----------------|------------------|----------------------------------------------------|
| `stock_codes` | `list[string]` | 配置文件默认值    | 要同步的股票代码列表（如 `["00700", "09988"]`）      |
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

| 参数         | 类型     | 默认值  | 说明                              |
|--------------|----------|---------|------------------------------------|
| `stock_code` | `string` | --      | 按股票代码过滤                     |
| `date_from`  | `string` | --      | 起始日期（YYYY-MM-DD）             |
| `date_to`    | `string` | --      | 截止日期（YYYY-MM-DD）             |
| `page`       | `int`    | `1`     | 页码（>= 1）                       |
| `page_size`  | `int`    | `20`    | 每页数量（1-100）                  |
| `language`   | `string` | `en`    | 返回语言：`en`、`zh` 或 `cn`       |

**请求示例：**

```bash
curl "http://localhost:8000/api/announcements?stock_code=00700&page=1&page_size=10&language=en"
```

**响应：**

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "stock_code": "00700",
      "news_id": "202604300007",
      "stock_name": "TENCENT HOLDINGS LTD",
      "title": "MONTHLY RETURN OF EQUITY ISSUER...",
      "filing_type": "Monthly Return",
      "short_text": "...",
      "long_text": "...",
      "hkex_url": "https://www1.hkexnews.hk/listedco/...",
      "file_type": "PDF",
      "file_size": 102400,
      "announcement_date": "2026-04-30T17:00:00",
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

**查询参数：**

| 参数       | 类型     | 默认值  | 说明                              |
|------------|----------|---------|------------------------------------|
| `language` | `string` | `en`    | 返回语言：`en`、`zh` 或 `cn`       |

```bash
curl "http://localhost:8000/api/announcements/550e8400-e29b-41d4-a716-446655440000?language=zh"
```

返回完整的公告记录，包括 `file_hash` 和 `last_synced_at` 字段。

### 下载公告 PDF

**`GET /api/announcements/{id}/download`**

**查询参数：**

| 参数       | 类型     | 默认值  | 说明                             |
|------------|----------|---------|-----------------------------------|
| `language` | `string` | `en`    | PDF 语言：`en` 或 `zh`/`cn`      |

```bash
curl -O "http://localhost:8000/api/announcements/550e8400-e29b-41d4-a716-446655440000/download?language=zh"
```

以文件流方式返回 PDF 文件，包含 `Content-Disposition` 下载头。当 `language=zh` 或 `language=cn` 时，优先返回中文版 PDF，若无则回退到英文版。

### 查询公告（Bulletin）

**`GET /api/bulletin`**

专用公告查询接口，提供结构化的响应格式，专为前端集成设计。

**查询参数：**

| 参数          | 类型     | 默认值  | 说明                                        |
|---------------|----------|---------|----------------------------------------------|
| `symbol`      | `string` | --      | 股票代码，多个用逗号分隔（必填）              |
| `pageindex`   | `int`    | `1`     | 页码（>= 1）                                 |
| `pagesize`    | `int`    | `10`    | 每页数量（1-20）                             |
| `language`    | `string` | `en`    | 返回语言：`en`、`zh` 或 `cn`                 |
| `sortorder`   | `string` | `desc`  | 排序方式：`desc`（最新优先）或 `asc`         |

**请求示例：**

```bash
curl "http://localhost:8000/api/bulletin?symbol=00700&pageindex=1&pagesize=5&language=zh"
```

**响应：**

```json
{
  "data_status": {
    "status_code": 100,
    "status_description": "正常返回",
    "response_date_time": "2026-05-11T10:00:00",
    "data_total_count": 150
  },
  "data": [
    {
      "symbol": "00700",
      "stock_name": "騰訊控股有限公司",
      "title": "月度報表...",
      "short_text": "...",
      "long_text": "...",
      "file_size": "100KB",
      "file_type": "PDF",
      "file_link": "https://www1.hkexnews.hk/listedco/...",
      "bulletin_date_time": "2026-04-30T17:00:00",
      "unique_id": "202604300007"
    }
  ]
}
```

### 健康检查

**`GET /health`**

```json
{ "status": "ok" }
```

## 数据库表结构

### `announcements` 公告表

| 字段                | 类型          | 说明                                                 |
|---------------------|---------------|------------------------------------------------------|
| `id`                | UUID（主键）   | 主键                                                 |
| `stock_code`        | VARCHAR(10)   | 股票代码（如 "00700"）                                |
| `news_id`           | VARCHAR(50)   | 港交所唯一新闻标识                                    |
| `title_en`          | TEXT          | 公告标题（英文）                                      |
| `title_zh`          | TEXT          | 公告标题（繁体中文）                                  |
| `title_cn`          | TEXT          | 公告标题（简体中文，自动生成）                         |
| `stock_name_en`     | VARCHAR(100)  | 公司名称（英文）                                      |
| `stock_name_zh`     | VARCHAR(100)  | 公司名称（繁体中文）                                  |
| `stock_name_cn`     | VARCHAR(100)  | 公司名称（简体中文，自动生成）                         |
| `filing_type_en`    | VARCHAR(50)   | 公告类型（英文）                                      |
| `filing_type_zh`    | VARCHAR(50)   | 公告类型（繁体中文）                                  |
| `filing_type_cn`    | VARCHAR(50)   | 公告类型（简体中文，自动生成）                         |
| `short_text_en`     | TEXT          | 简短描述（英文）                                      |
| `short_text_zh`     | TEXT          | 简短描述（繁体中文）                                  |
| `short_text_cn`     | TEXT          | 简短描述（简体中文，自动生成）                         |
| `long_text_en`      | TEXT          | 详细描述（英文）                                      |
| `long_text_zh`      | TEXT          | 详细描述（繁体中文）                                  |
| `long_text_cn`      | TEXT          | 详细描述（简体中文，自动生成）                         |
| `hkex_url_en`       | TEXT          | 港交所原始链接（英文）                                 |
| `hkex_url_zh`       | TEXT          | 港交所原始链接（中文）                                 |
| `file_path_en`      | TEXT          | 英文 PDF 存储路径                                     |
| `file_path_zh`      | TEXT          | 中文 PDF 存储路径                                     |
| `file_type`         | VARCHAR(10)   | 文件类型（如 "PDF"）                                  |
| `file_size`         | BIGINT        | 文件大小（字节）                                      |
| `file_hash`         | VARCHAR(64)   | 文件 MD5 哈希，用于去重                                |
| `source`            | ENUM          | 同步来源：`"auto"`（自动同步）或 `"manual"`（手动上传） |
| `is_visible`        | BOOLEAN       | 是否显示（默认 `true`）                               |
| `last_synced_at`    | DATETIME      | 最近一次同步时间                                      |
| `created_at`        | DATETIME      | 记录创建时间                                          |
| `updated_at`        | DATETIME      | 记录更新时间                                          |

**唯一约束：** `(stock_code, news_id)` -- 防止同一公告重复入库。

## 配置说明

所有配置项通过环境变量或 `.env` 文件设置。复制 `.env.example` 为 `.env` 并根据需要修改。

### 数据库配置

| 变量           | 默认值                                    | 说明                       |
|----------------|-------------------------------------------|----------------------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/hkex_sync.db` | SQLAlchemy 异步连接字符串  |

**SQLite**（默认，零配置）：

```text
DATABASE_URL=sqlite+aiosqlite:///./data/hkex_sync.db
```

**MySQL**（生产环境）：

```text
DATABASE_URL=mysql+asyncmy://user:password@localhost:3306/hkex_sync
```

**PostgreSQL**（生产环境）：

```text
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/hkex_sync
```

### 任务队列

| 变量                    | 默认值    | 说明                                                      |
|-------------------------|-----------|-----------------------------------------------------------|
| `CELERY_ENABLED`        | `false`   | `false` 时在进程内执行同步；`true` 时使用 Celery Worker   |
| `REDIS_URL`             | 见 .env   | Redis 连接 URL（仅 `CELERY_ENABLED=true` 时需要）         |
| `CELERY_BROKER_URL`     | 见 .env   | Celery 消息代理 URL（仅 `CELERY_ENABLED=true` 时需要）    |
| `CELERY_RESULT_BACKEND` | 见 .env   | Celery 结果后端 URL（仅 `CELERY_ENABLED=true` 时需要）    |

### 存储配置

| 变量                  | 默认值        | 说明                                          |
|-----------------------|---------------|-----------------------------------------------|
| `STORAGE_BACKEND`     | `local`       | 存储方式：`local`（本地）或 `s3`               |
| `STORAGE_LOCAL_PATH`  | `./data/pdfs` | PDF 文件本地存储目录（`local` 模式时生效）      |
| `S3_ENDPOINT`         | --            | S3 兼容存储端点 URL                            |
| `S3_BUCKET`           | --            | S3 存储桶名称                                  |
| `S3_ACCESS_KEY`       | --            | S3 访问密钥                                    |
| `S3_SECRET_KEY`       | --            | S3 密钥                                        |
| `S3_REGION`           | --            | S3 区域                                        |

### 同步配置

| 变量                  | 默认值         | 说明                                        |
|-----------------------|----------------|---------------------------------------------|
| `SYNC_STOCK_CODES`    | `00700`        | 逗号分隔的股票代码列表                        |
| `SYNC_CONCURRENCY`    | `5`            | PDF 并发下载数量                              |
| `SYNC_CRON_SCHEDULE`  | `0 * * * *`    | Celery Beat 定时同步 cron 表达式（默认每小时） |

### API

| 变量               | 默认值 | 说明                                          |
|--------------------|--------|-----------------------------------------------|
| `DEFAULT_LANGUAGE` | `en`   | API 默认返回语言（`en`、`zh` 或 `cn`）         |

### HTTP 客户端配置

| 变量                  | 默认值 | 说明                         |
|-----------------------|--------|------------------------------|
| `HTTP_TIMEOUT`        | `60`   | 请求超时时间（秒）            |
| `HTTP_MAX_RETRIES`    | `3`    | 请求最大重试次数              |
| `HTTP_RETRY_BACKOFF`  | `1.0`  | 指数退避乘数（秒）            |

### 机器人通知

将同步结果和新公告推送到团队群聊机器人。

| 变量                      | 默认值                  | 说明                                                   |
|---------------------------|-------------------------|--------------------------------------------------------|
| `NOTIFIER_ENABLED`        | `false`                 | 启用机器人通知                                          |
| `NOTIFIER_TYPE`           | --                      | 机器人类型：`feishu`、`wecom`、`dingtalk`              |
| `NOTIFIER_ON_SYNC`        | `true`                  | 同步完成后发送通知                                      |
| `NOTIFIER_ON_NEW`         | `true`                  | 有新公告时发送推送                                      |
| `NOTIFIER_FEISHU_WEBHOOK` | --                      | 飞书自定义机器人 Webhook URL                            |
| `NOTIFIER_FEISHU_SECRET`  | --                      | 飞书 Webhook 签名密钥（可选）                           |
| `SITE_URL`                | `http://localhost:8000` | 服务的对外访问地址（用于通知卡片按钮跳转）              |

**飞书机器人配置步骤：**

1. 在飞书群中创建自定义机器人
2. 复制 Webhook 地址和签名校验密钥（可选）
3. 配置环境变量：

```bash
NOTIFIER_ENABLED=true
NOTIFIER_TYPE=feishu
NOTIFIER_FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
NOTIFIER_FEISHU_SECRET=你的签名密钥
SITE_URL=https://你的服务地址
```

通知卡片会根据 `DEFAULT_LANGUAGE` 设置显示对应语言，并支持交互按钮（同步失败时重试、查看全部公告）。

## 同步流程说明

### 双语港交所数据获取

同步流程同时获取英文和繁体中文两种语言的公告数据：

1. **英文获取** -- 使用 `lang=E` 参数查询港交所，获取英文元数据（标题、公司名称、公告类型等）
2. **中文获取** -- 使用 `lang=ZH` 参数查询港交所，获取繁体中文元数据
3. **记录匹配** -- 通过 `DATE_TIME` 字段将英文和中文记录进行匹配，形成双语配对
4. **简体中文生成** -- 使用 [OpenCC](https://github.com/BYVoid/OpenCC) 将繁体中文字段自动转换为简体中文

### 港交所 API 调用流程

港交所搜索 API 使用 JSF 会话机制，需要三步：

1. **GET** 搜索页面（带参数）-- 提取 `ViewState` 和 JSF 表单 `action` URL（包含 `jsessionid`）
2. **POST** 表单 action URL（带 ViewState + 日期范围）-- 初始化服务端搜索会话
3. **GET** JSON API（分页 `rowRange`）-- 获取公告记录

### 首次同步

1. 通过 `prefix.do` API 将股票代码解析为内部 Stock ID
2. 查询最近 90 天至今的公告，按月分块，同时获取英文和中文版本
3. 每个月分块内分页拉取（每页最多 5000 条），直到获取所有结果
4. 通过 `DATE_TIME` 字段匹配英文和中文记录，形成双语配对
5. 通过 OpenCC 将繁体中文字段自动转换为简体中文
6. 解析并标准化为三语公告数据
7. 与数据库已有记录去重（基于 `stock_code` + `news_id`）
8. 将新公告元数据写入数据库
9. 并发下载英文和中文版 PDF 文件（可配置并发数，默认 5）
10. 更新记录的文件路径、文件大小和 MD5 哈希

### 增量同步（后续运行）

流程与首次同步相同，但日期范围从数据库中该股票代码最近一条公告的 `announcement_date` 开始，大幅减少 API 调用次数和处理时间。

### 定时同步

当 `CELERY_ENABLED=true` 时，Celery Beat 默认每小时触发一次增量同步。

## 依赖管理

核心依赖（默认安装）：

```text
fastapi, uvicorn, sqlalchemy, alembic, aiosqlite, pydantic, pydantic-settings,
httpx, tenacity, python-multipart, OpenCC
```

可选依赖组：

| 组         | 安装命令                       | 包含               |
|------------|-------------------------------|--------------------|
| MySQL      | `uv sync --extra mysql`       | asyncmy            |
| PostgreSQL | `uv sync --extra postgres`    | asyncpg            |
| Celery     | `uv sync --extra celery`      | celery, redis      |
| S3         | `uv sync --extra s3`          | boto3              |
| 全部       | `uv sync --extra all`         | 以上所有           |

## 开发指南

### 代码格式化

```bash
uv run ruff check app/
uv run ruff format app/
```

### 数据库迁移

```bash
# 修改模型后生成新的迁移脚本
alembic revision --autogenerate -m "迁移描述"

# 执行迁移（仅 MySQL/PostgreSQL；SQLite 自动建表）
alembic upgrade head

# 回退一个版本
alembic downgrade -1
```

## 许可证

[MIT](LICENSE)
