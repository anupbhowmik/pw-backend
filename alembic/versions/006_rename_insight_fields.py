"""Rename insight body→desc and data→details

Revision ID: 006
Revises: 005_google_oauth_user
"""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005_google_oauth_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("insights", "body", new_column_name="desc")
    op.drop_column("insights", "data")
    op.add_column("insights", sa.Column("details", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("insights", "details")
    op.alter_column("insights", "desc", new_column_name="body")
    op.add_column("insights", sa.Column("data", sa.dialects.postgresql.JSONB(), nullable=True))
