"""Rebuild API key indexes to support identifier prefixes

Revision ID: 007_adjust_api_key_identifier_indexes
Revises: 006_add_api_key_identifier
Create Date: 2025-03-09

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '007_adjust_api_key_identifier_indexes'
down_revision = '006_add_api_key_identifier'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop and recreate API key indexes to align with identifier lookups."""
    op.execute("DROP INDEX IF EXISTS idx_api_keys_identifier")
    op.execute("DROP INDEX IF EXISTS idx_api_keys_expiry")
    op.execute("DROP INDEX IF EXISTS idx_api_keys_active_expiry")

    op.create_index('idx_api_keys_identifier', 'api_keys', ['key_identifier'], unique=False)
    op.create_index('idx_api_keys_expiry', 'api_keys', ['expires_at'], unique=False)
    op.create_index('idx_api_keys_active_expiry', 'api_keys', ['is_active', 'expires_at'], unique=False)


def downgrade() -> None:
    """Restore the previous API key indexing strategy."""
    op.drop_index('idx_api_keys_active_expiry', table_name='api_keys')
    op.drop_index('idx_api_keys_expiry', table_name='api_keys')
    op.drop_index('idx_api_keys_identifier', table_name='api_keys')

    op.create_index('idx_api_keys_identifier', 'api_keys', ['key_identifier'], unique=True)
    op.create_index('idx_api_keys_expiry', 'api_keys', ['expires_at'], unique=False)
    op.create_index('idx_api_keys_active_expiry', 'api_keys', ['is_active', 'expires_at'], unique=False)
