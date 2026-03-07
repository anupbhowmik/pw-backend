"""All ORM models for Halkhata — 10 tables in one file."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_id, utcnow


# ------------------------------------------------------------------ #
# Users
# ------------------------------------------------------------------ #


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    google_id: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(128))
    picture: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    documents: Mapped[list["Document"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    insights: Mapped[list["Insight"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# ------------------------------------------------------------------ #
# Documents (replaces old receipts table)
# ------------------------------------------------------------------ #


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    file_path: Mapped[str] = mapped_column(Text)
    file_type: Mapped[str] = mapped_column(String(20), default="receipt")  # receipt | invoice | pdf
    status: Mapped[str] = mapped_column(String(20), default="ingested")  # ingested | extracted | normalized | failed
    ocr_text: Mapped[str | None] = mapped_column(Text)  # raw Tesseract OCR output
    extraction_raw: Mapped[dict | None] = mapped_column(JSONB)
    extraction_model: Mapped[str | None] = mapped_column(String(64))
    extraction_latency_ms: Mapped[int | None] = mapped_column(Integer)
    extraction_retries: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    warnings: Mapped[list | None] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="documents")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="document", cascade="all, delete-orphan")


# ------------------------------------------------------------------ #
# Categories (seeded with defaults)
# ------------------------------------------------------------------ #


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("categories.id"))
    is_system: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


# ------------------------------------------------------------------ #
# Merchant Master
# ------------------------------------------------------------------ #


class MerchantMaster(Base):
    __tablename__ = "merchant_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_name: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    category_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("categories.id"))
    store_type: Mapped[str | None] = mapped_column(String(64))


# ------------------------------------------------------------------ #
# Transactions (replaces old receipt store/txn fields)
# ------------------------------------------------------------------ #


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(String(32), ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    merchant_name: Mapped[str] = mapped_column(String(256))
    merchant_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("merchant_master.id"))
    store_city: Mapped[str | None] = mapped_column(String(128))
    store_state: Mapped[str | None] = mapped_column(String(64))
    purchase_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    subtotal: Mapped[float | None] = mapped_column(Float)
    tax: Mapped[float | None] = mapped_column(Float)
    total: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    payment_method: Mapped[str | None] = mapped_column(String(64))
    category_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("categories.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="transactions")
    document: Mapped["Document"] = relationship(back_populates="transactions")
    items: Mapped[list["TransactionItem"]] = relationship(back_populates="transaction", cascade="all, delete-orphan")


# ------------------------------------------------------------------ #
# Transaction Items (replaces old line_items)
# ------------------------------------------------------------------ #


class TransactionItem(Base):
    __tablename__ = "transaction_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String(32), ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    line_number: Mapped[int | None] = mapped_column(Integer)
    description_raw: Mapped[str] = mapped_column(Text)
    description_norm: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[float | None] = mapped_column(Float)
    unit_price: Mapped[float | None] = mapped_column(Float)
    total_price: Mapped[float] = mapped_column(Float)
    category_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("categories.id"))

    transaction: Mapped["Transaction"] = relationship(back_populates="items")


# ------------------------------------------------------------------ #
# Derived User Metrics (materialized spending aggregates)
# ------------------------------------------------------------------ #


class DerivedUserMetric(Base):
    __tablename__ = "derived_user_metrics"
    __table_args__ = (
        UniqueConstraint("user_id", "period", "period_start", "category_id", name="uq_user_metric"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    period: Mapped[str] = mapped_column(String(20))  # weekly | monthly | yearly
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    category_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("categories.id"))
    total_spent: Mapped[float] = mapped_column(Float, default=0)
    transaction_count: Mapped[int] = mapped_column(Integer, default=0)


# ------------------------------------------------------------------ #
# Insights
# ------------------------------------------------------------------ #


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(64))  # spending_spike | category_summary | trend
    title: Mapped[str] = mapped_column(String(256))
    desc: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="info")  # info | warning | alert
    details: Mapped[str | None] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="insights")


# ------------------------------------------------------------------ #
# Notifications
# ------------------------------------------------------------------ #


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(64))  # reminder | insight | system
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(20), default="in_app")  # in_app | push | email
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    related_id: Mapped[str | None] = mapped_column(String(32))
    related_type: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="notifications")


# ------------------------------------------------------------------ #
# Planner Sessions (Phase 2 stub)
# ------------------------------------------------------------------ #


class PlannerSession(Base):
    __tablename__ = "planner_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(64))  # budget | event | savings
    title: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | completed | archived
    config: Mapped[dict | None] = mapped_column(JSONB)
    progress: Mapped[dict | None] = mapped_column(JSONB)
    messages: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
