"""add player active flag

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-06-25 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.create_index(batch_op.f("ix_players_is_active"), ["is_active"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_players_is_active"))
        batch_op.drop_column("is_active")
