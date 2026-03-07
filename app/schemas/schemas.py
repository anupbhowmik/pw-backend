"""All Pydantic schemas for Halkhata — auth, documents, transactions, insights."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ================================================================== #
# Auth
# ================================================================== #


class GoogleAuthRequest(BaseModel):
    token: str  # Google OAuth ID token from frontend


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    picture: Optional[str] = None
    currency: str
    timezone: str
    created_at: datetime


class AuthContinueResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"


# ================================================================== #
# LLM Extraction (kept from original — used by document pipeline)
# ================================================================== #


class StoreSchema(BaseModel):
    name: str
    store_number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    category: Optional[str] = None


class TransactionSchema(BaseModel):
    purchase_datetime: datetime
    subtotal: float
    tax: float
    total: float
    currency: str = "USD"
    payment_method: Optional[str] = None
    card_last4: Optional[str] = None


class ItemSchema(BaseModel):
    line_number: Optional[int] = None
    description_raw: str
    description_norm: Optional[str] = None
    product_code: Optional[str] = None
    quantity: Optional[float] = None
    weight_lb: Optional[float] = None
    unit_price: Optional[float] = None
    total_price: float
    category: Optional[str] = None
    category_confidence: Optional[float] = None


class ExtractionMetadata(BaseModel):
    source: str = "vision_llm"
    extraction_model: str = ""
    confidence: float = Field(default=1.0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class ReceiptSchema(BaseModel):
    """Full receipt payload — used for LLM output validation AND API response."""

    store: StoreSchema
    transaction: TransactionSchema
    items: list[ItemSchema]
    metadata: ExtractionMetadata = Field(default_factory=ExtractionMetadata)


# ================================================================== #
# Extract / Process (two-step pipeline)
# ================================================================== #


class ExtractResponse(BaseModel):
    """Response from POST /v1/documents/ocr_extract — OCR-only step."""
    document_id: str
    ocr_text: str
    sha256: str
    status: str  # "extracted"


class ProcessRequest(BaseModel):
    """Request body for POST /v1/documents/parse — takes OCR text for LLM parsing."""
    document_id: str
    ocr_text: str


class ProcessResponse(BaseModel):
    """Response from POST /v1/documents/parse — structured receipt data."""
    document_id: str
    transaction_id: str
    status: str
    receipt: ReceiptSchema
    confidence: float
    warnings: list[str] = Field(default_factory=list)


# ================================================================== #
# Document API responses
# ================================================================== #


class DocumentResponse(BaseModel):
    id: str
    user_id: str
    file_type: str
    status: str
    confidence: float
    warnings: list[str] = Field(default_factory=list)
    receipt: Optional[ReceiptSchema] = None
    created_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    count: int


# ================================================================== #
# Transaction API responses
# ================================================================== #


class TransactionItemResponse(BaseModel):
    id: int
    line_number: Optional[int] = None
    description_raw: str
    description_norm: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total_price: float
    category: Optional[str] = None


class TransactionResponse(BaseModel):
    id: str
    document_id: str
    merchant_name: str
    store_city: Optional[str] = None
    store_state: Optional[str] = None
    purchase_date: Optional[datetime] = None
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    currency: str
    payment_method: Optional[str] = None
    category: Optional[str] = None
    items: list[TransactionItemResponse] = Field(default_factory=list)
    created_at: datetime


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    count: int


# ================================================================== #
# Insight schemas
# ================================================================== #


class SpendingSummary(BaseModel):
    category: str
    total_spent: float
    transaction_count: int
    percentage: float = 0.0


class SpendingResponse(BaseModel):
    period: str
    start: datetime
    end: datetime
    total: float
    summaries: list[SpendingSummary]


class InsightResponse(BaseModel):
    id: str
    type: str
    title: str
    desc: str
    severity: str
    details: Optional[str] = None
    is_read: bool
    created_at: datetime


class InsightListResponse(BaseModel):
    insights: list[InsightResponse]
    count: int


# ================================================================== #
# Notification schemas
# ================================================================== #


class NotificationResponse(BaseModel):
    id: str
    type: str
    title: str
    body: str
    channel: str
    is_read: bool
    scheduled_at: Optional[datetime] = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    count: int


class ReminderRequest(BaseModel):
    title: str
    body: str = ""
    scheduled_at: datetime


# ================================================================== #
# Generic
# ================================================================== #


class ErrorResponse(BaseModel):
    detail: str
    errors: list[dict] | None = None
