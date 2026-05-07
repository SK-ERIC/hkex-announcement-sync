# HKEX Announcement Sync

[中文文档](README.zh-CN.md)

A standalone backend data synchronization service that automatically fetches all historical and incremental announcements (PDF + metadata) from the Hong Kong Stock Exchange (HKEX) disclosure platform for specified stock codes, and provides a REST API for corporate website integration. Ideal for investor relations modules.

## Features

- **Stock Code Based Sync** — Configure one or more HK stock codes (e.g., `00700`, `09988`) to fetch all published announcement metadata from HKEXnews
- **Full & Incremental Sync** — First-run pulls full history (from listing date to present); subsequent runs only fetch new announcements since the last sync
- **Concurrent PDF Download** — Download announcement PDFs with configurable concurrency (default: 5 workers), with retry on failure
- **Deduplication** — Automatically skip already-synced announcements based on unique URL identifiers
- **Database Persistence** — Store all announcement metadata in MySQL or PostgreSQL via SQLAlchemy ORM
- **Scheduled Auto Sync** — Hourly incremental sync via Celery Beat (configurable schedule)
- **Manual Trigger API** — `POST /api/sync` to trigger on-demand sync with optional stock codes and date range
- **Task Status Tracking** — Poll `GET /api/sync/status/{task_id}` for real-time sync progress
- **REST API** — Paginated list, detail, and PDF download endpoints for website backend integration
- **Dual Database Support** — MySQL (asyncmy) and PostgreSQL (asyncpg), switchable via config
- **Dual Storage Support** — Local filesystem or S3-compatible storage (Aliyun OSS, MinIO, AWS S3, etc.)
- **Docker Compose Deployment** — One command to start API, Celery worker, Celery beat, MySQL, and Redis

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    REST API (FastAPI)                     │
│  /api/sync  /api/sync/status/{id}  /api/announcements    │
└──────────────┬─────────────────────────────┬─────────────┘
               │                             │
       ┌───────▼───────┐            ┌────────▼────────┐
       │  Celery Worker │            │  Query Service   │
       │  (sync tasks)  │            │  (CRUD + list)   │
       └───────┬───────┘            └────────┬─────────┘
               │                             │
    ┌──────────▼──────────┐        ┌─────────▼──────────┐
    │    Sync Service      │        │    SQLAlchemy      │
    │  ┌───────────────┐  │        │    (Async ORM)     │
    │  │ HKEX Client   │  │        └─────────┬──────────┘
    │  │ (scrape API)  │  │                  │
    │  └───────┬───────┘  │        ┌─────────▼──────────┐
    │  ┌───────▼───────┐  │        │  MySQL / PostgreSQL │
    │  │ PDF Downloader│  │        └────────────────────┘
    │  │ (concurrent)  │  │
    │  └───────┬───────┘  │
    │  ┌───────▼───────┐  │
    │  │   Storage     │  │
    │  │ Local / S3    │  │
    │  └───────────────┘  │
    └─────────────────────┘
               │
       ┌───────▼───────┐
       │ Celery Beat    │
       │ (hourly sync)  │
       └───────────────┘
```

## Project Structure

```
hkex-announcement-sync/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application entry
│   ├── config.py                   # Configuration (pydantic-settings)
│   ├── database.py                 # SQLAlchemy async engine & session
│   ├── models/
│   │   ├── __init__.py             # ORM models & Base
│   │   └── announcement.py         # Announcement model exports
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── announcement.py         # Announcement Pydantic schemas
│   │   └── sync.py                 # Sync request/response schemas
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py               # Aggregated API router
│   │   ├── announcements.py        # GET /api/announcements endpoints
│   │   └── sync.py                 # POST /api/sync endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── sync_service.py         # Sync orchestration pipeline
│   │   └── announcement_service.py # Announcement CRUD operations
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── hkex_client.py          # HKEX API client (search + parse)
│   │   └── pdf_downloader.py       # Concurrent PDF downloader
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── base.py                 # Storage abstract base class
│   │   ├── local.py                # Local filesystem storage
│   │   ├── s3.py                   # S3-compatible storage
│   │   └── factory.py              # Storage backend factory
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py           # Celery instance & Beat schedule
│   │   └── sync_tasks.py           # Sync Celery tasks
│   └── utils/
│       ├── __init__.py
│       └── logging.py              # Logging setup
├── migrations/                     # Alembic migration scripts
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── .env.example
└── .mise.toml                      # mise Python version config
```

## Quick Start

### Prerequisites

- [Python 3.12+](https://www.python.org/) (managed via [mise](https://mise.jdx.dev/) or system)
- [uv](https://docs.astral.sh/uv/) package manager
- [Docker](https://www.docker.com/) & Docker Compose (for containerized deployment)

### Option 1: Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/hkex-announcement-sync.git
cd hkex-announcement-sync

# Copy and edit configuration
cp .env.example .env
# Edit .env to set SYNC_STOCK_CODES, DATABASE_URL, etc.

# Start all services
docker compose up -d

# Run database migrations
docker compose exec api alembic upgrade head
```

This starts 5 services:

| Service   | Description                          | Port      |
|-----------|--------------------------------------|-----------|
| `api`     | FastAPI application (uvicorn)        | `8000`    |
| `worker`  | Celery worker (sync task execution)  | —         |
| `beat`    | Celery beat (scheduled sync trigger) | —         |
| `db`      | MySQL 8.0                            | `3306`    |
| `redis`   | Redis 7 (message broker)             | `6379`    |

### Option 2: Local Development

```bash
# Install Python version (if using mise)
mise install

# Install dependencies
uv sync

# Copy and edit configuration
cp .env.example .env

# Ensure MySQL and Redis are running locally, then run migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload

# Start Celery worker (in another terminal)
celery -A app.tasks.celery_app:celery_app worker --loglevel=info

# Start Celery beat scheduler (in another terminal)
celery -A app.tasks.celery_app:celery_app beat --loglevel=info
```

After starting, visit `http://localhost:8000/docs` for the interactive Swagger API documentation.

## API Reference

### Trigger Sync

**`POST /api/sync`**

Trigger a sync task asynchronously. Returns a `task_id` for status polling.

**Request Body:**

| Field         | Type           | Default          | Description                                       |
|---------------|----------------|------------------|---------------------------------------------------|
| `stock_codes` | `list[string]` | Config default   | Stock codes to sync (e.g., `["00700", "09988"]`)  |
| `mode`        | `string`       | `"incremental"`  | Sync mode: `"full"` or `"incremental"`            |
| `date_from`   | `date`         | Auto-calculated  | Start date filter                                  |
| `date_to`     | `date`         | Today            | End date filter                                    |

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

| Parameter    | Type     | Default | Description                      |
|--------------|----------|---------|----------------------------------|
| `stock_code` | `string` | —       | Filter by stock code             |
| `date_from`  | `string` | —       | Start date (YYYY-MM-DD)          |
| `date_to`    | `string` | —       | End date (YYYY-MM-DD)            |
| `page`       | `int`    | `1`     | Page number (>= 1)               |
| `page_size`  | `int`    | `20`    | Items per page (1-100)           |

**Example:**

```bash
curl "http://localhost:8000/api/announcements?stock_code=00700&page=1&page_size=10"
```

**Response:**

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

### Get Announcement Detail

**`GET /api/announcements/{id}`**

```bash
curl http://localhost:8000/api/announcements/550e8400-e29b-41d4-a716-446655440000
```

Returns the full announcement record including `file_hash` and `last_synced_at`.

### Download Announcement PDF

**`GET /api/announcements/{id}/download`**

```bash
curl -O http://localhost:8000/api/announcements/550e8400-e29b-41d4-a716-446655440000/download
```

Returns the PDF file as a download stream with `Content-Disposition` header.

### Health Check

**`GET /health`**

```json
{ "status": "ok" }
```

## Database Schema

### `announcements` Table

| Column              | Type          | Description                                     |
|---------------------|---------------|-------------------------------------------------|
| `id`                | UUID (PK)     | Primary key                                     |
| `stock_code`        | VARCHAR(10)   | Stock code (e.g., "00700")                      |
| `stock_name`        | VARCHAR(100)  | Company name                                    |
| `title`             | TEXT          | Announcement title                              |
| `announcement_date` | DATETIME      | Publication date                                |
| `filing_type`       | VARCHAR(50)   | Announcement category (optional)                |
| `hkex_url`          | TEXT          | Original HKEX link                              |
| `file_path`         | TEXT          | Local or S3 storage path                        |
| `file_size`         | BIGINT        | File size in bytes                              |
| `file_hash`         | VARCHAR(64)   | MD5 hash for deduplication                      |
| `source`            | ENUM          | `"auto"` (synced) or `"manual"` (uploaded)      |
| `is_visible`        | BOOLEAN       | Visibility flag (default: `true`)               |
| `last_synced_at`    | DATETIME      | Last sync timestamp                             |
| `created_at`        | DATETIME      | Record creation time                            |
| `updated_at`        | DATETIME      | Record update time                              |

**Unique Constraint:** `(stock_code, hkex_url)` — prevents duplicate entries for the same announcement.

## Configuration

All settings are configured via environment variables or a `.env` file. Copy `.env.example` to `.env` and customize.

### Database

| Variable       | Default                                          | Description                                      |
|----------------|--------------------------------------------------|--------------------------------------------------|
| `DATABASE_URL` | `mysql+asyncmy://root:root@localhost:3306/hkex_sync` | SQLAlchemy async connection string              |

**MySQL example:**

```
DATABASE_URL=mysql+asyncmy://user:password@localhost:3306/hkex_sync
```

**PostgreSQL example:**

```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/hkex_sync
```

### Storage

| Variable              | Default          | Description                                        |
|-----------------------|------------------|----------------------------------------------------|
| `STORAGE_BACKEND`     | `local`          | Storage type: `local` or `s3`                      |
| `STORAGE_LOCAL_PATH`  | `./data/pdfs`    | Local directory for PDF files (when `local`)        |
| `S3_ENDPOINT`         | —                | S3-compatible endpoint URL                         |
| `S3_BUCKET`           | —                | S3 bucket name                                     |
| `S3_ACCESS_KEY`       | —                | S3 access key                                      |
| `S3_SECRET_KEY`       | —                | S3 secret key                                      |
| `S3_REGION`           | —                | S3 region                                          |

### Sync

| Variable             | Default    | Description                                           |
|----------------------|------------|-------------------------------------------------------|
| `SYNC_STOCK_CODES`   | `00700`    | Comma-separated list of stock codes to sync           |
| `SYNC_CONCURRENCY`   | `5`        | Number of concurrent PDF download workers             |
| `SYNC_CRON_SCHEDULE` | `0 * * * *`| Celery Beat cron schedule (default: every hour)       |

### Celery / Redis

| Variable                 | Default                           | Description                    |
|--------------------------|-----------------------------------|--------------------------------|
| `REDIS_URL`              | `redis://localhost:6379/0`        | Redis connection URL           |
| `CELERY_BROKER_URL`      | `redis://localhost:6379/1`        | Celery broker URL              |
| `CELERY_RESULT_BACKEND`  | `redis://localhost:6379/2`        | Celery result backend URL      |

### HTTP Client

| Variable             | Default | Description                              |
|----------------------|---------|------------------------------------------|
| `HTTP_TIMEOUT`       | `60`    | Request timeout in seconds               |
| `HTTP_MAX_RETRIES`   | `3`     | Maximum retry attempts per request       |
| `HTTP_RETRY_BACKOFF` | `1.0`   | Exponential backoff multiplier (seconds) |

### API

| Variable            | Default | Description                     |
|---------------------|---------|---------------------------------|
| `API_PREFIX`        | `/api`  | API route prefix                |
| `PAGE_SIZE_DEFAULT` | `20`    | Default pagination page size    |
| `PAGE_SIZE_MAX`     | `100`   | Maximum pagination page size    |

## How Sync Works

### Full Sync (First Run)

1. Resolve each stock code to an HKEX internal stock ID via `prefix.do` API
2. Query announcements from `2000-01-01` to today, chunked by month (HKEX API limits queries to ~1 month)
3. Each month chunk is paginated (5000 records per page) until all results are fetched
4. Parse raw JSON records into normalized announcement data
5. Deduplicate against existing database records (by `stock_code` + `hkex_url`)
6. Insert new announcement metadata into the database
7. Download PDF files concurrently (configurable workers, default 5)
8. Update records with file path, size, and MD5 hash

### Incremental Sync (Subsequent Runs)

Same as full sync, but the date range starts from the most recent `announcement_date` in the database for each stock code, significantly reducing API calls and processing time.

### Scheduled Sync

Celery Beat triggers `scheduled_incremental_sync` every hour by default. This calls the same sync pipeline in incremental mode for all configured stock codes.

## Development

### Run Tests

```bash
uv run pytest
```

### Code Formatting

```bash
uv run ruff check app/
uv run ruff format app/
```

### Database Migrations

```bash
# Generate a new migration after model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## License

[MIT](LICENSE)
