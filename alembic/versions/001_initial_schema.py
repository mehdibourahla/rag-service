"""Initial schema for multi-tenant chatbot

Revision ID: 001
Revises:
Create Date: 2025-11-17 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tenants table
    op.create_table(
        'tenants',
        sa.Column('tenant_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('industry', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('tier', sa.String(50), nullable=False),
        sa.Column('contact_email', sa.String(255), nullable=False, unique=True),
        sa.Column('contact_name', sa.String(255), nullable=True),
        sa.Column('company_website', sa.String(512), nullable=True),
        sa.Column('settings', JSON, nullable=False, server_default='{}'),
        sa.Column('base_urls', JSON, nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('trial_ends_at', sa.DateTime(), nullable=True),
        sa.Column('metadata', JSON, nullable=False, server_default='{}'),
    )
    op.create_index('ix_tenants_contact_email', 'tenants', ['contact_email'])
    op.create_index('ix_tenants_status', 'tenants', ['status'])

    # Create tenant_api_keys table
    op.create_table(
        'tenant_api_keys',
        sa.Column('key_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.tenant_id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('key_hash', sa.String(255), nullable=False),
        sa.Column('prefix', sa.String(16), nullable=False),
        sa.Column('scopes', JSON, nullable=False, server_default='["chat", "upload", "query"]'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_index('ix_tenant_api_keys_tenant_id', 'tenant_api_keys', ['tenant_id'])
    op.create_index('ix_tenant_api_keys_prefix', 'tenant_api_keys', ['prefix'])
    op.create_index('ix_tenant_api_keys_is_active', 'tenant_api_keys', ['is_active'])

    # Create chat_sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('session_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.tenant_id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=True),
        sa.Column('user_agent', sa.String(512), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('end_reason', sa.String(50), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('user_message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('assistant_message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('language', sa.String(10), nullable=False, server_default='en'),
        sa.Column('metadata', JSON, nullable=False, server_default='{}'),
    )
    op.create_index('ix_chat_sessions_tenant_id', 'chat_sessions', ['tenant_id'])
    op.create_index('ix_chat_sessions_status', 'chat_sessions', ['status'])
    op.create_index('ix_chat_sessions_started_at', 'chat_sessions', ['started_at'])

    # Create messages table
    op.create_table(
        'messages',
        sa.Column('message_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('session_id', UUID(as_uuid=True), sa.ForeignKey('chat_sessions.session_id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.tenant_id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('processing_time_ms', sa.Float(), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('chunks_retrieved', sa.Integer(), nullable=True),
        sa.Column('sources_used', JSON, nullable=False, server_default='[]'),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('agent_action', sa.String(50), nullable=True),
        sa.Column('needs_retrieval', sa.Boolean(), nullable=True),
        sa.Column('metadata', JSON, nullable=False, server_default='{}'),
    )
    op.create_index('ix_messages_session_id', 'messages', ['session_id'])
    op.create_index('ix_messages_tenant_id', 'messages', ['tenant_id'])
    op.create_index('ix_messages_created_at', 'messages', ['created_at'])
    op.create_index('ix_messages_role', 'messages', ['role'])

    # Create message_feedback table
    op.create_table(
        'message_feedback',
        sa.Column('feedback_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('message_id', UUID(as_uuid=True), sa.ForeignKey('messages.message_id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', UUID(as_uuid=True), sa.ForeignKey('chat_sessions.session_id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.tenant_id', ondelete='CASCADE'), nullable=False),
        sa.Column('feedback_type', sa.String(50), nullable=False),
        sa.Column('value', sa.String(255), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('user_agent', sa.String(512), nullable=True),
    )
    op.create_index('ix_message_feedback_message_id', 'message_feedback', ['message_id'])
    op.create_index('ix_message_feedback_tenant_id', 'message_feedback', ['tenant_id'])
    op.create_index('ix_message_feedback_feedback_type', 'message_feedback', ['feedback_type'])


def downgrade() -> None:
    op.drop_table('message_feedback')
    op.drop_table('messages')
    op.drop_table('chat_sessions')
    op.drop_table('tenant_api_keys')
    op.drop_table('tenants')
