"""priority master + impact/urgency matrix

Revision ID: c7e9a1b3d5f7
Revises: b3d5f7a9c1e2
Create Date: 2026-09-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e9a1b3d5f7'
down_revision: Union[str, None] = 'b3d5f7a9c1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ccc_priority',
        sa.Column('code', sa.String(length=4), nullable=False),
        sa.Column('label', sa.String(length=64), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('severity', sa.Integer(), nullable=True),
        sa.Column('display_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('code'),
    )
    op.create_table(
        'ccc_priority_matrix',
        sa.Column('impact_code', sa.String(length=16), nullable=False),
        sa.Column('urgency_code', sa.String(length=16), nullable=False),
        sa.Column('priority_code', sa.String(length=4), nullable=False),
        sa.PrimaryKeyConstraint('impact_code', 'urgency_code'),
    )

    priority_table = sa.table(
        'ccc_priority',
        sa.column('code', sa.String),
        sa.column('label', sa.String),
        sa.column('description', sa.String),
        sa.column('severity', sa.Integer),
        sa.column('display_order', sa.Integer),
        sa.column('is_active', sa.Boolean),
    )
    op.bulk_insert(priority_table, [
        {'code': 'P1', 'label': 'Critical', 'description': 'Critical - MMU unable to operate / major service interruption', 'severity': 1, 'display_order': 1, 'is_active': True},
        {'code': 'P2', 'label': 'High', 'description': 'High - major equipment/application/network issue affecting operations', 'severity': 2, 'display_order': 2, 'is_active': True},
        {'code': 'P3', 'label': 'Medium', 'description': 'Medium - issue with workaround available', 'severity': 3, 'display_order': 3, 'is_active': True},
        {'code': 'P4', 'label': 'Low', 'description': 'Low - non-critical request / information issue', 'severity': 4, 'display_order': 4, 'is_active': True},
    ])

    matrix_table = sa.table(
        'ccc_priority_matrix',
        sa.column('impact_code', sa.String),
        sa.column('urgency_code', sa.String),
        sa.column('priority_code', sa.String),
    )
    op.bulk_insert(matrix_table, [
        {'impact_code': 'HIGH', 'urgency_code': 'HIGH', 'priority_code': 'P1'},
        {'impact_code': 'HIGH', 'urgency_code': 'MEDIUM', 'priority_code': 'P2'},
        {'impact_code': 'HIGH', 'urgency_code': 'LOW', 'priority_code': 'P2'},
        {'impact_code': 'MEDIUM', 'urgency_code': 'HIGH', 'priority_code': 'P2'},
        {'impact_code': 'MEDIUM', 'urgency_code': 'MEDIUM', 'priority_code': 'P3'},
        {'impact_code': 'MEDIUM', 'urgency_code': 'LOW', 'priority_code': 'P3'},
        {'impact_code': 'LOW', 'urgency_code': 'HIGH', 'priority_code': 'P3'},
        {'impact_code': 'LOW', 'urgency_code': 'MEDIUM', 'priority_code': 'P4'},
        {'impact_code': 'LOW', 'urgency_code': 'LOW', 'priority_code': 'P4'},
    ])

    op.add_column('ccc_ticket', sa.Column('impact_code', sa.String(length=16), nullable=True))
    op.add_column('ccc_ticket', sa.Column('urgency_code', sa.String(length=16), nullable=True))
    op.add_column('ccc_ticket', sa.Column('original_priority', sa.String(length=4), nullable=True))
    op.execute("UPDATE ccc_ticket SET original_priority = priority WHERE original_priority IS NULL")


def downgrade() -> None:
    op.drop_column('ccc_ticket', 'original_priority')
    op.drop_column('ccc_ticket', 'urgency_code')
    op.drop_column('ccc_ticket', 'impact_code')
    op.drop_table('ccc_priority_matrix')
    op.drop_table('ccc_priority')
