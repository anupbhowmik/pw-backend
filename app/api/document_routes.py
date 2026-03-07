"""Document & transaction routes — upload, extract, process, list, detail."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Category, Document, Transaction, TransactionItem, User
from app.schemas.schemas import (
    DocumentResponse,
    DocumentListResponse,
    ErrorResponse,
    ExtractResponse,
    ExtractionMetadata,
    ItemSchema,
    ProcessRequest,
    ProcessResponse,
    ReceiptSchema,
    StoreSchema,
    TransactionSchema,
    TransactionItemResponse,
    TransactionListResponse,
    TransactionResponse,
)
from app.agents.document_agent import DocumentAgent
from app.services.llm import LLMError
from app.tools.tools import (
    db_persist_transaction,
    db_upsert_document,
    llm_parse_ocr_text,
    llm_repair_json,
    normalize_receipt_data,
    ocr_extract_text,
    save_document_file,
    validate_receipt_json,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["documents"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/jpg"}


# POST /v1/documents/extract
@router.post("/documents/extract", response_model=DocumentResponse, responses={422: {"model": ErrorResponse}})
async def extract_document(
    request: Request,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Full extraction pipeline: uploads an image, runs OCR, parses via LLM, and returns structured receipt data.
    Combines OCR + LLM parsing in a single request — use the two-step endpoints for finer control."""
    request_id: str = getattr(request.state, "request_id", "unknown")

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {file.content_type}")

    image_bytes = await file.read()
    if len(image_bytes) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"File exceeds max size of {settings.MAX_UPLOAD_SIZE} bytes")

    agent = DocumentAgent(db=db, user_id=user.id, request_id=request_id)
    try:
        result = await agent.process(image_bytes, file.content_type or "image/jpeg")
    except LLMError as exc:
        logger.error("[%s] LLM error: %s", request_id, exc)
        status_code = 502 if exc.status_code == 429 else 503
        raise HTTPException(status_code=status_code, detail=f"LLM service error: {exc}")

    if result.status == "failed":
        raise HTTPException(status_code=422, detail="Receipt extraction failed after retries")

    # Build receipt schema for response
    receipt = result.normalized

    return DocumentResponse(
        id=result.document_id,
        user_id=user.id,
        file_type="receipt",
        status=result.status,
        confidence=result.confidence,
        warnings=result.warnings,
        receipt=receipt,
        created_at=datetime.now(timezone.utc),
    )


# POST /v1/documents/ocr_extract
@router.post("/documents/ocr_extract", response_model=ExtractResponse)
async def extract_ocr(
    request: Request,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Runs Tesseract OCR on an uploaded receipt image and stores the raw text.
    No LLM call is made — use /documents/parse to send the OCR text through the LLM."""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {file.content_type}")

    image_bytes = await file.read()
    if len(image_bytes) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"File exceeds max size of {settings.MAX_UPLOAD_SIZE} bytes")

    # 1. Save file to disk
    sha256, file_path = save_document_file(image_bytes, file.content_type or "image/jpeg")

    # 2. Run Tesseract OCR
    ocr_text = ocr_extract_text(image_bytes)

    # 3. Create document record with status "extracted"
    doc = await db_upsert_document(
        db, user.id, sha256, file_path,
        status="extracted",
        raw_json="",
        latency_ms=0,
        retries=0,
    )
    doc.ocr_text = ocr_text
    await db.commit()

    return ExtractResponse(
        document_id=doc.id,
        ocr_text=ocr_text,
        sha256=sha256,
        status="extracted",
    )

# Helpers
def _doc_to_response(doc: Document) -> DocumentResponse:
    """Convert Document ORM row to API response."""
    receipt = None
    if doc.transactions:
        txn = doc.transactions[0]
        items = [
            ItemSchema(
                line_number=it.line_number,
                description_raw=it.description_raw,
                description_norm=it.description_norm,
                quantity=it.quantity,
                unit_price=it.unit_price,
                total_price=it.total_price,
            )
            for it in txn.items
        ]
        receipt = ReceiptSchema(
            store=StoreSchema(
                name=txn.merchant_name,
                city=txn.store_city,
                state=txn.store_state,
            ),
            transaction=TransactionSchema(
                purchase_datetime=txn.purchase_date or txn.created_at,
                subtotal=txn.subtotal or 0,
                tax=txn.tax or 0,
                total=txn.total or 0,
                currency=txn.currency,
                payment_method=txn.payment_method,
            ),
            items=items,
            metadata=ExtractionMetadata(
                extraction_model=doc.extraction_model or "",
                confidence=doc.confidence,
                warnings=doc.warnings or [],
            ),
        )

    return DocumentResponse(
        id=doc.id,
        user_id=doc.user_id,
        file_type=doc.file_type,
        status=doc.status,
        confidence=doc.confidence,
        warnings=doc.warnings or [],
        receipt=receipt,
        created_at=doc.created_at,
    )


def _txn_to_response(txn: Transaction) -> TransactionResponse:
    """Convert Transaction ORM row to API response."""
    return TransactionResponse(
        id=txn.id,
        document_id=txn.document_id,
        merchant_name=txn.merchant_name,
        store_city=txn.store_city,
        store_state=txn.store_state,
        purchase_date=txn.purchase_date,
        subtotal=txn.subtotal,
        tax=txn.tax,
        total=txn.total,
        currency=txn.currency,
        payment_method=txn.payment_method,
        items=[
            TransactionItemResponse(
                id=it.id,
                line_number=it.line_number,
                description_raw=it.description_raw,
                description_norm=it.description_norm,
                quantity=it.quantity,
                unit_price=it.unit_price,
                total_price=it.total_price,
            )
            for it in txn.items
        ],
        created_at=txn.created_at,
    )
