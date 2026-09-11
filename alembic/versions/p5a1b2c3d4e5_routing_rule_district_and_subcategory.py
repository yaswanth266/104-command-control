"""Routing rule: district_id column + subcategory_code index (Phase 5 stage 1)

Revision ID: p5a1b2c3d4e5
Revises: a1b2c3d4e5f6
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'p5a1b2c3d4e5'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ccc_routing_rule', sa.Column('district_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_ccc_routing_rule_district_id'), 'ccc_routing_rule', ['district_id'], unique=False)
    op.create_index(op.f('ix_ccc_routing_rule_subcategory_code'), 'ccc_routing_rule', ['subcategory_code'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ccc_routing_rule_subcategory_code'), table_name='ccc_routing_rule')
    op.drop_index(op.f('ix_ccc_routing_rule_district_id'), table_name='ccc_routing_rule')
    op.drop_column('ccc_routing_rule', 'district_id')
