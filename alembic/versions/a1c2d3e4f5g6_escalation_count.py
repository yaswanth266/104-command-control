"""track how many times a ticket has been escalated

Revision ID: a1c2d3e4f5g6
Revises: c919f7be7f5e
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c2d3e4f5g6'
down_revision: Union[str, None] = 'c919f7be7f5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ccc_ticket', sa.Column('escalation_count', sa.Integer(), server_default=sa.text('0'), nullable=True))
    op.execute("UPDATE ccc_ticket SET escalation_count = 1 WHERE escalated = 1")


def downgrade() -> None:
    op.drop_column('ccc_ticket', 'escalation_count')
