"""Add composite index for API key identifier, active flag, and expiry

Revision ID: 008_add_api_key_identifier_active_expiry_index
Revises: 007_adjust_api_key_identifier_indexes
Create Date: 2025-04-10

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '008_add_api_key_identifier_active_expiry_index'
down_revision = '007_adjust_api_key_identifier_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create a composite index optimized for identifier-based lookups."""
    op.create_index(
        'idx_api_keys_identifier_active_expiry',
        'api_keys',
        ['key_identifier', 'is_active', 'expires_at'],
        unique=False,
    )


def downgrade() -> None:
    """Drop the composite index."""
    op.drop_index('idx_api_keys_identifier_active_expiry', table_name='api_keys')
