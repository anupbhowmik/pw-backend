"""Add ocr_text column to documents table.

Revision ID: 004
Revises: 003
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("ocr_text", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "ocr_text")
