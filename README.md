# HKEX Announcement Sync

[中文文档](README.zh-CN.md)

A standalone backend data synchronization service that automatically fetches all historical and incremental announcements (PDF + metadata) from the Hong Kong Stock Exchange (HKEX) disclosure platform for specified stock codes, and provides a REST API for corporate website integration. Ideal for investor relations modules.

## Features

- **Multilingual Support** -- Announcement data stored in 3 languages: English (EN), Traditional Chinese (ZH), and Simplified Chinese (CN, auto-generated via OpenCC)
- **Bulletin Query API** -- Dedicated `GET /api/bulletin` endpoint for HKEX bulletin queries with language support
- **Language Parameter** -- All announcement APIs accept a `language` query parameter (`en|zh|cn`) to return data in the requested language
- **Zero-Config Local Dev** -- SQLite by default, no external services required to get started
- **Redis Optional** -- Sync tasks run in-process when Redis is not available; delegate to Celery when it is
- **Stock Code Based Sync** -- Configure one or more HK stock codes (e.g., `00700`, `09988`) to fetch all published announcement metadata from HKEXnews
- **Full & Incremental Sync** -- First-run pulls recent 90 days; subsequent runs only fetch new announcements since the last sync
- **Concurrent PDF Download** -- Download announcement PDFs (both EN and ZH versions) with configurable concurrency (default: 5 workers), with retry on failure
- **Deduplication** -- Automatically skip already-synced announcements based on unique `news_id`
- **Database Persistence** -- Store all announcement metadata in SQLite, MySQL, or PostgreSQL via SQLAlchemy ORM
- **Scheduled Auto Sync** -- Hourly incremental sync via Celery Beat (configurable schedule)
- **Manual Trigger API** -- `POST /api/sync` to trigger on-demand sync with optional stock codes and date range
- **Task Status Tracking** -- Poll `GET /api/sync/status/{task_id}` for real-time sync progress
- **REST API** -- Paginated list, detail, bulletin query, and PDF download endpoints for website backend integration
- **Triple Database Support** -- SQLite (default), MySQL, and PostgreSQL, switchable via config
- **Dual Storage Support** -- Local filesystem or S3-compatible storage (Aliyun OSS, MinIO, AWS S3, etc.)
- **Web UI** -- Built-in announcement browsing interface with search, pagination, and language switching
- **Docker Compose Deployment** -- Standalone mode (single container) or production mode (5 services)

## Quick Start

### Option 1: Docker Standalone (Recommended)

The fastest way to get started -- single container, no external dependencies.

```bash
# Clone the repository
git clone https://github.com/SK-ERIC/hkex-announcement-sync.git
cd hkex-announcement-sync

# Create data directory
mkdir -p data

# (Optional) Customize stock codes and default language
# Create a .env file:
# SYNC_STOCK_CODES=00700,09988
# DEFAULT_LANGUAGE=en

# Start the service
docker compose -f docker-compose.standalone.yml up -d
```

Visit `http://localhost:8000` for the Web UI, or `http://localhost:8000/docs` for the API docs.

**Environment variables:**

| Variable             | Default                | Description                                    |
|----------------------|------------------------|------------------------------------------------|
| `SYNC_STOCK_CODES`   | `00700,09988`          | Comma-separated stock codes to sync            |
| `DEFAULT_LANGUAGE`   | `en`                   | Default UI/API language (`en`, `zh`, or `cn`)  |
| `PORT`               | `8000`                 | Host port to expose                            |

### Option 2: Local Development (Zero Config)

No MySQL, Redis, or external services needed. Just Python.

```bash
# Install dependencies
uv sync

# Copy and edit configuration (defaults work out of the box)
cp .env.example .env

# Start API server -- SQLite database is auto-created
uvicorn app.main:app --reload
```

Visit `http://localhost:8000` for the Web UI, or `http://localhost:8000/docs` for the interactive Swagger API documentation.

**Trigger your first sync:**

```bash
curl -X POST http://localhost:8000/api/sync \
  -H "Content-Type: application/json" \
  -d '{"stock_codes": ["00700"], "mode": "incremental"}'
```

Or click **Sync Now** in the Web UI.

### Option 3: Docker Compose (Production)

```bash
# Clone the repository
git clone https://github.com/SK-ERIC/hkex-announcement-sync.git
cd hkex-announcement-sync

# Copy and edit configuration
cp .env.example .env
# Edit .env: set DATABASE_URL, CELERY_ENABLED=true, stock codes, etc.

# Start all services
docker compose up -d

# Run database migrations (MySQL/PostgreSQL only)
docker compose exec api alembic upgrade head
```

This starts 5 services:

| Service   | Description                          | Port      |
|-----------|--------------------------------------|-----------|
| `api`     | FastAPI application (uvicorn)        | `8000`    |
| `worker`  | Celery worker (sync task execution)  | --        |
| `beat`    | Celery beat (scheduled sync trigger) | --        |
| `db`      | MySQL 8.0                            | `3306`    |
| `redis`   | Redis 7 (message broker)             | `6379`    |

## Architecture

```text
+---------------------------------------------------------------------+
|                         REST API (FastAPI)                           |
|  /api/sync  /api/sync/status/{id}  /api/announcements  /api/bulletin|
+-----------------------+----------------------------+----------------+
                        |                            |
            +-----------v-----------+     +----------v---------+
            |     Sync Service      |     |   Query Service    |
            |                       |     |   (CRUD + list)    |
            |   Celery mode:        |     +----------+---------+
            |   delegate to worker  |                |
            |                       |     +----------v---------+
            |   Inline mode:        |     |   SQLAlchemy       |
            |   run directly        |     |   (Async ORM)      |
            +-----------+-----------+     +----------+---------+
                        |                            |
             +----------v-----------+   +------------v---------+
             | +------------------+ |   | SQLite / MySQL /     |
             | |  HKEX Client     | |   | PostgreSQL           |
             | | (EN + ZH,        | |   +----------------------+
             | |  JSF session)    | |
             | +--------+---------+ |
             | +--------v---------+ |
             | | OpenCC           | |
             | | ZH -> CN conv.   | |
             | +--------+---------+ |
             | +--------v---------+ |
             | | PDF Downloader   | |
             | | (EN + ZH)        | |
             | +--------+---------+ |
             | +--------v---------+ |
             | |    Storage       | |
             | |  Local / S3      | |
             | +------------------+ |
             +----------------------+
```

**Two sync modes:**

| Mode        | When                            | How                                                    |
|-------------|---------------------------------|--------------------------------------------------------|
| **Inline**  | `CELERY_ENABLED=false` (default) | Sync runs directly in the API process                  |
| **Celery**  | `CELERY_ENABLED=true`           | Sync is dispatched to Celery worker via Redis          |

## Project Structure

```text
hkex-announcement-sync/
+-- app/
|   +-- __init__.py
|   +-- main.py                     # FastAPI application entry
|   +-- config.py                   # Configuration (pydantic-settings)
|   +-- database.py                 # SQLAlchemy async engine & session
|   +-- models/
|   |   +-- __init__.py             # ORM models & Base
|   |   +-- announcement.py         # Announcement model exports
|   +-- schemas/
|   |   +-- __init__.py
|   |   +-- announcement.py         # Announcement Pydantic schemas
|   |   +-- sync.py                 # Sync request/response schemas
|   +-- api/
|   |   +-- __init__.py
|   |   +-- router.py               # Aggregated API router
|   |   +-- announcements.py        # GET /api/announcements endpoints
|   |   +-- bulletin.py             # GET /api/bulletin endpoint
|   |   +-- sync.py                 # POST /api/sync endpoints
|   +-- services/
|   |   +-- __init__.py
|   |   +-- sync_service.py         # Sync orchestration pipeline
|   |   +-- announcement_service.py # Announcement CRUD operations
|   +-- scraper/
|   |   +-- __init__.py
|   |   +-- hkex_client.py          # HKEX API client (JSF session + JSON, EN & ZH)
|   |   +-- pdf_downloader.py       # Concurrent PDF downloader (EN + ZH)
|   +-- storage/
|   |   +-- __init__.py
|   |   +-- base.py                 # Storage abstract base class
|   |   +-- local.py                # Local filesystem storage
|   |   +-- s3.py                   # S3-compatible storage
|   |   +-- factory.py              # Storage backend factory
|   +-- tasks/
|   |   +-- __init__.py
|   |   +-- celery_app.py           # Celery instance & Beat schedule
|   |   +-- sync_tasks.py           # Sync Celery tasks
|   +-- static/
|   |   +-- index.html              # Web UI entry
|   |   +-- style.css               # Web UI styles
|   |   +-- app.js                  # Web UI logic
|   +-- utils/
|       +-- __init__.py
|       +-- logging.py              # Logging setup
+-- migrations/                     # Alembic migration scripts
+-- docker-compose.yml              # Production deployment (5 services)
+-- docker-compose.standalone.yml   # Standalone deployment (single container)
+-- Dockerfile
+-- pyproject.toml
+-- alembic.ini
+-- .env.example
+-- .mise.toml                      # mise Python version config
```

## API Reference

> **API Version:** 0.1.0

All announcement endpoints accept a `language` query parameter to control the language of returned data.

### Trigger Sync

**`POST /api/sync`**

Trigger a sync task asynchronously. Returns a `task_id` for status polling.

**Request Body:**

| Field         | Type           | Default          | Description                                        |
|---------------|----------------|------------------|----------------------------------------------------|
| `stock_codes` | `list[string]` | Config default   | Stock codes to sync (e.g., `["00700", "09988"]`)   |
| `mode`        | `string`       | `"incremental"`  | Sync mode: `"full"` or `"incremental"`             |
| `date_from`   | `date`         | Auto-calculated  | Start date filter                                   |
| `date_to`     | `date`         | Today            | End date filter                                     |

**Example:**

```bash
curl -X POST http://localhost:8000/api/sync \
  -H "Content-Type: application/json" \
  -d '{
    "stock_codes": ["00700"],
    "mode": "incremental"
  }'
```

**Response:**

```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### Query Sync Status

**`GET /api/sync/status/{task_id}`**

**Response:**

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

**`status` values:** `pending` | `running` | `success` | `failed`

### List Announcements

**`GET /api/announcements`**

**Query Parameters:**

| Parameter    | Type     | Default | Description                            |
|--------------|----------|---------|----------------------------------------|
| `stock_code` | `string` | --      | Filter by stock code                   |
| `date_from`  | `string` | --      | Start date (YYYY-MM-DD)                |
| `date_to`    | `string` | --      | End date (YYYY-MM-DD)                  |
| `page`       | `int`    | `1`     | Page number (>= 1)                     |
| `page_size`  | `int`    | `20`    | Items per page (1-100)                 |
| `language`   | `string` | `en`    | Response language: `en`, `zh`, or `cn` |

**Example:**

```bash
curl "http://localhost:8000/api/announcements?stock_code=00700&page=1&page_size=10&language=en"
```

**Response:**

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

### Get Announcement Detail

**`GET /api/announcements/{id}`**

**Query Parameters:**

| Parameter  | Type     | Default | Description                            |
|------------|----------|---------|----------------------------------------|
| `language` | `string` | `en`    | Response language: `en`, `zh`, or `cn` |

```bash
curl "http://localhost:8000/api/announcements/550e8400-e29b-41d4-a716-446655440000?language=zh"
```

Returns the full announcement record including `file_hash` and `last_synced_at`.

### Download Announcement PDF

**`GET /api/announcements/{id}/download`**

**Query Parameters:**

| Parameter  | Type     | Default | Description                           |
|------------|----------|---------|---------------------------------------|
| `language` | `string` | `en`    | PDF language: `en` or `zh`/`cn`      |

```bash
curl -O "http://localhost:8000/api/announcements/550e8400-e29b-41d4-a716-446655440000/download?language=zh"
```

Returns the PDF file as a download stream with `Content-Disposition` header. When `language=zh` or `language=cn`, returns the Chinese PDF if available, otherwise falls back to the English version.

### Query Bulletins

**`GET /api/bulletin`**

A dedicated endpoint for querying HKEX bulletins with a structured response format, designed for frontend integration.

**Query Parameters:**

| Parameter    | Type     | Default | Description                                     |
|--------------|----------|---------|-------------------------------------------------|
| `symbol`     | `string` | --      | Stock code(s), comma-separated (required)       |
| `pageindex`  | `int`    | `1`     | Page index (>= 1)                               |
| `pagesize`   | `int`    | `10`    | Items per page (1-20)                           |
| `language`   | `string` | `en`    | Response language: `en`, `zh`, or `cn`          |
| `sortorder`  | `string` | `desc`  | Sort order: `desc` (newest first) or `asc`      |

**Example:**

```bash
curl "http://localhost:8000/api/bulletin?symbol=00700&pageindex=1&pagesize=5&language=zh"
```

**Response:**

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

### Health Check

**`GET /health`**

```json
{ "status": "ok" }
```

## Database Schema

### `announcements` Table

| Column              | Type          | Description                                              |
|---------------------|---------------|----------------------------------------------------------|
| `id`                | UUID (PK)     | Primary key                                              |
| `stock_code`        | VARCHAR(10)   | Stock code (e.g., "00700")                               |
| `news_id`           | VARCHAR(50)   | HKEX unique news identifier                              |
| `title_en`          | TEXT          | Announcement title (English)                             |
| `title_zh`          | TEXT          | Announcement title (Traditional Chinese)                 |
| `title_cn`          | TEXT          | Announcement title (Simplified Chinese, auto-generated)  |
| `stock_name_en`     | VARCHAR(100)  | Company name (English)                                   |
| `stock_name_zh`     | VARCHAR(100)  | Company name (Traditional Chinese)                       |
| `stock_name_cn`     | VARCHAR(100)  | Company name (Simplified Chinese, auto-generated)        |
| `filing_type_en`    | VARCHAR(50)   | Announcement category (English)                          |
| `filing_type_zh`    | VARCHAR(50)   | Announcement category (Traditional Chinese)              |
| `filing_type_cn`    | VARCHAR(50)   | Announcement category (Simplified Chinese, auto-gen.)    |
| `short_text_en`     | TEXT          | Short description (English)                              |
| `short_text_zh`     | TEXT          | Short description (Traditional Chinese)                  |
| `short_text_cn`     | TEXT          | Short description (Simplified Chinese, auto-generated)   |
| `long_text_en`      | TEXT          | Long description (English)                               |
| `long_text_zh`      | TEXT          | Long description (Traditional Chinese)                   |
| `long_text_cn`      | TEXT          | Long description (Simplified Chinese, auto-generated)    |
| `hkex_url_en`       | TEXT          | Original HKEX link (English)                             |
| `hkex_url_zh`       | TEXT          | Original HKEX link (Chinese)                             |
| `file_path_en`      | TEXT          | Storage path for English PDF                             |
| `file_path_zh`      | TEXT          | Storage path for Chinese PDF                             |
| `file_type`         | VARCHAR(10)   | File type (e.g., "PDF")                                  |
| `file_size`         | BIGINT        | File size in bytes                                       |
| `file_hash`         | VARCHAR(64)   | MD5 hash for deduplication                               |
| `source`            | ENUM          | `"auto"` (synced) or `"manual"` (uploaded)               |
| `is_visible`        | BOOLEAN       | Visibility flag (default: `true`)                        |
| `last_synced_at`    | DATETIME      | Last sync timestamp                                      |
| `created_at`        | DATETIME      | Record creation time                                     |
| `updated_at`        | DATETIME      | Record update time                                       |

**Unique Constraint:** `(stock_code, news_id)` -- prevents duplicate entries for the same announcement.

## Configuration

All settings are configured via environment variables or a `.env` file. Copy `.env.example` to `.env` and customize.

### Database

| Variable       | Default                                    | Description                        |
|----------------|--------------------------------------------|------------------------------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/hkex_sync.db` | SQLAlchemy async connection string |

**SQLite** (default, zero-config):

```text
DATABASE_URL=sqlite+aiosqlite:///./data/hkex_sync.db
```

**MySQL** (for production):

```text
DATABASE_URL=mysql+asyncmy://user:password@localhost:3306/hkex_sync
```

**PostgreSQL** (for production):

```text
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/hkex_sync
```

### Task Queue

| Variable                | Default   | Description                                                      |
|-------------------------|-----------|------------------------------------------------------------------|
| `CELERY_ENABLED`        | `false`   | When `false`, sync runs in-process. When `true`, uses Celery.    |
| `REDIS_URL`             | see .env  | Redis connection URL (only needed when `CELERY_ENABLED=true`)    |
| `CELERY_BROKER_URL`     | see .env  | Celery broker URL (only needed when `CELERY_ENABLED=true`)       |
| `CELERY_RESULT_BACKEND` | see .env  | Celery result backend URL (only needed when `CELERY_ENABLED=true`)|

### Storage

| Variable              | Default        | Description                                         |
|-----------------------|----------------|-----------------------------------------------------|
| `STORAGE_BACKEND`     | `local`        | Storage type: `local` or `s3`                       |
| `STORAGE_LOCAL_PATH`  | `./data/pdfs`  | Local directory for PDF files (when `local`)         |
| `S3_ENDPOINT`         | --             | S3-compatible endpoint URL                          |
| `S3_BUCKET`           | --             | S3 bucket name                                      |
| `S3_ACCESS_KEY`       | --             | S3 access key                                       |
| `S3_SECRET_KEY`       | --             | S3 secret key                                       |
| `S3_REGION`           | --             | S3 region                                           |

### Sync

| Variable             | Default       | Description                                          |
|----------------------|---------------|------------------------------------------------------|
| `SYNC_STOCK_CODES`   | `00700`       | Comma-separated list of stock codes to sync          |
| `SYNC_CONCURRENCY`   | `5`           | Number of concurrent PDF download workers            |
| `SYNC_CRON_SCHEDULE` | `0 * * * *`   | Celery Beat cron schedule (default: every hour)      |

### API

| Variable           | Default | Description                                       |
|--------------------|---------|---------------------------------------------------|
| `DEFAULT_LANGUAGE` | `en`    | Default language for API responses (`en`, `zh`, or `cn`)|

### HTTP Client

| Variable             | Default | Description                              |
|----------------------|---------|------------------------------------------|
| `HTTP_TIMEOUT`       | `60`    | Request timeout in seconds               |
| `HTTP_MAX_RETRIES`   | `3`     | Maximum retry attempts per request       |
| `HTTP_RETRY_BACKOFF` | `1.0`   | Exponential backoff multiplier (seconds) |

### Notification

Send sync results and new announcement alerts to team chat bots.

| Variable                  | Default                | Description                                                  |
|---------------------------|------------------------|--------------------------------------------------------------|
| `NOTIFIER_ENABLED`        | `false`                | Enable bot notifications                                     |
| `NOTIFIER_TYPE`           | --                     | Bot type: `feishu`, `wecom`, `dingtalk`                     |
| `NOTIFIER_ON_SYNC`        | `true`                 | Send notification on sync completion                         |
| `NOTIFIER_ON_NEW`         | `true`                 | Send notification when new announcements are synced          |
| `NOTIFIER_FEISHU_WEBHOOK` | --                     | Feishu/Lark custom bot webhook URL                           |
| `NOTIFIER_FEISHU_SECRET`  | --                     | Feishu webhook sign secret (optional)                        |
| `SITE_URL`                | `http://localhost:8000`| Public URL of this service (used in notification buttons)    |

**Feishu (Lark) setup:**

1. Create a custom bot in your Feishu group
2. Copy the webhook URL and optional sign secret
3. Configure environment variables:

```bash
NOTIFIER_ENABLED=true
NOTIFIER_TYPE=feishu
NOTIFIER_FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
NOTIFIER_FEISHU_SECRET=your_sign_secret
SITE_URL=https://your-service-url.com
```

Notification cards follow the `DEFAULT_LANGUAGE` setting and support interactive buttons (retry on failure, view all announcements).

## How Sync Works

### Bilingual HKEX Fetching

The sync process fetches announcement data in both English and Traditional Chinese from HKEX:

1. **English fetch** -- Queries HKEX with `lang=E` to get English metadata (title, stock name, filing type, etc.)
2. **Chinese fetch** -- Queries HKEX with `lang=ZH` to get Traditional Chinese metadata
3. **Matching** -- EN and ZH records are matched by `DATE_TIME` to create paired bilingual entries
4. **Simplified Chinese generation** -- Traditional Chinese fields are automatically converted to Simplified Chinese using [OpenCC](https://github.com/BYVoid/OpenCC)

### HKEX API Flow

The HKEX search API requires a JSF session-based approach:

1. **GET** search page with parameters -- extracts `ViewState` and JSF form `action` URL (contains `jsessionid`)
2. **POST** the form action URL with `ViewState` + date range -- initializes the server-side search session
3. **GET** the JSON API with pagination (`rowRange`) -- fetches announcement records

### Full Sync (First Run)

1. Resolve each stock code to an HKEX internal stock ID via `prefix.do` API
2. Query announcements from the last 90 days to today, chunked by month, in both EN and ZH
3. Each month chunk is paginated (up to 5000 records per page) until all results are fetched
4. Match EN and ZH records by `DATE_TIME` to create bilingual pairs
5. Auto-generate Simplified Chinese (CN) fields from Traditional Chinese (ZH) via OpenCC
6. Parse and normalize into trilingual announcement data
7. Deduplicate against existing database records (by `stock_code` + `news_id`)
8. Insert new announcement metadata into the database
9. Download both EN and ZH PDF files concurrently (configurable workers, default 5)
10. Update records with file paths, file sizes, and MD5 hashes

### Incremental Sync (Subsequent Runs)

Same as full sync, but the date range starts from the most recent `announcement_date` in the database for each stock code, significantly reducing API calls and processing time.

### Scheduled Sync

When `CELERY_ENABLED=true`, Celery Beat triggers `scheduled_incremental_sync` every hour by default.

## Dependencies

Core dependencies (installed by default):

```text
fastapi, uvicorn, sqlalchemy, alembic, aiosqlite, pydantic, pydantic-settings,
httpx, tenacity, python-multipart, OpenCC
```

Optional dependency groups:

| Group       | Install                       | Includes               |
|-------------|-------------------------------|------------------------|
| MySQL       | `uv sync --extra mysql`       | asyncmy                |
| PostgreSQL  | `uv sync --extra postgres`    | asyncpg                |
| Celery      | `uv sync --extra celery`      | celery, redis          |
| S3          | `uv sync --extra s3`          | boto3                  |
| All         | `uv sync --extra all`         | all of the above       |

## Development

### Code Formatting

```bash
uv run ruff check app/
uv run ruff format app/
```

### Database Migrations

```bash
# Generate a new migration after model changes
alembic revision --autogenerate -m "description"

# Apply migrations (MySQL/PostgreSQL only; SQLite auto-creates tables)
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## License

[MIT](LICENSE)
