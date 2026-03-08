"""Dashboard routes - simple aggregate data for overview cards/charts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Category, Document, Insight, Notification, Transaction, User
from app.schemas.schemas import (
    DashboardCategorySpendItem,
    DashboardCategorySpendResponse,
    DashboardRecentTransactionItem,
    DashboardRecentTransactionsResponse,
    DashboardSummaryResponse,
)

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    last_month_cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    docs_stmt = select(func.count(Document.id)).where(Document.user_id == user.id)
    txns_stmt = select(func.count(Transaction.id)).where(Transaction.user_id == user.id)
    avg_txn_stmt = select(func.coalesce(func.avg(Transaction.total), 0.0)).where(
        Transaction.user_id == user.id
    )
    total_spent_stmt = select(func.coalesce(func.sum(Transaction.total), 0.0)).where(
        Transaction.user_id == user.id,
        func.coalesce(Transaction.purchase_date, Transaction.created_at) >= last_month_cutoff,
    )
    unread_insights_stmt = select(func.count(Insight.id)).where(
        Insight.user_id == user.id,
        Insight.is_read.is_(False),
    )
    unread_notifications_stmt = select(func.count(Notification.id)).where(
        Notification.user_id == user.id,
        Notification.is_read.is_(False),
    )
    last_receipt_total_stmt = (
        select(Transaction.total)
        .where(Transaction.user_id == user.id)
        .order_by(
            Transaction.purchase_date.desc().nullslast(),
            Transaction.created_at.desc(),
        )
        .limit(1)
    )

    docs_result = await db.execute(docs_stmt)
    txns_result = await db.execute(txns_stmt)
    avg_txn_result = await db.execute(avg_txn_stmt)
    total_spent_result = await db.execute(total_spent_stmt)
    unread_insights_result = await db.execute(unread_insights_stmt)
    unread_notifications_result = await db.execute(unread_notifications_stmt)
    last_receipt_total_result = await db.execute(last_receipt_total_stmt)

    total_documents = int(docs_result.scalar_one() or 0)
    total_transactions = int(txns_result.scalar_one() or 0)
    total_spent = float(total_spent_result.scalar_one() or 0.0)
    average_transaction = float(avg_txn_result.scalar_one() or 0.0)
    last_receipt_total = float(last_receipt_total_result.scalar_one_or_none() or 0.0)

    return DashboardSummaryResponse(
        total_documents=total_documents,
        total_transactions=total_transactions,
        total_spent=round(total_spent, 2),
        average_transaction=round(average_transaction, 2),
        last_receipt_total=round(last_receipt_total, 2),
        unread_insights=int(unread_insights_result.scalar_one() or 0),
        unread_notifications=int(unread_notifications_result.scalar_one() or 0),
    )


@router.get("/spending-by-category", response_model=DashboardCategorySpendResponse)
async def get_spending_by_category(
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(
            func.coalesce(Category.name, "Uncategorized").label("category"),
            func.coalesce(func.sum(Transaction.total), 0.0).label("amount"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user.id)
        .group_by(Category.name)
        .order_by(func.coalesce(func.sum(Transaction.total), 0.0).desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    categories = [
        DashboardCategorySpendItem(
            category=str(row.category),
            amount=round(float(row.amount or 0.0), 2),
            transaction_count=int(row.transaction_count or 0),
        )
        for row in rows
    ]

    return DashboardCategorySpendResponse(categories=categories, count=len(categories))


@router.get("/recent-transactions", response_model=DashboardRecentTransactionsResponse)
async def get_recent_transactions(
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user.id)
        .order_by(
            Transaction.purchase_date.desc().nullslast(),
            Transaction.created_at.desc(),
        )
        .limit(limit)
    )

    result = await db.execute(stmt)
    txns = result.scalars().all()

    transactions = [
        DashboardRecentTransactionItem(
            id=t.id,
            merchant_name=t.merchant_name,
            total=round(float(t.total or 0.0), 2),
            purchase_date=t.purchase_date,
            currency=t.currency,
        )
        for t in txns
    ]

    return DashboardRecentTransactionsResponse(transactions=transactions, count=len(transactions))
