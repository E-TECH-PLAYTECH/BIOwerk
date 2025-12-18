"""Add exp and status columns to refresh_tokens table

Revision ID: 007_add_refresh_token_exp_and_status
Revises: 006_add_refresh_tokens_table
Create Date: 2025-02-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "007_add_refresh_token_exp_and_status"
down_revision = "006_add_refresh_tokens_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add exp and status columns with supporting indexes."""
    op.add_column("refresh_tokens", sa.Column("exp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.add_column("refresh_tokens", sa.Column("status", sa.String(length=32), nullable=False, server_default="active"))
    op.create_index("idx_refresh_token_status", "refresh_tokens", ["status", "expires_at"])

    # Backfill exp column with expires_at values for existing rows
    op.execute("UPDATE refresh_tokens SET exp = expires_at WHERE exp IS NULL")


def downgrade() -> None:
    """Remove exp and status columns and related index."""
    op.drop_index("idx_refresh_token_status", table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "status")
    op.drop_column("refresh_tokens", "exp")
