"""Add refresh_tokens table for JTI-tracked refresh tokens

Revision ID: 006_add_refresh_tokens_table
Revises: 005_add_rbac_tables
Create Date: 2025-02-14

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006_add_refresh_tokens_table'
down_revision = '005_add_rbac_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Create refresh_tokens table for managing refresh token lifecycle."""
    op.create_table(
        'refresh_tokens',
        sa.Column('jti', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('rotated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_reason', sa.String(length=255), nullable=True),
        sa.Column('replaced_by_jti', sa.String(length=36), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('ix_refresh_tokens_expires_at', 'refresh_tokens', ['expires_at'])
    op.create_index('ix_refresh_tokens_revoked_at', 'refresh_tokens', ['revoked_at'])
    op.create_index('ix_refresh_tokens_rotated_at', 'refresh_tokens', ['rotated_at'])
    op.create_index('ix_refresh_tokens_replaced_by_jti', 'refresh_tokens', ['replaced_by_jti'])
    op.create_index('ix_refresh_tokens_ip_address', 'refresh_tokens', ['ip_address'])
    op.create_index('ix_refresh_tokens_last_used_at', 'refresh_tokens', ['last_used_at'])
    op.create_index('idx_refresh_token_user_active', 'refresh_tokens', ['user_id', 'revoked_at', 'rotated_at'])


def downgrade():
    """Drop refresh_tokens table."""
    op.drop_index('idx_refresh_token_user_active', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_last_used_at', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_ip_address', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_replaced_by_jti', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_rotated_at', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_revoked_at', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_expires_at', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_user_id', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
