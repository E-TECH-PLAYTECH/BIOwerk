"""Add API key identifier and supporting indexes

Revision ID: 006_add_api_key_identifier
Revises: 005_add_rbac_tables
Create Date: 2025-02-08

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_add_api_key_identifier'
down_revision = '005_add_rbac_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add key_identifier column and indexes for API key lookups."""
    op.add_column('api_keys', sa.Column('key_identifier', sa.String(length=128), nullable=True))

    # Remove legacy expiry index if it exists to avoid duplication
    op.execute("DROP INDEX IF EXISTS ix_api_keys_expires_at")

    # New indexes to accelerate API key lookups and expiry checks
    op.create_index('idx_api_keys_identifier', 'api_keys', ['key_identifier'], unique=True)
    op.create_index('idx_api_keys_expiry', 'api_keys', ['expires_at'], unique=False)
    op.create_index('idx_api_keys_active_expiry', 'api_keys', ['is_active', 'expires_at'], unique=False)


def downgrade() -> None:
    """Revert key identifier support."""
    op.drop_index('idx_api_keys_active_expiry', table_name='api_keys')
    op.drop_index('idx_api_keys_expiry', table_name='api_keys')
    op.drop_index('idx_api_keys_identifier', table_name='api_keys')
    op.drop_column('api_keys', 'key_identifier')
