"""Halkhata schema — drop old tables, create 10 new tables, seed categories.

Revision ID: 003
Revises: 002
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

# 13 default categories to seed
DEFAULT_CATEGORIES = [
    ("groceries", "Groceries", 1),
    ("dining", "Dining Out", 2),
    ("health_pharmacy", "Health & Pharmacy", 3),
    ("convenience_gas", "Convenience & Gas", 4),
    ("shopping", "Shopping & General", 5),
    ("home_garden", "Home & Garden", 6),
    ("electronics", "Electronics & Tech", 7),
    ("pet_care", "Pet Care", 8),
    ("household", "Household Essentials", 9),
    ("clothing", "Clothing & Apparel", 10),
    ("auto_transport", "Auto & Transport", 11),
    ("office", "Office & Supplies", 12),
    ("other", "Other", 13),
]


def upgrade() -> None:
    # Drop old tables
    op.drop_table("line_items")
    op.drop_table("receipts")

    # Users
    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("email", sa.String(256), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("display_name", sa.String(128)),
        sa.Column("currency", sa.String(8), server_default="USD"),
        sa.Column("timezone", sa.String(64), server_default="America/New_York"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Categories
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("categories.id")),
        sa.Column("is_system", sa.Boolean, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer, server_default="0"),
    )

    # Seed default categories
    categories_table = sa.table(
        "categories",
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("is_system", sa.Boolean),
    )
    op.bulk_insert(
        categories_table,
        [{"slug": slug, "name": name, "sort_order": order, "is_system": True} for slug, name, order in DEFAULT_CATEGORIES],
    )

    # Merchant Master
    op.create_table(
        "merchant_master",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("canonical_name", sa.String(256), unique=True, nullable=False, index=True),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id")),
        sa.Column("store_type", sa.String(64)),
    )

    # Documents
    op.create_table(
        "documents",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sha256", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("file_type", sa.String(20), server_default="receipt"),
        sa.Column("status", sa.String(20), server_default="ingested"),
        sa.Column("extraction_raw", JSONB),
        sa.Column("extraction_model", sa.String(64)),
        sa.Column("extraction_latency_ms", sa.Integer),
        sa.Column("extraction_retries", sa.Integer, server_default="0"),
        sa.Column("confidence", sa.Float, server_default="1.0"),
        sa.Column("warnings", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Transactions
    op.create_table(
        "transactions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_id", sa.String(32), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("merchant_name", sa.String(256), nullable=False),
        sa.Column("merchant_id", sa.Integer, sa.ForeignKey("merchant_master.id")),
        sa.Column("store_city", sa.String(128)),
        sa.Column("store_state", sa.String(64)),
        sa.Column("purchase_date", sa.DateTime(timezone=True)),
        sa.Column("subtotal", sa.Float),
        sa.Column("tax", sa.Float),
        sa.Column("total", sa.Float),
        sa.Column("currency", sa.String(8), server_default="USD"),
        sa.Column("payment_method", sa.String(64)),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Transaction Items
    op.create_table(
        "transaction_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("transaction_id", sa.String(32), sa.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("line_number", sa.Integer),
        sa.Column("description_raw", sa.Text, nullable=False),
        sa.Column("description_norm", sa.Text),
        sa.Column("quantity", sa.Float),
        sa.Column("unit_price", sa.Float),
        sa.Column("total_price", sa.Float, nullable=False),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id")),
    )

    # Derived User Metrics
    op.create_table(
        "derived_user_metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id")),
        sa.Column("total_spent", sa.Float, server_default="0"),
        sa.Column("transaction_count", sa.Integer, server_default="0"),
        sa.UniqueConstraint("user_id", "period", "period_start", "category_id", name="uq_user_metric"),
    )

    # Insights
    op.create_table(
        "insights",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("severity", sa.String(20), server_default="info"),
        sa.Column("data", JSONB),
        sa.Column("is_read", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Notifications
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("channel", sa.String(20), server_default="in_app"),
        sa.Column("is_read", sa.Boolean, server_default=sa.text("false")),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("related_id", sa.String(32)),
        sa.Column("related_type", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Planner Sessions
    op.create_table(
        "planner_sessions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("config", JSONB),
        sa.Column("progress", JSONB),
        sa.Column("messages", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("planner_sessions")
    op.drop_table("notifications")
    op.drop_table("insights")
    op.drop_table("derived_user_metrics")
    op.drop_table("transaction_items")
    op.drop_table("transactions")
    op.drop_table("documents")
    op.drop_table("merchant_master")
    op.drop_table("categories")
    op.drop_table("users")

    # Recreate old tables
    op.create_table(
        "receipts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("sha256", sa.String(64), unique=True, nullable=False),
        sa.Column("image_path", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), server_default="ingested"),
        sa.Column("store_name", sa.String(256)),
        sa.Column("store_number", sa.String(64)),
        sa.Column("store_city", sa.String(128)),
        sa.Column("store_state", sa.String(64)),
        sa.Column("store_category", sa.String(64)),
        sa.Column("purchase_datetime", sa.DateTime(timezone=True)),
        sa.Column("subtotal", sa.Float),
        sa.Column("tax", sa.Float),
        sa.Column("total", sa.Float),
        sa.Column("currency", sa.String(8), server_default="USD"),
        sa.Column("payment_method", sa.String(64)),
        sa.Column("card_last4", sa.String(4)),
        sa.Column("extraction_raw", JSONB),
        sa.Column("extraction_model", sa.String(64)),
        sa.Column("extraction_latency_ms", sa.Integer),
        sa.Column("extraction_retries", sa.Integer, server_default="0"),
        sa.Column("confidence", sa.Float, server_default="1.0"),
        sa.Column("warnings", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "line_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("receipt_id", sa.String(32), sa.ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False),
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
