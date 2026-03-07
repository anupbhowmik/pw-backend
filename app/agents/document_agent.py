"""Document Agent — orchestrates the receipt extraction pipeline using tools."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Document, Transaction
from app.schemas.schemas import ReceiptSchema
from app.tools.tools import (
    db_persist_transaction,
    db_upsert_document,
    llm_extract_receipt,
    llm_parse_ocr_text,
    llm_repair_json,
    normalize_receipt_data,
    ocr_extract_text,
    save_document_file,
    validate_receipt_json,
)

logger = logging.getLogger(__name__)

MIN_OCR_CHARS = 50


@dataclass
class PipelineResult:
    """Outcome of the document processing pipeline."""

    document_id: str = ""
    transaction_id: str = ""
    status: str = "ingested"
    normalized: ReceiptSchema | None = None
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)
    validation_errors: list[dict] = field(default_factory=list)


class DocumentAgent:
    """Processes uploaded receipt images through the full extraction pipeline.

    Pipeline: save → OCR → LLM text parse → validate → repair → normalize → persist
    Fallback: if OCR produces < 50 chars, skip OCR and send image directly to Gemini vision.
    """

    def __init__(self, db: AsyncSession, user_id: str, request_id: str = "") -> None:
        self.db = db
        self.user_id = user_id
        self.request_id = request_id

    async def process(self, image_bytes: bytes, media_type: str) -> PipelineResult:
        result = PipelineResult()

        # 1. Save file
        sha256, file_path = save_document_file(image_bytes, media_type)
        logger.info("[%s] Saved document %s", self.request_id, sha256[:12])

        # 2. Try OCR first
        ocr_text = ocr_extract_text(image_bytes)
        logger.info("[%s] OCR extracted %d chars", self.request_id, len(ocr_text))

        # 3. Choose extraction method
        if len(ocr_text) >= MIN_OCR_CHARS:
            # OCR succeeded — parse text with Gemini
            logger.info("[%s] Using OCR text → Gemini text parsing", self.request_id)
            raw_json, latency_ms = await llm_parse_ocr_text(ocr_text)
        else:
            # OCR failed — fall back to Gemini vision
            logger.info("[%s] OCR insufficient, falling back to Gemini vision", self.request_id)
            raw_json, latency_ms = await llm_extract_receipt(image_bytes, media_type)

        logger.info("[%s] LLM responded in %dms (%d chars)", self.request_id, latency_ms, len(raw_json))

        # 4. Validate
        parsed, errors = validate_receipt_json(raw_json)
        retries = 0

        # 5. Repair loop if needed
        if parsed is None:
            for attempt in range(1, settings.MAX_REPAIR_RETRIES + 1):
                logger.info("[%s] Repair attempt %d", self.request_id, attempt)
                retries = attempt
                raw_json = await llm_repair_json(raw_json, errors)
                parsed, errors = validate_receipt_json(raw_json)
                if parsed is not None:
                    break

        # Failed after retries
        if parsed is None:
            result.status = "failed"
            result.validation_errors = errors
            doc = await db_upsert_document(
                self.db, self.user_id, sha256, file_path,
                "failed", raw_json, latency_ms, retries,
            )
            await self.db.commit()
            result.document_id = doc.id
            return result

        # 6. Normalize
        normalized = normalize_receipt_data(parsed, settings.GEMINI_MODEL)
        logger.info("[%s] Normalized receipt", self.request_id)

        # 7. Persist document
        doc = await db_upsert_document(
            self.db, self.user_id, sha256, file_path,
            "normalized", raw_json, latency_ms, retries,
            confidence=normalized.metadata.confidence,
            warnings=normalized.metadata.warnings,
        )

        # 8. Persist transaction + items
        txn = await db_persist_transaction(self.db, doc, normalized, self.user_id)

        result.document_id = doc.id
        result.transaction_id = txn.id
        result.status = "normalized"
        result.normalized = normalized
        result.confidence = normalized.metadata.confidence
        result.warnings = normalized.metadata.warnings
        logger.info("[%s] Pipeline complete: doc=%s txn=%s", self.request_id, doc.id, txn.id)
        return result
