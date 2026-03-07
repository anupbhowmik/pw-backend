# Receipt Extraction API — Clawbot

AI-powered receipt extraction backend. Upload a receipt image, get structured JSON back.

**Pipeline:** Ingest → Extract (Gemini vision) → Validate → Repair → Normalize → Persist → Respond

## Directory Structure

```
ai-backend/
├── app/
│   ├── api/
│   │   ├── middleware.py      # Request logging + request_id
│   │   └── routes.py          # FastAPI endpoints
│   ├── core/
│   │   ├── config.py          # Settings from env vars
│   │   ├── database.py        # Async SQLAlchemy session
│   │   └── logging.py         # Logging setup
│   ├── models/
│   │   └── receipt.py         # SQLAlchemy ORM models
│   ├── prompts/
│   │   └── extraction.py      # LLM system/user prompts
│   ├── schemas/
│   │   └── receipt.py         # Pydantic schemas
│   ├── services/
│   │   ├── clawbot.py         # Orchestrator (pipeline)
│   │   ├── llm.py             # Gemini async client wrapper
│   │   └── normalizer.py      # Store/item normalization + categorization
│   └── main.py                # FastAPI app entry point
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial.py
├── tests/
│   ├── test_api.py
│   ├── test_normalizer.py
│   └── test_schema.py
├── data/images/               # Uploaded receipt images (gitignored)
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
# Edit .env and set your GEMINI_API_KEY
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
curl -X POST http://localhost:8000/v1/receipts/extract \
  -F "file=@receipt.jpg" \
  | python -m json.tool

# Get a stored receipt
curl http://localhost:8000/v1/receipts/{receipt_id} | python -m json.tool

# List receipts with filtering
curl "http://localhost:8000/v1/receipts?merchant=walmart&limit=10" | python -m json.tool
```

## API Endpoints

| Method | Path                          | Description                    |
|--------|-------------------------------|--------------------------------|
| POST   | `/v1/receipts/extract`        | Upload image, extract receipt  |
| GET    | `/v1/receipts/{receipt_id}`   | Get stored receipt by ID       |
| GET    | `/v1/receipts`                | List receipts (filter/paginate)|
| GET    | `/health`                     | Health check                   |

## Example Response

```json
{
  "receipt_id": "a1b2c3d4e5f6...",
  "status": "normalized",
  "receipt": {
    "store": {
      "name": "Walmart",
      "store_number": "4156",
      "city": "Austin",
      "state": "TX"
    },
    "transaction": {
      "purchase_datetime": "2024-03-15T14:32:00",
      "subtotal": 25.47,
      "tax": 2.10,
      "total": 27.57,
      "currency": "USD",
      "payment_method": "VISA",
      "card_last4": "1234"
    },
    "items": [
      {
        "line_number": 1,
        "description_raw": "ORGANIC BANANAS",
        "description_norm": "Organic Bananas",
        "product_code": null,
        "quantity": 3.0,
        "weight_lb": null,
        "unit_price": 0.59,
        "total_price": 1.77,
        "category": "produce",
        "category_confidence": 0.85
      },
      {
        "line_number": 2,
        "description_raw": "2% MILK 1GAL",
        "description_norm": "2% Milk 1Gal",
        "product_code": null,
        "quantity": 1.0,
        "weight_lb": null,
        "unit_price": 3.49,
        "total_price": 3.49,
        "category": "dairy",
        "category_confidence": 0.85
      }
    ],
    "metadata": {
      "source": "vision_llm",
      "extraction_model": "gemini-2.0-flash",
      "confidence": 0.95,
      "warnings": []
    }
  },
  "warnings": [],
  "confidence": 0.95
}
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Alembic Migrations

```bash
# Run migrations (done automatically in Docker)
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"
```

## Environment Variables

| Variable         | Default                                              | Description         |
|------------------|------------------------------------------------------|---------------------|
| `GEMINI_API_KEY` | (required)                                           | Google Gemini API key |
| `DATABASE_URL`   | `postgresql+asyncpg://receipts:receipts@db:5432/receipts` | Async Postgres URL |
| `APP_ENV`        | `development`                                        | Environment name    |
