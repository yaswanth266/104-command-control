"""Master-data sync cache (vehicles/employees/hierarchy) + routing rule role/team per level (Phase 5 stage 2)

Revision ID: p5b2c3d4e5f6
Revises: p5a1b2c3d4e5
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'p5b2c3d4e5f6'
down_revision: Union[str, None] = 'p5a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ccc_ext_vehicle',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('registration_no', sa.String(length=32), nullable=False),
        sa.Column('segment_number', sa.String(length=64), nullable=True),
        sa.Column('district_name', sa.String(length=191), nullable=True),
        sa.Column('mandal_name', sa.String(length=191), nullable=True),
        sa.Column('secretariat', sa.String(length=191), nullable=True),
        sa.Column('village', sa.String(length=191), nullable=True),
        sa.Column('district_id', sa.Integer(), nullable=True),
        sa.Column('mandal_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ccc_ext_vehicle_registration_no'), 'ccc_ext_vehicle', ['registration_no'], unique=True)
    op.create_index(op.f('ix_ccc_ext_vehicle_district_id'), 'ccc_ext_vehicle', ['district_id'], unique=False)
    op.create_index(op.f('ix_ccc_ext_vehicle_mandal_id'), 'ccc_ext_vehicle', ['mandal_id'], unique=False)

    op.create_table(
        'ccc_ext_employee',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('emp_code', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=191), nullable=True),
        sa.Column('designation', sa.String(length=128), nullable=True),
        sa.Column('role_code', sa.String(length=24), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ccc_ext_employee_emp_code'), 'ccc_ext_employee', ['emp_code'], unique=True)
    op.create_index(op.f('ix_ccc_ext_employee_role_code'), 'ccc_ext_employee', ['role_code'], unique=False)

    op.create_table(
        'ccc_emp_hierarchy',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('emp_code', sa.String(length=32), nullable=False),
        sa.Column('role_code', sa.String(length=24), nullable=False),
        sa.Column('holder_emp_code', sa.String(length=32), nullable=True),
        sa.Column('holder_name', sa.String(length=191), nullable=True),
        sa.Column('holder_designation', sa.String(length=128), nullable=True),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ccc_emp_hierarchy_emp_code'), 'ccc_emp_hierarchy', ['emp_code'], unique=False)
    op.create_index('ux_ccc_emp_hierarchy_emp_role', 'ccc_emp_hierarchy', ['emp_code', 'role_code'], unique=True)

    op.create_table(
        'ccc_sync_run',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('job', sa.String(length=32), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=True),
        sa.Column('rows_upserted', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ccc_sync_run_job'), 'ccc_sync_run', ['job'], unique=False)

    op.add_column('ccc_routing_rule', sa.Column('l1_role', sa.String(length=24), nullable=True))
    op.add_column('ccc_routing_rule', sa.Column('l2_team_code', sa.String(length=24), nullable=True))
    op.add_column('ccc_routing_rule', sa.Column('l2_role', sa.String(length=24), nullable=True))
    op.add_column('ccc_routing_rule', sa.Column('l3_team_code', sa.String(length=24), nullable=True))
    op.add_column('ccc_routing_rule', sa.Column('l3_role', sa.String(length=24), nullable=True))
    op.add_column('ccc_routing_rule', sa.Column('l4_team_code', sa.String(length=24), nullable=True))
    op.add_column('ccc_routing_rule', sa.Column('l4_role', sa.String(length=24), nullable=True))


def downgrade() -> None:
    op.drop_column('ccc_routing_rule', 'l4_role')
    op.drop_column('ccc_routing_rule', 'l4_team_code')
    op.drop_column('ccc_routing_rule', 'l3_role')
    op.drop_column('ccc_routing_rule', 'l3_team_code')
    op.drop_column('ccc_routing_rule', 'l2_role')
    op.drop_column('ccc_routing_rule', 'l2_team_code')
    op.drop_column('ccc_routing_rule', 'l1_role')

    op.drop_index(op.f('ix_ccc_sync_run_job'), table_name='ccc_sync_run')
    op.drop_table('ccc_sync_run')

    op.drop_index('ux_ccc_emp_hierarchy_emp_role', table_name='ccc_emp_hierarchy')
    op.drop_index(op.f('ix_ccc_emp_hierarchy_emp_code'), table_name='ccc_emp_hierarchy')
    op.drop_table('ccc_emp_hierarchy')

    op.drop_index(op.f('ix_ccc_ext_employee_role_code'), table_name='ccc_ext_employee')
    op.drop_index(op.f('ix_ccc_ext_employee_emp_code'), table_name='ccc_ext_employee')
    op.drop_table('ccc_ext_employee')

    op.drop_index(op.f('ix_ccc_ext_vehicle_mandal_id'), table_name='ccc_ext_vehicle')
    op.drop_index(op.f('ix_ccc_ext_vehicle_district_id'), table_name='ccc_ext_vehicle')
    op.drop_index(op.f('ix_ccc_ext_vehicle_registration_no'), table_name='ccc_ext_vehicle')
    op.drop_table('ccc_ext_vehicle')
