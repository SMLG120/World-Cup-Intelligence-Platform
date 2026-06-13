"""add player squad fields and coach team link

Revision ID: b5c7a9e1d3f2
Revises: a1c9e8d4f602
Create Date: 2026-06-13 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5c7a9e1d3f2"
down_revision: Union[str, None] = "a1c9e8d4f602"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.add_column(sa.Column("shirt_number", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("first_names", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("last_names", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("name_on_shirt", sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column("date_of_birth", sa.String(length=12), nullable=True))
        batch_op.add_column(sa.Column("height_cm", sa.Integer(), nullable=True))

    with op.batch_alter_table("coaches", schema=None) as batch_op:
        batch_op.add_column(sa.Column("team_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("first_names", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("last_names", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("role", sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column("date_of_birth", sa.String(length=12), nullable=True))
        batch_op.create_foreign_key("fk_coaches_team_id", "teams", ["team_id"], ["id"])
        batch_op.create_index("ix_coaches_team_id", ["team_id"])


def downgrade() -> None:
    with op.batch_alter_table("coaches", schema=None) as batch_op:
        batch_op.drop_index("ix_coaches_team_id")
        batch_op.drop_constraint("fk_coaches_team_id", type_="foreignkey")
        batch_op.drop_column("date_of_birth")
        batch_op.drop_column("role")
        batch_op.drop_column("last_names")
        batch_op.drop_column("first_names")
        batch_op.drop_column("team_id")

    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.drop_column("height_cm")
        batch_op.drop_column("date_of_birth")
        batch_op.drop_column("name_on_shirt")
        batch_op.drop_column("last_names")
        batch_op.drop_column("first_names")
        batch_op.drop_column("shirt_number")
