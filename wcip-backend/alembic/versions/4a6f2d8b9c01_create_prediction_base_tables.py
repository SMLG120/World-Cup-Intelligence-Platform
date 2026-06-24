"""create prediction base tables

Revision ID: 4a6f2d8b9c01
Revises: 3f8b9d9c2a11
Create Date: 2026-06-24 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4a6f2d8b9c01"
down_revision: Union[str, None] = "3f8b9d9c2a11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if "players" not in existing:
        op.create_table(
            "players",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("team_name", sa.String(length=120), nullable=False),
            sa.Column("position", sa.String(length=30), nullable=False),
            sa.Column("club", sa.String(length=120), nullable=True),
            sa.Column("age", sa.Integer(), nullable=True),
            sa.Column("nationality", sa.String(length=120), nullable=True),
            sa.Column("minutes_played", sa.Float(), nullable=False),
            sa.Column("goals", sa.Float(), nullable=False),
            sa.Column("assists", sa.Float(), nullable=False),
            sa.Column("xg", sa.Float(), nullable=False),
            sa.Column("xag", sa.Float(), nullable=False),
            sa.Column("key_passes", sa.Float(), nullable=False),
            sa.Column("shots_on_target", sa.Float(), nullable=False),
            sa.Column("progressive_passes", sa.Float(), nullable=False),
            sa.Column("progressive_carries", sa.Float(), nullable=False),
            sa.Column("tackles", sa.Float(), nullable=False),
            sa.Column("interceptions", sa.Float(), nullable=False),
            sa.Column("clearances", sa.Float(), nullable=False),
            sa.Column("yellow_cards", sa.Integer(), nullable=False),
            sa.Column("red_cards", sa.Integer(), nullable=False),
            sa.Column("injured", sa.Boolean(), nullable=False),
            sa.Column("suspended", sa.Boolean(), nullable=False),
            sa.Column("injury_notes", sa.Text(), nullable=True),
            sa.Column("market_value_eur", sa.Float(), nullable=True),
            sa.Column("international_caps", sa.Integer(), nullable=False),
            sa.Column("international_goals", sa.Integer(), nullable=False),
            sa.Column("recent_form_score", sa.Float(), nullable=False),
            sa.Column("fitness_score", sa.Float(), nullable=False),
            sa.Column("data_source", sa.String(length=80), nullable=True),
            sa.Column("external_id", sa.String(length=80), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("players", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_players_name"), ["name"], unique=False)
            batch_op.create_index(batch_op.f("ix_players_team_name"), ["team_name"], unique=False)
            batch_op.create_index(batch_op.f("ix_players_external_id"), ["external_id"], unique=False)

    if "coaches" not in existing:
        op.create_table(
            "coaches",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("team_name", sa.String(length=120), nullable=False),
            sa.Column("nationality", sa.String(length=120), nullable=True),
            sa.Column("preferred_formation", sa.String(length=20), nullable=True),
            sa.Column("win_pct", sa.Float(), nullable=False),
            sa.Column("draw_pct", sa.Float(), nullable=False),
            sa.Column("loss_pct", sa.Float(), nullable=False),
            sa.Column("matches_managed", sa.Integer(), nullable=False),
            sa.Column("tournament_experience", sa.Integer(), nullable=False),
            sa.Column("knockout_record", sa.Float(), nullable=False),
            sa.Column("tactical_flexibility", sa.Float(), nullable=False),
            sa.Column("recent_form_score", sa.Float(), nullable=False),
            sa.Column("impact_score", sa.Float(), nullable=False),
            sa.Column("data_source", sa.String(length=80), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("coaches", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_coaches_name"), ["name"], unique=False)
            batch_op.create_index(batch_op.f("ix_coaches_team_name"), ["team_name"], unique=True)

    if "match_results" not in existing:
        op.create_table(
            "match_results",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("match_date", sa.Date(), nullable=False),
            sa.Column("home_team", sa.String(length=120), nullable=False),
            sa.Column("away_team", sa.String(length=120), nullable=False),
            sa.Column("home_goals", sa.Integer(), nullable=False),
            sa.Column("away_goals", sa.Integer(), nullable=False),
            sa.Column("tournament", sa.String(length=120), nullable=True),
            sa.Column("city", sa.String(length=120), nullable=True),
            sa.Column("country", sa.String(length=120), nullable=True),
            sa.Column("neutral", sa.Boolean(), nullable=False),
            sa.Column("outcome", sa.Integer(), nullable=True),
            sa.Column("data_source", sa.String(length=80), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("home_team", "away_team", "match_date", name="uq_match"),
        )
        with op.batch_alter_table("match_results", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_match_results_match_date"), ["match_date"], unique=False)
            batch_op.create_index(batch_op.f("ix_match_results_home_team"), ["home_team"], unique=False)
            batch_op.create_index(batch_op.f("ix_match_results_away_team"), ["away_team"], unique=False)

    if "match_features" not in existing:
        op.create_table(
            "match_features",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("match_result_id", sa.Integer(), nullable=True),
            sa.Column("home_team", sa.String(length=120), nullable=False),
            sa.Column("away_team", sa.String(length=120), nullable=False),
            sa.Column("match_date", sa.Date(), nullable=False),
            sa.Column("elo_diff", sa.Float(), nullable=False),
            sa.Column("fifa_rank_diff", sa.Float(), nullable=False),
            sa.Column("xg_diff", sa.Float(), nullable=False),
            sa.Column("xga_diff", sa.Float(), nullable=False),
            sa.Column("goals_scored_diff", sa.Float(), nullable=False),
            sa.Column("goals_conceded_diff", sa.Float(), nullable=False),
            sa.Column("form_diff", sa.Float(), nullable=False),
            sa.Column("avg_age_diff", sa.Float(), nullable=False),
            sa.Column("market_value_diff", sa.Float(), nullable=False),
            sa.Column("injury_burden_diff", sa.Float(), nullable=False),
            sa.Column("coach_impact_diff", sa.Float(), nullable=False),
            sa.Column("squad_chemistry_diff", sa.Float(), nullable=False),
            sa.Column("travel_distance_km", sa.Float(), nullable=False),
            sa.Column("rest_days", sa.Float(), nullable=False),
            sa.Column("tournament_exp_diff", sa.Float(), nullable=False),
            sa.Column("starting_xi_strength_diff", sa.Float(), nullable=False),
            sa.Column("bench_strength_diff", sa.Float(), nullable=False),
            sa.Column("feature_version", sa.String(length=20), nullable=False),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("match_features", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_match_features_match_result_id"), ["match_result_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_match_features_home_team"), ["home_team"], unique=False)
            batch_op.create_index(batch_op.f("ix_match_features_away_team"), ["away_team"], unique=False)
            batch_op.create_index(batch_op.f("ix_match_features_match_date"), ["match_date"], unique=False)

    if "ml_models" not in existing:
        op.create_table(
            "ml_models",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("model_name", sa.String(length=80), nullable=False),
            sa.Column("version", sa.String(length=40), nullable=False),
            sa.Column("file_path", sa.String(length=255), nullable=False),
            sa.Column("accuracy", sa.Float(), nullable=True),
            sa.Column("f1_score", sa.Float(), nullable=True),
            sa.Column("brier_score", sa.Float(), nullable=True),
            sa.Column("log_loss", sa.Float(), nullable=True),
            sa.Column("calibration_score", sa.Float(), nullable=True),
            sa.Column("ensemble_weight", sa.Float(), nullable=False),
            sa.Column("feature_version", sa.String(length=20), nullable=False),
            sa.Column("training_samples", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("ml_models", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_ml_models_model_name"), ["model_name"], unique=False)

    if "qualified_teams" not in existing:
        op.create_table(
            "qualified_teams",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("team_name", sa.String(length=120), nullable=False),
            sa.Column("team_code", sa.String(length=3), nullable=False),
            sa.Column("confederation", sa.String(length=20), nullable=False),
            sa.Column("tournament_year", sa.Integer(), nullable=False),
            sa.Column("group_label", sa.String(length=5), nullable=True),
            sa.Column("pot", sa.Integer(), nullable=True),
            sa.Column("qualified_date", sa.Date(), nullable=True),
            sa.Column("qualification_path", sa.String(length=120), nullable=True),
            sa.Column("host_nation", sa.Boolean(), nullable=False),
            sa.Column("confirmed", sa.Boolean(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("qualified_teams", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_qualified_teams_team_name"), ["team_name"], unique=True)


def downgrade() -> None:
    for table_name in (
        "qualified_teams",
        "ml_models",
        "match_features",
        "match_results",
        "coaches",
        "players",
    ):
        op.drop_table(table_name)
