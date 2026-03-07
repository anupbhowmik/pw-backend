"""Initial schema: receipts + line_items

Revision ID: 001
Revises:
Create Date: 2026-03-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "receipts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("sha256", sa.String(64), unique=True, index=True, nullable=False),
        sa.Column("image_path", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ingested"),
        # Store
        sa.Column("store_name", sa.String(256)),
        sa.Column("store_number", sa.String(64)),
        sa.Column("store_city", sa.String(128)),
        sa.Column("store_state", sa.String(64)),
        # Transaction
        sa.Column("purchase_datetime", sa.DateTime(timezone=True)),
        sa.Column("subtotal", sa.Float),
        sa.Column("tax", sa.Float),
        sa.Column("total", sa.Float),
        sa.Column("currency", sa.String(8), server_default="USD"),
        sa.Column("payment_method", sa.String(64)),
        sa.Column("card_last4", sa.String(4)),
        # Extraction metadata
        sa.Column("extraction_raw", postgresql.JSONB),
        sa.Column("extraction_model", sa.String(64)),
        sa.Column("extraction_latency_ms", sa.Integer),
        sa.Column("extraction_retries", sa.Integer, server_default="0"),
        sa.Column("confidence", sa.Float, server_default="1.0"),
        sa.Column("warnings", postgresql.JSONB),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "line_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "receipt_id",
            sa.String(32),
            sa.ForeignKey("receipts.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column("line_number", sa.Integer),
        sa.Column("description_raw", sa.Text, nullable=False),
        sa.Column("description_norm", sa.Text),
        sa.Column("product_code", sa.String(64)),
        sa.Column("quantity", sa.Float),
        sa.Column("weight_lb", sa.Float),
        sa.Column("unit_price", sa.Float),
        sa.Column("total_price", sa.Float, nullable=False),
        sa.Column("category", sa.String(64)),
        sa.Column("category_confidence", sa.Float),
    )


def downgrade() -> None:
    op.drop_table("line_items")
    op.drop_table("receipts")
