"""instruments: buffered NSE/BSE equity list for the searchable picker

Revision ID: 0003_instruments
Revises: 0002_task02
Create Date: 2026-07-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_instruments"
down_revision: str | None = "0002_task02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instrument_token", sa.Integer(), nullable=False),
        sa.Column("exchange", sa.String(length=8), nullable=False),
        sa.Column("tradingsymbol", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("synced_on", sa.String(length=10), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange", "tradingsymbol", name="uq_instrument_exch_symbol"),
    )
    op.create_index("ix_instruments_instrument_token", "instruments", ["instrument_token"])
    op.create_index("ix_instruments_tradingsymbol", "instruments", ["tradingsymbol"])
    op.create_index("ix_instrument_search", "instruments", ["exchange", "tradingsymbol"])


def downgrade() -> None:
    op.drop_index("ix_instrument_search", table_name="instruments")
    op.drop_index("ix_instruments_tradingsymbol", table_name="instruments")
    op.drop_index("ix_instruments_instrument_token", table_name="instruments")
    op.drop_table("instruments")
