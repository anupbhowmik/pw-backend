"""Data routes for transaction table operations (list, edit, delete)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Category, Transaction, TransactionItem, User
from app.schemas.schemas import (
    DataDeleteResponse,
    DataDetailResponse,
    DataDetailUpdateRequest,
    DataItemResponse,
    DataListResponse,
    TransactionItemResponse,
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


@router.get("/transaction/detail/{transaction_id}", response_model=DataDetailResponse)
async def get_transaction_detail(
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(Transaction, Category.name)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(
            Transaction.id == transaction_id,
            Transaction.user_id == user.id,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    txn, category_name = row

    items_stmt = (
        select(TransactionItem, Category.name)
        .outerjoin(Category, Category.id == TransactionItem.category_id)
        .where(TransactionItem.transaction_id == txn.id)
        .order_by(TransactionItem.line_number.asc().nullslast())
    )
    items_result = await db.execute(items_stmt)
    items = [
        TransactionItemResponse(
            id=item.id,
            line_number=item.line_number,
            description_raw=item.description_raw,
            description_norm=item.description_norm,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=item.total_price,
            category=item_cat_name,
        )
        for item, item_cat_name in items_result.all()
    ]

    return DataDetailResponse(
        id=txn.id,
        merchant_name=txn.merchant_name,
        purchase_date=txn.purchase_date,
        subtotal=txn.subtotal,
        tax=txn.tax,
        total=txn.total,
        currency=txn.currency,
        payment_method=txn.payment_method,
        category_id=txn.category_id,
        category=category_name,
        items=items,
        created_at=txn.created_at,
    )


@router.put("/transaction/edit/{transaction_id}", response_model=DataDetailResponse)
async def edit_transaction_detail(
    transaction_id: str,
    body: DataDetailUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(Transaction)
        .where(
            Transaction.id == transaction_id,
            Transaction.user_id == user.id,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    txn = result.scalar_one_or_none()

    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Validate category_id references
    category_ids_to_check = set()
    txn_updates = body.model_dump(exclude_unset=True, exclude={"items"})
    if "category_id" in txn_updates and txn_updates["category_id"] is not None:
        category_ids_to_check.add(txn_updates["category_id"])
    if body.items is not None:
        for item_update in body.items:
            item_fields = item_update.model_dump(exclude_unset=True)
            if "category_id" in item_fields and item_fields["category_id"] is not None:
                category_ids_to_check.add(item_fields["category_id"])
    if category_ids_to_check:
        cat_check = await db.execute(
            select(Category.id).where(Category.id.in_(category_ids_to_check))
        )
        found_ids = {row[0] for row in cat_check.all()}
        missing = category_ids_to_check - found_ids
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid category_id: {', '.join(str(i) for i in missing)}",
            )

    # Update transaction-level fields
    for key, value in txn_updates.items():
        setattr(txn, key, value)

    # Update line items if provided
    if body.items is not None:
        item_ids = [i.id for i in body.items]
        items_stmt = (
            select(TransactionItem)
            .where(
                TransactionItem.id.in_(item_ids),
                TransactionItem.transaction_id == txn.id,
            )
        )
        items_result = await db.execute(items_stmt)
        item_map = {item.id: item for item in items_result.scalars().all()}

        for item_update in body.items:
            db_item = item_map.get(item_update.id)
            if db_item is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {item_update.id} not found in transaction",
                )
            updates = item_update.model_dump(exclude_unset=True, exclude={"id"})
            for key, value in updates.items():
                setattr(db_item, key, value)

    await db.commit()

    # Fetch category name for response
    category_name = None
    if txn.category_id is not None:
        cat_stmt = select(Category.name).where(Category.id == txn.category_id).limit(1)
        cat_result = await db.execute(cat_stmt)
        category_name = cat_result.scalar_one_or_none()

    # Fetch all items for response
    all_items_stmt = (
        select(TransactionItem, Category.name)
        .outerjoin(Category, Category.id == TransactionItem.category_id)
        .where(TransactionItem.transaction_id == txn.id)
        .order_by(TransactionItem.line_number.asc().nullslast())
    )
    all_items_result = await db.execute(all_items_stmt)
    resp_items = [
        TransactionItemResponse(
            id=item.id,
            line_number=item.line_number,
            description_raw=item.description_raw,
            description_norm=item.description_norm,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=item.total_price,
            category=item_cat_name,
        )
        for item, item_cat_name in all_items_result.all()
    ]

    return DataDetailResponse(
        id=txn.id,
        merchant_name=txn.merchant_name,
        purchase_date=txn.purchase_date,
        subtotal=txn.subtotal,
        tax=txn.tax,
        total=txn.total,
        currency=txn.currency,
        payment_method=txn.payment_method,
        category_id=txn.category_id,
        category=category_name,
        items=resp_items,
        created_at=txn.created_at,
    )


@router.delete("/transaction/{item_id}", response_model=DataDeleteResponse)
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
