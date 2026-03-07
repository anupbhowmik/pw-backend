"""Switch users table to Google OAuth: add google_id, picture; drop password_hash.

Revision ID: 005
Revises: 004
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_id", sa.String(256), nullable=True))
    op.add_column("users", sa.Column("picture", sa.Text, nullable=True))
    op.create_unique_constraint("uq_users_google_id", "users", ["google_id"])
    op.create_index("ix_users_google_id", "users", ["google_id"])
    op.drop_column("users", "password_hash")


def downgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.Text, nullable=True))
    op.drop_index("ix_users_google_id", table_name="users")
    op.drop_constraint("uq_users_google_id", "users", type_="unique")
    op.drop_column("users", "picture")
    op.drop_column("users", "google_id")
