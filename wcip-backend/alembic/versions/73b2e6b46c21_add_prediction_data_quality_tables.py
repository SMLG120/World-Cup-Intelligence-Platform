"""add prediction data quality tables

Revision ID: 73b2e6b46c21
Revises: 3f8b9d9c2a11
Create Date: 2026-06-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "73b2e6b46c21"
down_revision: Union[str, None] = "4a6f2d8b9c01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PLAYER_FEATURE_COLUMNS = [
    "average_starting_xi_rating_diff",
    "average_squad_rating_diff",
    "top_5_player_rating_avg_diff",
    "goalkeeper_rating_diff",
    "defensive_unit_rating_diff",
    "midfield_unit_rating_diff",
    "attacking_unit_rating_diff",
    "squad_depth_score_diff",
    "star_player_score_diff",
    "injury_burden_score_diff",
    "player_form_score_diff",
    "player_availability_score_diff",
    "international_experience_score_diff",
    "average_caps_diff",
    "total_international_goals_diff",
    "weighted_player_strength_diff",
]


def upgrade() -> None:
    op.create_table(
        "ranking_source_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=80), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("ranking_id", sa.String(length=80), nullable=True),
        sa.Column("data_version", sa.String(length=80), nullable=True),
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
    with op.batch_alter_table("ranking_source_logs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ranking_source_logs_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_ranking_source_logs_ranking_id"), ["ranking_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_ranking_source_logs_data_version"), ["data_version"], unique=False)

    op.create_table(
        "team_rankings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("team_name", sa.String(length=120), nullable=False),
        sa.Column("team_code", sa.String(length=3), nullable=True),
        sa.Column("confederation", sa.String(length=40), nullable=True),
        sa.Column("ranking_provider", sa.String(length=40), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("points", sa.Float(), nullable=True),
        sa.Column("ranking_date", sa.Date(), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("data_version", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["fifa_ranking_snapshots.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "team_name", name="uq_team_ranking_snapshot_team"),
    )
    with op.batch_alter_table("team_rankings", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_team_rankings_snapshot_id"), ["snapshot_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_team_rankings_team_id"), ["team_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_team_rankings_team_name"), ["team_name"], unique=False)
        batch_op.create_index(batch_op.f("ix_team_rankings_team_code"), ["team_code"], unique=False)
        batch_op.create_index(batch_op.f("ix_team_rankings_rank"), ["rank"], unique=False)
        batch_op.create_index(batch_op.f("ix_team_rankings_ranking_date"), ["ranking_date"], unique=False)
        batch_op.create_index(batch_op.f("ix_team_rankings_data_version"), ["data_version"], unique=False)
        batch_op.create_index("ix_team_rankings_team_date", ["team_name", "ranking_date"], unique=False)

    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.add_column(sa.Column("player_rating", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("ea_fc_rating", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("player_rating_source", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("player_rating_version", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("player_rating_updated_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "player_rating_imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("source_file", sa.String(length=500), nullable=True),
        sa.Column("source_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("valid_rows", sa.Integer(), nullable=False),
        sa.Column("skipped_rows", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("player_rating_imports", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_player_rating_imports_source_name"), ["source_name"], unique=False)
        batch_op.create_index(batch_op.f("ix_player_rating_imports_source_version"), ["source_version"], unique=False)
        batch_op.create_index(batch_op.f("ix_player_rating_imports_status"), ["status"], unique=False)

    op.create_table(
        "player_rating_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=True),
        sa.Column("player_name", sa.String(length=150), nullable=False),
        sa.Column("team_name", sa.String(length=120), nullable=False),
        sa.Column("position", sa.String(length=30), nullable=True),
        sa.Column("club", sa.String(length=120), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("ea_fc_rating", sa.Float(), nullable=True),
        sa.Column("recent_form_score", sa.Float(), nullable=True),
        sa.Column("source_row_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["import_id"], ["player_rating_imports.id"]),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_id", "team_name", "player_name", name="uq_player_rating_import_team_player"),
    )
    with op.batch_alter_table("player_rating_records", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_player_rating_records_import_id"), ["import_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_player_rating_records_player_id"), ["player_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_player_rating_records_player_name"), ["player_name"], unique=False)
        batch_op.create_index(batch_op.f("ix_player_rating_records_team_name"), ["team_name"], unique=False)
        batch_op.create_index(batch_op.f("ix_player_rating_records_source_row_hash"), ["source_row_hash"], unique=False)

    with op.batch_alter_table("match_features", schema=None) as batch_op:
        for name in PLAYER_FEATURE_COLUMNS:
            batch_op.add_column(sa.Column(name, sa.Float(), nullable=False, server_default="0.0"))


def downgrade() -> None:
    with op.batch_alter_table("match_features", schema=None) as batch_op:
        for name in reversed(PLAYER_FEATURE_COLUMNS):
            batch_op.drop_column(name)

    with op.batch_alter_table("player_rating_records", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_player_rating_records_source_row_hash"))
        batch_op.drop_index(batch_op.f("ix_player_rating_records_team_name"))
        batch_op.drop_index(batch_op.f("ix_player_rating_records_player_name"))
        batch_op.drop_index(batch_op.f("ix_player_rating_records_player_id"))
        batch_op.drop_index(batch_op.f("ix_player_rating_records_import_id"))
    op.drop_table("player_rating_records")

    with op.batch_alter_table("player_rating_imports", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_player_rating_imports_status"))
        batch_op.drop_index(batch_op.f("ix_player_rating_imports_source_version"))
        batch_op.drop_index(batch_op.f("ix_player_rating_imports_source_name"))
    op.drop_table("player_rating_imports")

    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.drop_column("player_rating_updated_at")
        batch_op.drop_column("player_rating_version")
        batch_op.drop_column("player_rating_source")
        batch_op.drop_column("ea_fc_rating")
        batch_op.drop_column("player_rating")

    with op.batch_alter_table("team_rankings", schema=None) as batch_op:
        batch_op.drop_index("ix_team_rankings_team_date")
        batch_op.drop_index(batch_op.f("ix_team_rankings_data_version"))
        batch_op.drop_index(batch_op.f("ix_team_rankings_ranking_date"))
        batch_op.drop_index(batch_op.f("ix_team_rankings_rank"))
        batch_op.drop_index(batch_op.f("ix_team_rankings_team_code"))
        batch_op.drop_index(batch_op.f("ix_team_rankings_team_name"))
        batch_op.drop_index(batch_op.f("ix_team_rankings_team_id"))
        batch_op.drop_index(batch_op.f("ix_team_rankings_snapshot_id"))
    op.drop_table("team_rankings")

    with op.batch_alter_table("ranking_source_logs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ranking_source_logs_data_version"))
        batch_op.drop_index(batch_op.f("ix_ranking_source_logs_ranking_id"))
        batch_op.drop_index(batch_op.f("ix_ranking_source_logs_status"))
    op.drop_table("ranking_source_logs")
