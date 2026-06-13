"""add realtime elo and refresh metadata

Revision ID: a1c9e8d4f602
Revises: 73b2e6b46c21
Create Date: 2026-06-13 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c9e8d4f602"
down_revision: Union[str, None] = "73b2e6b46c21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "elo_rating_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.String(length=100), nullable=False),
        sa.Column("rating_date", sa.Date(), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("team_count", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("data_version", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("elo_rating_snapshots", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_elo_rating_snapshots_snapshot_id"), ["snapshot_id"], unique=True)
        batch_op.create_index(batch_op.f("ix_elo_rating_snapshots_rating_date"), ["rating_date"], unique=False)
        batch_op.create_index(batch_op.f("ix_elo_rating_snapshots_is_current"), ["is_current"], unique=False)
        batch_op.create_index(batch_op.f("ix_elo_rating_snapshots_data_version"), ["data_version"], unique=False)
        batch_op.create_index("ix_elo_rating_snapshots_current_date", ["is_current", "rating_date"], unique=False)

    op.create_table(
        "team_elo_ratings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("team_name", sa.String(length=120), nullable=False),
        sa.Column("team_code", sa.String(length=3), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("rating_date", sa.Date(), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("data_version", sa.String(length=100), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["elo_rating_snapshots.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "team_name", name="uq_team_elo_snapshot_team"),
    )
    with op.batch_alter_table("team_elo_ratings", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_team_elo_ratings_snapshot_id"), ["snapshot_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_team_elo_ratings_team_id"), ["team_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_team_elo_ratings_team_name"), ["team_name"], unique=False)
        batch_op.create_index(batch_op.f("ix_team_elo_ratings_team_code"), ["team_code"], unique=False)
        batch_op.create_index(batch_op.f("ix_team_elo_ratings_rank"), ["rank"], unique=False)
        batch_op.create_index(batch_op.f("ix_team_elo_ratings_rating_date"), ["rating_date"], unique=False)
        batch_op.create_index(batch_op.f("ix_team_elo_ratings_data_version"), ["data_version"], unique=False)
        batch_op.create_index("ix_team_elo_ratings_team_date", ["team_name", "rating_date"], unique=False)

    op.create_table(
        "elo_source_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=80), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("snapshot_id", sa.String(length=100), nullable=True),
        sa.Column("data_version", sa.String(length=100), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("rows_fetched", sa.Integer(), nullable=True),
        sa.Column("rows_loaded", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("elo_source_logs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_elo_source_logs_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_elo_source_logs_snapshot_id"), ["snapshot_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_elo_source_logs_data_version"), ["data_version"], unique=False)

    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.add_column(sa.Column("profile_description", sa.Text(), nullable=True))

    with op.batch_alter_table("ml_models", schema=None) as batch_op:
        batch_op.add_column(sa.Column("data_snapshot_version", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("calibration_status", sa.String(length=40), nullable=False, server_default="unknown"))
        batch_op.add_column(sa.Column("requires_recalibration", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("ml_models", schema=None) as batch_op:
        batch_op.drop_column("requires_recalibration")
        batch_op.drop_column("calibration_status")
        batch_op.drop_column("data_snapshot_version")

    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.drop_column("profile_description")

    with op.batch_alter_table("elo_source_logs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_elo_source_logs_data_version"))
        batch_op.drop_index(batch_op.f("ix_elo_source_logs_snapshot_id"))
        batch_op.drop_index(batch_op.f("ix_elo_source_logs_status"))
    op.drop_table("elo_source_logs")

    with op.batch_alter_table("team_elo_ratings", schema=None) as batch_op:
        batch_op.drop_index("ix_team_elo_ratings_team_date")
        batch_op.drop_index(batch_op.f("ix_team_elo_ratings_data_version"))
        batch_op.drop_index(batch_op.f("ix_team_elo_ratings_rating_date"))
        batch_op.drop_index(batch_op.f("ix_team_elo_ratings_rank"))
        batch_op.drop_index(batch_op.f("ix_team_elo_ratings_team_code"))
        batch_op.drop_index(batch_op.f("ix_team_elo_ratings_team_name"))
        batch_op.drop_index(batch_op.f("ix_team_elo_ratings_team_id"))
        batch_op.drop_index(batch_op.f("ix_team_elo_ratings_snapshot_id"))
    op.drop_table("team_elo_ratings")

    with op.batch_alter_table("elo_rating_snapshots", schema=None) as batch_op:
        batch_op.drop_index("ix_elo_rating_snapshots_current_date")
        batch_op.drop_index(batch_op.f("ix_elo_rating_snapshots_data_version"))
        batch_op.drop_index(batch_op.f("ix_elo_rating_snapshots_is_current"))
        batch_op.drop_index(batch_op.f("ix_elo_rating_snapshots_rating_date"))
        batch_op.drop_index(batch_op.f("ix_elo_rating_snapshots_snapshot_id"))
    op.drop_table("elo_rating_snapshots")
