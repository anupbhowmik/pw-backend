"""Add monthly budget fields to users.

Revision ID: 007
Revises: 006
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("monthly_income", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("monthly_rent", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("monthly_gym_subscription", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("monthly_insurance", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "monthly_insurance")
    op.drop_column("users", "monthly_gym_subscription")
    op.drop_column("users", "monthly_rent")
    op.drop_column("users", "monthly_income")
