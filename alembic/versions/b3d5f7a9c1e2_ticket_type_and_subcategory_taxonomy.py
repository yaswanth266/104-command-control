"""ticket type master + promote reason to sub-category master

Revision ID: b3d5f7a9c1e2
Revises: a1c2d3e4f5g6
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3d5f7a9c1e2'
down_revision: Union[str, None] = 'a1c2d3e4f5g6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ccc_ticket_type',
        sa.Column('code', sa.String(length=24), nullable=False),
        sa.Column('label', sa.String(length=191), nullable=False),
        sa.Column('workflow_code', sa.String(length=24), nullable=True),
        sa.Column('requires_approval', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('code'),
    )

    ticket_type_table = sa.table(
        'ccc_ticket_type',
        sa.column('code', sa.String),
        sa.column('label', sa.String),
        sa.column('requires_approval', sa.Boolean),
        sa.column('is_active', sa.Boolean),
    )
    op.bulk_insert(ticket_type_table, [
        {'code': 'INCIDENT', 'label': 'Incident', 'requires_approval': False, 'is_active': True},
        {'code': 'SERVICE_REQUEST', 'label': 'Service Request', 'requires_approval': False, 'is_active': True},
        {'code': 'CHANGE_REQUEST', 'label': 'Change Request', 'requires_approval': True, 'is_active': True},
    ])

    op.add_column('ccc_category', sa.Column('ticket_type', sa.String(length=24), server_default=sa.text("'INCIDENT'"), nullable=False))
    op.add_column('ccc_category', sa.Column('effective_from', sa.DateTime(), nullable=True))
    op.add_column('ccc_category', sa.Column('effective_to', sa.DateTime(), nullable=True))
    op.add_column('ccc_category', sa.Column('modified_by', sa.String(length=64), nullable=True))
    op.add_column('ccc_category', sa.Column('modified_at', sa.DateTime(), nullable=True))

    op.add_column('ccc_reason', sa.Column('ticket_type', sa.String(length=24), server_default=sa.text("'INCIDENT'"), nullable=False))
    op.add_column('ccc_reason', sa.Column('default_priority', sa.String(length=4), nullable=True))
    op.add_column('ccc_reason', sa.Column('sla_policy_code', sa.String(length=32), nullable=True))
    op.add_column('ccc_reason', sa.Column('workflow_code', sa.String(length=24), nullable=True))
    op.add_column('ccc_reason', sa.Column('effective_from', sa.DateTime(), nullable=True))
    op.add_column('ccc_reason', sa.Column('effective_to', sa.DateTime(), nullable=True))

    op.add_column('ccc_ticket', sa.Column('ticket_type', sa.String(length=24), server_default=sa.text("'INCIDENT'"), nullable=True))
    op.add_column('ccc_ticket', sa.Column('subcategory_code', sa.String(length=32), nullable=True))
    op.add_column('ccc_ticket', sa.Column('category_label_snapshot', sa.String(length=191), nullable=True))
    op.add_column('ccc_ticket', sa.Column('subcategory_label_snapshot', sa.String(length=191), nullable=True))
    op.create_index(op.f('ix_ccc_ticket_ticket_type'), 'ccc_ticket', ['ticket_type'], unique=False)
    op.create_index(op.f('ix_ccc_ticket_subcategory_code'), 'ccc_ticket', ['subcategory_code'], unique=False)

    op.execute("UPDATE ccc_ticket SET ticket_type = 'INCIDENT' WHERE ticket_type IS NULL")


def downgrade() -> None:
    op.drop_index(op.f('ix_ccc_ticket_subcategory_code'), table_name='ccc_ticket')
    op.drop_index(op.f('ix_ccc_ticket_ticket_type'), table_name='ccc_ticket')
    op.drop_column('ccc_ticket', 'subcategory_label_snapshot')
    op.drop_column('ccc_ticket', 'category_label_snapshot')
    op.drop_column('ccc_ticket', 'subcategory_code')
    op.drop_column('ccc_ticket', 'ticket_type')

    op.drop_column('ccc_reason', 'effective_to')
    op.drop_column('ccc_reason', 'effective_from')
    op.drop_column('ccc_reason', 'workflow_code')
    op.drop_column('ccc_reason', 'sla_policy_code')
    op.drop_column('ccc_reason', 'default_priority')
    op.drop_column('ccc_reason', 'ticket_type')

    op.drop_column('ccc_category', 'modified_at')
    op.drop_column('ccc_category', 'modified_by')
    op.drop_column('ccc_category', 'effective_to')
    op.drop_column('ccc_category', 'effective_from')
    op.drop_column('ccc_category', 'ticket_type')

    op.drop_table('ccc_ticket_type')
