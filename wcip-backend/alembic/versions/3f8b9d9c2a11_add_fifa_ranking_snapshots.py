"""add fifa ranking snapshots

Revision ID: 3f8b9d9c2a11
Revises: 0964b8fff254
Create Date: 2026-06-08 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3f8b9d9c2a11"
down_revision: Union[str, None] = "0964b8fff254"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fifa_ranking_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ranking_id", sa.String(length=80), nullable=False),
        sa.Column("gender", sa.String(length=20), nullable=False),
        sa.Column("sport_type", sa.String(length=30), nullable=False),
        sa.Column("ranking_date", sa.Date(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_update_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("team_count", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("fifa_ranking_snapshots", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_fifa_ranking_snapshots_ranking_id"), ["ranking_id"], unique=True)
        batch_op.create_index(batch_op.f("ix_fifa_ranking_snapshots_ranking_date"), ["ranking_date"], unique=False)
        batch_op.create_index(batch_op.f("ix_fifa_ranking_snapshots_is_current"), ["is_current"], unique=False)
        batch_op.create_index("ix_fifa_ranking_snapshots_current_date", ["is_current", "ranking_date"], unique=False)

    op.create_table(
        "fifa_ranking_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("team_name", sa.String(length=120), nullable=False),
        sa.Column("team_code", sa.String(length=3), nullable=True),
        sa.Column("confederation", sa.String(length=40), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("previous_rank", sa.Integer(), nullable=True),
        sa.Column("rank_change", sa.Integer(), nullable=True),
        sa.Column("points", sa.Float(), nullable=True),
        sa.Column("previous_points", sa.Float(), nullable=True),
        sa.Column("points_change", sa.Float(), nullable=True),
        sa.Column("raw_team_name", sa.String(length=160), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["fifa_ranking_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "team_name", name="uq_fifa_ranking_entry_team"),
        sa.UniqueConstraint("snapshot_id", "team_code", name="uq_fifa_ranking_entry_code"),
    )
    with op.batch_alter_table("fifa_ranking_entries", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_fifa_ranking_entries_snapshot_id"), ["snapshot_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_fifa_ranking_entries_team_name"), ["team_name"], unique=False)
        batch_op.create_index(batch_op.f("ix_fifa_ranking_entries_team_code"), ["team_code"], unique=False)
        batch_op.create_index(batch_op.f("ix_fifa_ranking_entries_rank"), ["rank"], unique=False)
        batch_op.create_index("ix_fifa_ranking_entries_team_snapshot", ["team_name", "snapshot_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("fifa_ranking_entries", schema=None) as batch_op:
        batch_op.drop_index("ix_fifa_ranking_entries_team_snapshot")
        batch_op.drop_index(batch_op.f("ix_fifa_ranking_entries_rank"))
        batch_op.drop_index(batch_op.f("ix_fifa_ranking_entries_team_code"))
        batch_op.drop_index(batch_op.f("ix_fifa_ranking_entries_team_name"))
        batch_op.drop_index(batch_op.f("ix_fifa_ranking_entries_snapshot_id"))
    op.drop_table("fifa_ranking_entries")

    with op.batch_alter_table("fifa_ranking_snapshots", schema=None) as batch_op:
        batch_op.drop_index("ix_fifa_ranking_snapshots_current_date")
        batch_op.drop_index(batch_op.f("ix_fifa_ranking_snapshots_is_current"))
        batch_op.drop_index(batch_op.f("ix_fifa_ranking_snapshots_ranking_date"))
        batch_op.drop_index(batch_op.f("ix_fifa_ranking_snapshots_ranking_id"))
    op.drop_table("fifa_ranking_snapshots")
