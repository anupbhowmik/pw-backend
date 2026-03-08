"""Data routes for transaction table operations (list, edit, delete)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Category, Transaction, User
from app.schemas.schemas import (
    DataDeleteResponse,
    DataItemResponse,
    DataItemUpdateRequest,
    DataListResponse,
)

router = APIRouter(prefix="/v1/data", tags=["data"])


@router.get("/items", response_model=DataListResponse)
async def list_data_items(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(Transaction, Category.name)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user.id)
        .order_by(
            Transaction.purchase_date.desc().nullslast(),
            Transaction.created_at.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    items = [
        DataItemResponse(
            id=txn.id,
            merchant_name=txn.merchant_name,
            purchase_date=txn.purchase_date,
            total=txn.total,
            currency=txn.currency,
            payment_method=txn.payment_method,
            category_id=txn.category_id,
            category=category_name,
            created_at=txn.created_at,
        )
        for txn, category_name in rows
    ]

    return DataListResponse(items=items, count=len(items), limit=limit, offset=offset)


@router.put("/items/{item_id}", response_model=DataItemResponse)
async def edit_data_item(
    item_id: str,
    body: DataItemUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(Transaction)
        .where(
            Transaction.id == item_id,
            Transaction.user_id == user.id,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    txn = result.scalar_one_or_none()

    if txn is None:
        raise HTTPException(status_code=404, detail="Item not found")

    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(txn, key, value)

    await db.commit()

    category_name = None
    if txn.category_id is not None:
        cat_stmt = select(Category.name).where(Category.id == txn.category_id).limit(1)
        cat_result = await db.execute(cat_stmt)
        category_name = cat_result.scalar_one_or_none()

    return DataItemResponse(
        id=txn.id,
        merchant_name=txn.merchant_name,
        purchase_date=txn.purchase_date,
        total=txn.total,
        currency=txn.currency,
        payment_method=txn.payment_method,
        category_id=txn.category_id,
        category=category_name,
        created_at=txn.created_at,
    )


@router.delete("/items/{item_id}", response_model=DataDeleteResponse)
async def delete_data_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(Transaction)
        .where(
            Transaction.id == item_id,
            Transaction.user_id == user.id,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    txn = result.scalar_one_or_none()

    if txn is None:
        raise HTTPException(status_code=404, detail="Item not found")

    await db.delete(txn)
    await db.commit()

    return DataDeleteResponse(deleted=True, id=item_id)
