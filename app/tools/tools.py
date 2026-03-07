"""All tool functions — stateless, clear input/output. Called by agents."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytesseract
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import (
    Category,
    Document,
    MerchantMaster,
    Transaction,
    TransactionItem,
)
from app.prompts.extraction import (
    EXTRACTION_SYSTEM,
    EXTRACTION_USER,
    EXTRACTION_USER_FROM_OCR,
    REPAIR_SYSTEM,
    build_repair_user_message,
)
from app.schemas.schemas import ReceiptSchema
from app.services.llm import call_text, call_vision
from app.services.normalizer import normalize_receipt, normalize_store_name

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# File tools
# ------------------------------------------------------------------ #


def save_document_file(image_bytes: bytes, media_type: str) -> tuple[str, str]:
    """Hash image with SHA256, save to disk. Returns (sha256, file_path)."""
    sha = hashlib.sha256(image_bytes).hexdigest()
    ext = "png" if "png" in media_type else "jpg"
    img_dir = Path(settings.IMAGE_DIR)
    img_dir.mkdir(parents=True, exist_ok=True)
    dest = img_dir / f"{sha}.{ext}"
    if not dest.exists():
        dest.write_bytes(image_bytes)
    return sha, str(dest)


def ocr_extract_text(image_bytes: bytes) -> str:
    """Run Tesseract OCR on image bytes. Returns raw OCR text string."""
    image = Image.open(BytesIO(image_bytes))
    text = pytesseract.image_to_string(image)
    return text.strip()


# ------------------------------------------------------------------ #
# LLM tools
# ------------------------------------------------------------------ #


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers that LLMs sometimes add."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n", 1)
        text = lines[1] if len(lines) > 1 else ""
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


async def llm_extract_receipt(image_bytes: bytes, media_type: str) -> tuple[str, int]:
    """Call vision model on receipt image. Returns (raw_json_str, latency_ms)."""
    raw, latency = await call_vision(image_bytes, media_type, EXTRACTION_SYSTEM, EXTRACTION_USER)
    return _strip_fences(raw), latency


async def llm_repair_json(raw_json: str, errors: list[dict]) -> str:
    """Ask LLM to fix invalid JSON. Returns repaired JSON string."""
    user_msg = build_repair_user_message(raw_json, errors)
    repaired = await call_text(REPAIR_SYSTEM, user_msg)
    return _strip_fences(repaired)


async def llm_parse_ocr_text(ocr_text: str) -> tuple[str, int]:
    """Send raw OCR text to Gemini for structured receipt parsing. Returns (raw_json, latency_ms)."""
    t0 = time.perf_counter()
    user_msg = EXTRACTION_USER_FROM_OCR.format(ocr_text=ocr_text)
    raw = await call_text(EXTRACTION_SYSTEM, user_msg)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    return _strip_fences(raw), latency_ms


# ------------------------------------------------------------------ #
# Validation tools
# ------------------------------------------------------------------ #


def validate_receipt_json(raw_json: str) -> tuple[ReceiptSchema | None, list[dict]]:
    """Parse and validate raw JSON against ReceiptSchema. Returns (parsed | None, errors)."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        return None, [{"type": "json_decode", "msg": str(exc)}]

    try:
        parsed = ReceiptSchema.model_validate(data)
        return parsed, []
    except ValidationError as exc:
        return None, exc.errors()


# ------------------------------------------------------------------ #
# Normalization tools
# ------------------------------------------------------------------ #


def normalize_receipt_data(parsed: ReceiptSchema, model_name: str) -> ReceiptSchema:
    """Normalize store names, item categories, monetary values."""
    return normalize_receipt(parsed, model_name)


# ------------------------------------------------------------------ #
# DB tools
# ------------------------------------------------------------------ #


async def db_upsert_document(
    db: AsyncSession,
    user_id: str,
    sha256: str,
    file_path: str,
    status: str,
    raw_json: str,
    latency_ms: int,
    retries: int,
    confidence: float = 1.0,
    warnings: list[str] | None = None,
) -> Document:
    """Create or update a document row keyed on sha256."""
    raw_data = None
    try:
        raw_data = json.loads(raw_json)
    except json.JSONDecodeError:
        pass

    stmt = select(Document).where(Document.sha256 == sha256)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if doc is not None:
        doc.status = status
        doc.extraction_raw = raw_data
        doc.extraction_model = settings.GEMINI_MODEL
        doc.extraction_latency_ms = latency_ms
        doc.extraction_retries = retries
        doc.confidence = confidence
        doc.warnings = warnings or []
    else:
        doc = Document(
            user_id=user_id,
            sha256=sha256,
            file_path=file_path,
            status=status,
            extraction_raw=raw_data,
            extraction_model=settings.GEMINI_MODEL,
            extraction_latency_ms=latency_ms,
            extraction_retries=retries,
            confidence=confidence,
            warnings=warnings or [],
        )
        db.add(doc)

    await db.flush()
    return doc


async def db_persist_transaction(
    db: AsyncSession,
    doc: Document,
    normalized: ReceiptSchema,
    user_id: str,
) -> Transaction:
    """Persist a normalized receipt as a Transaction + TransactionItems."""
    nr = normalized

    # Look up or resolve category
    store_cat_slug = None
    _, store_cat = normalize_store_name(nr.store.name)
    if store_cat and store_cat != "unknown":
        store_cat_slug = store_cat

    category_id = None
    if store_cat_slug:
        result = await db.execute(select(Category).where(Category.slug == store_cat_slug))
        cat = result.scalar_one_or_none()
        if cat:
            category_id = cat.id

    txn = Transaction(
        user_id=user_id,
        document_id=doc.id,
        merchant_name=nr.store.name,
        store_city=nr.store.city,
        store_state=nr.store.state,
        purchase_date=nr.transaction.purchase_datetime,
        subtotal=nr.transaction.subtotal,
        tax=nr.transaction.tax,
        total=nr.transaction.total,
        currency=nr.transaction.currency,
        payment_method=nr.transaction.payment_method,
        category_id=category_id,
    )
    db.add(txn)
    await db.flush()

    for it in nr.items:
        item_cat_id = None
        if it.category:
            result = await db.execute(select(Category).where(Category.slug == it.category))
            cat = result.scalar_one_or_none()
            if cat:
                item_cat_id = cat.id

        ti = TransactionItem(
            transaction_id=txn.id,
            line_number=it.line_number,
            description_raw=it.description_raw,
            description_norm=it.description_norm,
            quantity=it.quantity,
            unit_price=it.unit_price,
            total_price=it.total_price,
            category_id=item_cat_id,
        )
        db.add(ti)

    # Update document status
    doc.status = "normalized"
    doc.confidence = nr.metadata.confidence
    doc.warnings = nr.metadata.warnings

    await db.commit()
    return txn


async def db_compute_spending(
    db: AsyncSession,
    user_id: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Compute spending by category for a user in a time range."""
    stmt = (
        select(
            Category.name,
            Category.slug,
            func.coalesce(func.sum(Transaction.total), 0).label("total_spent"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .join(Transaction, Transaction.category_id == Category.id)
        .where(
            Transaction.user_id == user_id,
            Transaction.purchase_date >= start,
            Transaction.purchase_date < end,
        )
        .group_by(Category.id, Category.name, Category.slug)
        .order_by(func.sum(Transaction.total).desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    grand_total = sum(r.total_spent for r in rows) or 1.0
    return [
        {
            "category": r.name,
            "slug": r.slug,
            "total_spent": round(float(r.total_spent), 2),
            "transaction_count": r.transaction_count,
            "percentage": round(float(r.total_spent) / grand_total * 100, 1),
        }
        for r in rows
    ]
