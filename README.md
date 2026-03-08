# Pennywise Backend API

AI-powered personal finance backend. Upload receipt images for structured extraction, get spending insights, price comparisons, and financial planning — all powered by Google Gemini.

**Core Pipeline:** Ingest → OCR (Tesseract) → Extract (Gemini vision) → Validate → Normalize → Persist → Respond

## Directory Structure

```
pw-backend/
├── app/
│   ├── agents/
│   │   ├── document_agent.py     # Receipt extraction pipeline orchestration
│   │   ├── feed_agent.py         # Price comparisons + transaction summaries
│   │   ├── insight_agent.py      # Spending insights generation
│   │   └── planner_agent.py      # Financial planning chat
│   ├── api/
│   │   ├── middleware.py          # Request logging + request_id
│   │   ├── auth_routes.py        # Google OAuth + JWT authentication
│   │   ├── data_routes.py        # Transaction CRUD (list/detail/edit/delete)
│   │   ├── document_routes.py    # Two-step extraction (OCR + LLM)
│   │   ├── dashboard_routes.py   # Dashboard summary + spending breakdown
│   │   ├── feed_routes.py        # Personalized shopping feed
│   │   ├── insight_routes.py     # Spending insights
│   │   └── planner_routes.py     # Financial planning chat
│   ├── core/
│   │   ├── config.py             # Settings from env vars
│   │   ├── database.py           # Async SQLAlchemy session
│   │   └── security.py           # JWT + Google OAuth verification
│   ├── models/
│   │   ├── base.py               # Base class + helpers
│   │   └── models.py             # ORM models (User, Document, Transaction, etc.)
│   ├── prompts/
│   │   ├── extraction.py         # Receipt extraction prompts
│   │   ├── feed.py               # Feed generation prompts
│   │   ├── insight.py            # Insight generation prompts
│   │   └── planner.py            # Planner chat prompts
│   ├── schemas/
│   │   └── schemas.py            # Pydantic request/response schemas
│   ├── services/
│   │   ├── llm.py                # Google Gemini async client wrapper
│   │   └── normalizer.py         # Store/item normalization + categorization
│   ├── tools/
│   │   └── tools.py              # Stateless extraction/persistence tools
│   └── main.py                   # FastAPI app entry point
├── alembic/
│   └── versions/                  # 7 migration files
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── requirements.txt
└── .env.example
```

## Quick Start

### 1. Configure environment

```bash
cp .env.example .env
```

### 2. Start with Docker Compose

```bash
docker compose up --build
```

This starts Postgres + the API, runs Alembic migrations automatically, and exposes the API on port 8000.

### 3. Test it

```bash
# Health check
curl http://localhost:8000/health

# Extract a receipt (upload an image)
curl -X POST http://localhost:8000/v1/documents/extract \
  -H "Authorization: Bearer <token>" \
  -F "file=@receipt.jpg" \
  | python -m json.tool

# Dashboard summary
curl http://localhost:8000/v1/dashboard/summary \
  -H "Authorization: Bearer <token>" \
  | python -m json.tool
```

## API Endpoints

All endpoints except `/health` and `/v1/auth/google` require a JWT bearer token.

### Authentication

| Method | Path                     | Description                        |
|--------|--------------------------|------------------------------------|
| POST   | `/v1/auth/google`        | Google OAuth login, returns JWT     |
| GET    | `/v1/auth/user/profile`  | Get current user profile            |
| PUT    | `/v1/auth/user/profile`  | Update user profile + budget fields |

### Document Extraction

| Method | Path                        | Description                              |
|--------|-----------------------------|------------------------------------------|
| POST   | `/v1/documents/extract`     | Upload image, full extraction pipeline   |
| POST   | `/v1/documents/ocr_extract` | OCR-only step (returns raw OCR text)     |

### Transaction Data

| Method | Path                                        | Description                      |
|--------|---------------------------------------------|----------------------------------|
| GET    | `/v1/data/items`                            | List transactions (paginated)    |
| GET    | `/v1/data/transaction/detail/{id}`          | Get transaction details + items  |
| PUT    | `/v1/data/transaction/edit/{id}`            | Edit transaction + line items    |
| DELETE | `/v1/data/transaction/{id}`                 | Delete a transaction             |

### Dashboard

| Method | Path                                 | Description                       |
|--------|--------------------------------------|-----------------------------------|
| GET    | `/v1/dashboard/summary`             | Total docs, txns, spending stats  |
| GET    | `/v1/dashboard/spending-by-category` | Spending breakdown by category    |
| GET    | `/v1/dashboard/recent-transactions`  | Recent transaction list           |

### Feed, Insights & Planner

| Method | Path              | Description                                      |
|--------|-------------------|--------------------------------------------------|
| GET    | `/v1/feed`        | Price comparisons + transaction summaries (LLM + web search) |
| GET    | `/v1/insights`    | AI-generated spending insights + trend analysis  |
| POST   | `/v1/planner/chat`| Multi-turn financial planning chat               |

### System

| Method | Path      | Description  |
|--------|-----------|--------------|
| GET    | `/health` | Health check |

## Data Models

| Model              | Description                                    |
|--------------------|------------------------------------------------|
| User               | Google OAuth profile, budget fields             |
| Document           | Receipt image metadata, OCR text, extraction    |
| Category           | 13 system-defined spending categories           |
| MerchantMaster     | Canonical merchant names + category mapping     |
| Transaction        | Receipt-level data (merchant, date, totals)     |
| TransactionItem    | Line items on a receipt                         |
| DerivedUserMetric  | Aggregated spending metrics by period/category  |
| Insight            | AI-generated spending insights                  |
| Notification       | User notifications                              |
| PlannerSession     | Financial planning chat sessions                |


## Alembic Migrations

```bash
# Run migrations (done automatically in Docker)
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"
```

## Environment Variables

| Variable           | Default                                                    | Description              |
|--------------------|------------------------------------------------------------|--------------------------|
| `GEMINI_API_KEY`   | (required)                                                 | Google Gemini API key    |
| `DATABASE_URL`     | `postgresql+asyncpg://receipts:receipts@db:5432/receipts`  | Async Postgres URL       |
| `APP_ENV`          | `development`                                              | Environment name         |
| `GEMINI_MODEL`     | `gemini-3.1-flash-lite-preview`                            | LLM model for extraction |
| `GOOGLE_CLIENT_ID` | (required for auth)                                        | Google OAuth client ID   |
| `JWT_SECRET`       | `change-me-in-production`                                  | JWT signing secret       |
| `JWT_ALGORITHM`    | `HS256`                                                    | JWT algorithm            |
| `JWT_EXPIRE_MINUTES` | `10080` (7 days)                                         | JWT token expiry         |
| `MAX_UPLOAD_SIZE`  | `10485760` (10 MB)                                         | Max upload file size     |
