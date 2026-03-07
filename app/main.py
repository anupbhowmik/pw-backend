"""Halkhata — FastAPI application entry point."""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth_routes import router as auth_router
from app.api.document_routes import router as document_router
from app.api.insight_routes import router as insight_router
from app.api.middleware import RequestLoggingMiddleware

# Inline logging setup (replaces core/logging.py)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

app = FastAPI(
    title="Halkhata API",
    description="Financial intelligence platform — document extraction, insights, planning",
    version="0.2.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging
app.add_middleware(RequestLoggingMiddleware)

# Routers
app.include_router(auth_router)
app.include_router(document_router)
app.include_router(insight_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
