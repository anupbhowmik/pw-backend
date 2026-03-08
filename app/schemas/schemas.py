"""All Pydantic schemas for Halkhata — auth, documents, transactions, insights."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# Auth
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
    monthly_income: Optional[float] = None
    monthly_rent: Optional[float] = None
    monthly_gym_subscription: Optional[float] = None
    monthly_insurance: Optional[float] = None


class UserProfileUpdateRequest(BaseModel):
    monthly_income: Optional[float] = None
    monthly_rent: Optional[float] = None
    monthly_gym_subscription: Optional[float] = None
    monthly_insurance: Optional[float] = None


class AuthContinueResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"


# LLM Extraction (kept from original — used by document pipeline)
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


# Extract / Process (two-step pipeline)
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


# Document API responses
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


# Transaction API responses
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


# Insight schemas
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

# Dashboard schemas
class DashboardSummaryResponse(BaseModel):
    total_documents: int
    total_transactions: int
    total_spent: float
    average_transaction: float
    last_receipt_total: float
    unread_insights: int


class DashboardCategorySpendItem(BaseModel):
    category: str
    amount: float
    transaction_count: int


class DashboardCategorySpendResponse(BaseModel):
    categories: list[DashboardCategorySpendItem]
    count: int


class DashboardRecentTransactionItem(BaseModel):
    id: str
    merchant_name: str
    total: float
    purchase_date: Optional[datetime] = None
    currency: str


class DashboardRecentTransactionsResponse(BaseModel):
    transactions: list[DashboardRecentTransactionItem]
    count: int


# Data CRUD schemas
class DataItemResponse(BaseModel):
    id: str
    merchant_name: str
    purchase_date: Optional[datetime] = None
    total: Optional[float] = None
    currency: str
    payment_method: Optional[str] = None
    category_id: Optional[int] = None
    category: Optional[str] = None
    created_at: datetime


class DataListResponse(BaseModel):
    items: list[DataItemResponse]
    count: int
    limit: int
    offset: int


class DataItemUpdateRequest(BaseModel):
    merchant_name: Optional[str] = None
    purchase_date: Optional[datetime] = None
    total: Optional[float] = None
    currency: Optional[str] = None
    payment_method: Optional[str] = None
    category_id: Optional[int] = None


class DataDeleteResponse(BaseModel):
    deleted: bool
    id: str


# Feed schemas
class FeedItemResponse(BaseModel):
    type: str  # price_comparison | transaction_summary | empty
    title: str
    desc: str
    # price_comparison fields
    product: Optional[str] = None
    current_store: Optional[str] = None
    current_price: Optional[float] = None
    suggested_store: Optional[str] = None
    suggested_price: Optional[float] = None
    saving: Optional[float] = None
    # transaction_summary fields
    merchant: Optional[str] = None
    total: Optional[float] = None
    item_count: Optional[int] = None
    top_items: list[str] = Field(default_factory=list)
    purchase_date: Optional[str] = None


class FeedListResponse(BaseModel):
    feeds: list[FeedItemResponse]
    count: int


# Planner schemas
class PlannerMessage(BaseModel):
    user: str = ""
    airesponse: str = ""


class PlannerChatRequest(BaseModel):
    messages: list[PlannerMessage]


class PlannerChatResponse(BaseModel):
    response: str


# Generic
class ErrorResponse(BaseModel):
    detail: str
    errors: list[dict] | None = None
