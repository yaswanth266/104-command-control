"""SLA policy master + business calendar

Revision ID: d8f1b3a5c7e9
Revises: c7e9a1b3d5f7
Create Date: 2026-09-25 00:00:00.000000

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8f1b3a5c7e9'
down_revision: Union[str, None] = 'c7e9a1b3d5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TAT_DEFAULT = {"P1": 240, "P2": 480, "P3": 1440, "P4": 4320}


def upgrade() -> None:
    op.create_table(
        'ccc_business_calendar',
        sa.Column('code', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=191), nullable=False),
        sa.Column('is_24x7', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('timezone', sa.String(length=64), server_default=sa.text("'Asia/Kolkata'"), nullable=False),
        sa.Column('working_hours', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('code'),
    )
    op.create_table(
        'ccc_calendar_holiday',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('calendar_code', sa.String(length=32), nullable=False),
        sa.Column('holiday_date', sa.Date(), nullable=False),
        sa.Column('label', sa.String(length=191), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ccc_calendar_holiday_calendar_code'), 'ccc_calendar_holiday', ['calendar_code'], unique=False)

    op.create_table(
        'ccc_sla_policy',
        sa.Column('code', sa.String(length=48), nullable=False),
        sa.Column('subcategory_code', sa.String(length=32), nullable=True),
        sa.Column('category_code', sa.String(length=24), nullable=True),
        sa.Column('ticket_type', sa.String(length=24), nullable=True),
        sa.Column('priority_code', sa.String(length=4), nullable=False),
        sa.Column('response_mins', sa.Integer(), nullable=True),
        sa.Column('resolution_mins', sa.Integer(), nullable=False),
        sa.Column('calendar_code', sa.String(length=32), nullable=False),
        sa.Column('warning_pct', sa.Float(), nullable=True),
        sa.Column('breach_pct', sa.Float(), nullable=True),
        sa.Column('pause_statuses', sa.JSON(), nullable=True),
        sa.Column('effective_from', sa.DateTime(), nullable=True),
        sa.Column('effective_to', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('code'),
    )
    op.create_index(op.f('ix_ccc_sla_policy_subcategory_code'), 'ccc_sla_policy', ['subcategory_code'], unique=False)
    op.create_index(op.f('ix_ccc_sla_policy_category_code'), 'ccc_sla_policy', ['category_code'], unique=False)
    op.create_index(op.f('ix_ccc_sla_policy_ticket_type'), 'ccc_sla_policy', ['ticket_type'], unique=False)
    op.create_index(op.f('ix_ccc_sla_policy_priority_code'), 'ccc_sla_policy', ['priority_code'], unique=False)

    op.add_column('ccc_ticket', sa.Column('sla_policy_code', sa.String(length=48), nullable=True))
    op.add_column('ccc_ticket', sa.Column('response_due_at', sa.DateTime(), nullable=True))
    op.add_column('ccc_ticket', sa.Column('response_breached', sa.Boolean(), server_default=sa.text('0'), nullable=True))

    calendar_table = sa.table(
        'ccc_business_calendar',
        sa.column('code', sa.String), sa.column('name', sa.String), sa.column('is_24x7', sa.Boolean),
    )
    op.bulk_insert(calendar_table, [
        {'code': 'DEFAULT-24X7', 'name': 'Default (24x7, no holidays)', 'is_24x7': True},
    ])

    # Baseline (scope-less) policy rows, one per priority - this is what
    # get_tat_map()/PUT /admin/sla's `tat` patch read and write from now on.
    # Seeded to match TAT_DEFAULT exactly so every existing ticket-creation
    # test keeps passing unchanged.
    policy_table = sa.table(
        'ccc_sla_policy',
        sa.column('code', sa.String), sa.column('priority_code', sa.String),
        sa.column('resolution_mins', sa.Integer), sa.column('calendar_code', sa.String),
        sa.column('pause_statuses', sa.JSON), sa.column('is_active', sa.Boolean),
    )
    op.bulk_insert(policy_table, [
        {'code': f'BASELINE-{code}', 'priority_code': code, 'resolution_mins': mins,
         'calendar_code': 'DEFAULT-24X7', 'pause_statuses': ["PENDING"], 'is_active': True}
        for code, mins in _TAT_DEFAULT.items()
    ])

    # Carry forward a deployment's already-customized ccc_config['tat'], if
    # any, so migrating doesn't silently revert a production TAT override
    # back to the hardcoded default.
    conn = op.get_bind()
    row = conn.execute(sa.text("SELECT v FROM ccc_config WHERE k = 'tat'")).fetchone()
    if row and row[0]:
        try:
            tat = json.loads(row[0])
        except Exception:
            tat = {}
        for code, mins in tat.items():
            if code in _TAT_DEFAULT and isinstance(mins, (int, float)) and mins > 0:
                conn.execute(
                    sa.text("UPDATE ccc_sla_policy SET resolution_mins = :mins WHERE code = :pcode"),
                    {"mins": int(mins), "pcode": f"BASELINE-{code}"},
                )


def downgrade() -> None:
    op.drop_column('ccc_ticket', 'response_breached')
    op.drop_column('ccc_ticket', 'response_due_at')
    op.drop_column('ccc_ticket', 'sla_policy_code')

    op.drop_index(op.f('ix_ccc_sla_policy_priority_code'), table_name='ccc_sla_policy')
    op.drop_index(op.f('ix_ccc_sla_policy_ticket_type'), table_name='ccc_sla_policy')
    op.drop_index(op.f('ix_ccc_sla_policy_category_code'), table_name='ccc_sla_policy')
    op.drop_index(op.f('ix_ccc_sla_policy_subcategory_code'), table_name='ccc_sla_policy')
    op.drop_table('ccc_sla_policy')

    op.drop_index(op.f('ix_ccc_calendar_holiday_calendar_code'), table_name='ccc_calendar_holiday')
    op.drop_table('ccc_calendar_holiday')
    op.drop_table('ccc_business_calendar')
