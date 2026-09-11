"""Vehicle geo snapshot (segment/secretariat/village) + caller emp lookup fields

Revision ID: a1b2c3d4e5f6
Revises: e9a1c3b5d7f9
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e9a1c3b5d7f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ccc_ticket', sa.Column('segment_number', sa.String(length=64), nullable=True))
    op.add_column('ccc_ticket', sa.Column('secretariat', sa.String(length=191), nullable=True))
    op.add_column('ccc_ticket', sa.Column('village', sa.String(length=191), nullable=True))
    op.add_column('ccc_ticket', sa.Column('caller_emp_id', sa.String(length=64), nullable=True))
    op.add_column('ccc_ticket', sa.Column('caller_designation', sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column('ccc_ticket', 'caller_designation')
    op.drop_column('ccc_ticket', 'caller_emp_id')
    op.drop_column('ccc_ticket', 'village')
    op.drop_column('ccc_ticket', 'secretariat')
    op.drop_column('ccc_ticket', 'segment_number')
