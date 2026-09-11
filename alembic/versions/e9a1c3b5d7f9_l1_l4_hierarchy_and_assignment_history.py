"""L1-L4 hierarchy, routing rules, assignment history/exceptions

Revision ID: e9a1c3b5d7f9
Revises: d8f1b3a5c7e9
Create Date: 2026-10-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9a1c3b5d7f9'
down_revision: Union[str, None] = 'd8f1b3a5c7e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ccc_ticket_assignment',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('level', sa.String(length=8), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('user_name_snapshot', sa.String(length=128), nullable=True),
        sa.Column('team_code', sa.String(length=24), nullable=True),
        sa.Column('team_name_snapshot', sa.String(length=191), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('released_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=16), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column('source', sa.String(length=16), server_default=sa.text("'LOCAL'"), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ccc_ticket_assignment_ticket_id'), 'ccc_ticket_assignment', ['ticket_id'], unique=False)

    op.create_table(
        'ccc_routing_rule',
        sa.Column('code', sa.String(length=48), nullable=False),
        sa.Column('category_code', sa.String(length=24), nullable=False),
        sa.Column('zone_id', sa.Integer(), nullable=True),
        sa.Column('ticket_type', sa.String(length=24), nullable=True),
        sa.Column('subcategory_code', sa.String(length=32), nullable=True),
        sa.Column('l1_team_code', sa.String(length=24), nullable=True),
        sa.Column('l1_username', sa.String(length=64), nullable=True),
        sa.Column('l2_username', sa.String(length=64), nullable=True),
        sa.Column('l3_username', sa.String(length=64), nullable=True),
        sa.Column('l4_username', sa.String(length=64), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('code'),
    )
    op.create_index(op.f('ix_ccc_routing_rule_category_code'), 'ccc_routing_rule', ['category_code'], unique=False)
    op.create_index(op.f('ix_ccc_routing_rule_zone_id'), 'ccc_routing_rule', ['zone_id'], unique=False)

    op.create_table(
        'ccc_api_assignment_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('mode', sa.String(length=16), nullable=False),
        sa.Column('request_payload', sa.JSON(), nullable=True),
        sa.Column('response_payload', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ccc_api_assignment_log_ticket_id'), 'ccc_api_assignment_log', ['ticket_id'], unique=False)

    op.create_table(
        'ccc_assignment_exception',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=64), nullable=False),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=16), server_default=sa.text("'OPEN'"), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ccc_assignment_exception_ticket_id'), 'ccc_assignment_exception', ['ticket_id'], unique=False)

    op.add_column('ccc_ticket', sa.Column('current_level', sa.String(length=4), server_default=sa.text("'L1'"), nullable=True))
    op.add_column('ccc_ticket', sa.Column('current_assignee_username', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('ccc_ticket', 'current_assignee_username')
    op.drop_column('ccc_ticket', 'current_level')

    op.drop_index(op.f('ix_ccc_assignment_exception_ticket_id'), table_name='ccc_assignment_exception')
    op.drop_table('ccc_assignment_exception')

    op.drop_index(op.f('ix_ccc_api_assignment_log_ticket_id'), table_name='ccc_api_assignment_log')
    op.drop_table('ccc_api_assignment_log')

    op.drop_index(op.f('ix_ccc_routing_rule_zone_id'), table_name='ccc_routing_rule')
    op.drop_index(op.f('ix_ccc_routing_rule_category_code'), table_name='ccc_routing_rule')
    op.drop_table('ccc_routing_rule')

    op.drop_index(op.f('ix_ccc_ticket_assignment_ticket_id'), table_name='ccc_ticket_assignment')
    op.drop_table('ccc_ticket_assignment')
