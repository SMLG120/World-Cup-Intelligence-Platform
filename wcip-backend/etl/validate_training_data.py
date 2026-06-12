"""Validate WCIP training and prediction data readiness.

Run from the backend directory:

    python etl/validate_training_data.py

The validator is intentionally conservative. It reports data quality failures
that can bias model training, inference, Elo recalibration, and simulations.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable

from sqlalchemy import func, select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.base import SessionLocal  # noqa: E402
from app.models.match_result import MatchFeatures, MatchResult, MLModelRecord, QualifiedTeam  # noqa: E402
from app.models.player import Coach, Player  # noqa: E402
from app.models.ranking import FifaRankingSnapshot, TeamRanking  # noqa: E402
from app.models.team import EloHistory, Team  # noqa: E402


@dataclass
class Check:
    name: str
    status: str
    message: str
    details: dict = field(default_factory=dict)


class ValidationReport:
    def __init__(self) -> None:
        self.checks: list[Check] = []

    def pass_(self, name: str, message: str, **details) -> None:
        self.checks.append(Check(name, "PASS", message, details))

    def warn(self, name: str, message: str, **details) -> None:
        self.checks.append(Check(name, "WARN", message, details))

    def fail(self, name: str, message: str, **details) -> None:
        self.checks.append(Check(name, "FAIL", message, details))

    @property
    def failed(self) -> bool:
        return any(check.status == "FAIL" for check in self.checks)

    def as_dict(self) -> dict:
        return {
            "status": "FAIL" if self.failed else "PASS",
            "checks": [
                {
                    "name": check.name,
                    "status": check.status,
                    "message": check.message,
                    "details": check.details,
                }
                for check in self.checks
            ],
        }

    def print_text(self) -> None:
        print(f"Training data validation: {'FAIL' if self.failed else 'PASS'}")
        for check in self.checks:
            detail = f" {json.dumps(check.details, sort_keys=True)}" if check.details else ""
            print(f"[{check.status}] {check.name}: {check.message}{detail}")


def validate_training_data(*, null_threshold: float = 0.35) -> ValidationReport:
    report = ValidationReport()
    today = date.today()

    with SessionLocal() as db:
        teams = db.scalars(select(Team)).all()
        qualified = db.scalars(select(QualifiedTeam).where(QualifiedTeam.tournament_year == 2026)).all()
        team_names = {team.name for team in teams}
        qualified_names = {team.team_name for team in qualified}

        _check_teams(report, teams, qualified, team_names, qualified_names)
        _check_rankings(report, db, team_names, qualified_names, today)
        _check_elo(report, db, teams)
        _check_players_and_coaches(report, db, qualified_names)
        _check_results_and_features(report, db, team_names, today, null_threshold)
        _check_models(report, db)

    return report


def _check_teams(
    report: ValidationReport,
    teams: list[Team],
    qualified: list[QualifiedTeam],
    team_names: set[str],
    qualified_names: set[str],
) -> None:
    if len(teams) < 48:
        report.fail("team_count", "Fewer than 48 teams are available.", count=len(teams))
    else:
        report.pass_("team_count", "Team registry has enough teams.", count=len(teams))

    duplicate_names = _duplicates(team.name for team in teams)
    duplicate_codes = _duplicates(team.code for team in teams if team.code)
    if duplicate_names or duplicate_codes:
        report.fail(
            "duplicate_teams",
            "Duplicate team names or FIFA codes were found.",
            names=duplicate_names,
            codes=duplicate_codes,
        )
    else:
        report.pass_("duplicate_teams", "No duplicate team names or FIFA codes found.")

    missing_qualified = sorted(qualified_names - team_names)
    if missing_qualified:
        report.fail(
            "qualified_team_mappings",
            "Qualified teams missing from teams table.",
            teams=missing_qualified[:25],
            count=len(missing_qualified),
        )
    else:
        report.pass_("qualified_team_mappings", "All 2026 qualified teams map to team records.")

    if len(qualified) < 48:
        report.warn("qualified_teams", "World Cup 2026 field has fewer than 48 teams.", count=len(qualified))
    else:
        report.pass_("qualified_teams", "World Cup 2026 field has 48 teams.", count=len(qualified))


def _check_rankings(
    report: ValidationReport,
    db,
    team_names: set[str],
    qualified_names: set[str],
    today: date,
) -> None:
    current = db.scalars(
        select(FifaRankingSnapshot)
        .where(FifaRankingSnapshot.is_current.is_(True))
        .order_by(FifaRankingSnapshot.ranking_date.desc())
    ).first()
    if not current:
        report.fail("fifa_snapshot", "No current FIFA ranking snapshot is loaded.")
    elif current.ranking_date > today:
        report.fail(
            "fifa_snapshot_date",
            "Current FIFA ranking snapshot is dated in the future.",
            ranking_date=str(current.ranking_date),
            today=str(today),
        )
    else:
        report.pass_(
            "fifa_snapshot",
            "Current FIFA ranking snapshot is available.",
            ranking_date=str(current.ranking_date),
            ranking_id=current.ranking_id,
            team_count=current.team_count,
        )

    ranked_teams = set(
        db.scalars(
            select(TeamRanking.team_name).where(TeamRanking.ranking_provider == "FIFA")
        ).all()
    )
    missing_rankings = sorted(qualified_names - ranked_teams)
    if missing_rankings:
        report.fail(
            "missing_qualified_rankings",
            "Qualified teams missing FIFA ranking records.",
            teams=missing_rankings[:25],
            count=len(missing_rankings),
        )
    else:
        report.pass_("missing_qualified_rankings", "All qualified teams have FIFA ranking records.")

    bad_team_ranks = [
        team.name
        for team in db.scalars(select(Team).where((Team.fifa_rank <= 0) | (Team.fifa_rank.is_(None)))).all()
    ]
    if bad_team_ranks:
        report.fail(
            "invalid_team_fifa_rank",
            "Team table contains missing or invalid fifa_rank values.",
            teams=bad_team_ranks[:25],
            count=len(bad_team_ranks),
        )
    else:
        report.pass_("invalid_team_fifa_rank", "Team fifa_rank values are populated.")


def _check_elo(report: ValidationReport, db, teams: list[Team]) -> None:
    invalid = [team.name for team in teams if team.elo is None or team.elo <= 0]
    neutral = [team.name for team in teams if abs(float(team.elo or 0) - 1500.0) < 1e-6]
    if invalid:
        report.fail("invalid_elo", "Teams have missing or invalid Elo ratings.", teams=invalid[:25], count=len(invalid))
    else:
        report.pass_("invalid_elo", "Team Elo ratings are positive.")

    if neutral:
        report.warn(
            "neutral_elo_defaults",
            "Some teams still have neutral default Elo ratings.",
            teams=neutral[:25],
            count=len(neutral),
        )
    else:
        report.pass_("neutral_elo_defaults", "No team is stuck at neutral default Elo.")

    history_count = db.scalar(select(func.count()).select_from(EloHistory)) or 0
    if history_count == 0:
        report.fail("elo_history", "No Elo history records are available.")
    else:
        report.pass_("elo_history", "Elo history records are available.", count=history_count)


def _check_players_and_coaches(report: ValidationReport, db, qualified_names: set[str]) -> None:
    player_rows = db.scalars(select(Player)).all()
    player_teams = {player.team_name for player in player_rows}
    missing_player_teams = sorted(qualified_names - player_teams)
    if missing_player_teams:
        report.fail(
            "missing_player_records",
            "Qualified teams missing player records.",
            teams=missing_player_teams[:25],
            count=len(missing_player_teams),
        )
    else:
        report.pass_("missing_player_records", "All qualified teams have player records.")

    duplicate_players = db.execute(
        select(Player.team_name, Player.name, func.count())
        .group_by(Player.team_name, Player.name)
        .having(func.count() > 1)
    ).all()
    if duplicate_players:
        report.fail(
            "duplicate_players",
            "Duplicate players found within a team.",
            players=[{"team": t, "name": n, "count": c} for t, n, c in duplicate_players[:25]],
            count=len(duplicate_players),
        )
    else:
        report.pass_("duplicate_players", "No duplicate players found within teams.")

    rated_count = db.scalar(select(func.count()).select_from(Player).where(Player.player_rating.is_not(None))) or 0
    if player_rows and rated_count / len(player_rows) < 0.60:
        report.fail(
            "player_ratings",
            "Most player rows are missing player_rating values.",
            rated=rated_count,
            total=len(player_rows),
        )
    else:
        report.pass_("player_ratings", "Player ratings coverage is acceptable.", rated=rated_count, total=len(player_rows))

    market_count = db.scalar(select(func.count()).select_from(Player).where(Player.market_value_eur.is_not(None))) or 0
    if player_rows and market_count / len(player_rows) < 0.60:
        report.warn(
            "squad_market_values",
            "Most player rows are missing market values; squad value features may be weak.",
            populated=market_count,
            total=len(player_rows),
        )
    else:
        report.pass_("squad_market_values", "Squad market value coverage is acceptable.", populated=market_count)

    coach_teams = set(db.scalars(select(Coach.team_name)).all())
    missing_coaches = sorted(qualified_names - coach_teams)
    if missing_coaches:
        report.fail("missing_coaches", "Qualified teams missing coach records.", teams=missing_coaches[:25], count=len(missing_coaches))
    else:
        report.pass_("missing_coaches", "All qualified teams have coach records.")


def _check_results_and_features(
    report: ValidationReport,
    db,
    team_names: set[str],
    today: date,
    null_threshold: float,
) -> None:
    result_count = db.scalar(select(func.count()).select_from(MatchResult)) or 0
    if result_count == 0:
        report.fail("match_results", "No historical match results are available.")
    else:
        report.pass_("match_results", "Historical match results are available.", count=result_count)

    future_matches = db.scalar(
        select(func.count()).select_from(MatchResult).where(MatchResult.match_date > today)
    ) or 0
    if future_matches:
        report.fail("future_match_results", "Historical match table contains future-dated rows.", count=future_matches)
    else:
        report.pass_("future_match_results", "No future-dated match results found.")

    unknown_home = sorted(set(db.scalars(select(MatchResult.home_team)).all()) - team_names)
    unknown_away = sorted(set(db.scalars(select(MatchResult.away_team)).all()) - team_names)
    unknown = sorted(set(unknown_home) | set(unknown_away))
    if unknown:
        report.warn(
            "historical_country_mappings",
            "Historical result countries are not all present in the current teams table.",
            teams=unknown[:25],
            count=len(unknown),
        )
    else:
        report.pass_("historical_country_mappings", "Historical match countries map to team records.")

    feature_count = db.scalar(select(func.count()).select_from(MatchFeatures)) or 0
    if feature_count == 0:
        report.warn("match_features", "No precomputed feature-store rows found; inference may compute features on demand.")
        return

    report.pass_("match_features", "Precomputed feature-store rows are available.", count=feature_count)
    for column in _feature_columns():
        populated = db.scalar(
            select(func.count()).select_from(MatchFeatures).where(column.is_not(None))
        ) or 0
        null_ratio = 1.0 - (populated / feature_count)
        if null_ratio > null_threshold:
            report.fail(
                "null_heavy_feature_column",
                f"Feature column {column.key} is null-heavy.",
                column=column.key,
                null_ratio=round(null_ratio, 4),
            )

    future_features = db.scalar(
        select(func.count()).select_from(MatchFeatures).where(MatchFeatures.match_date > today)
    ) or 0
    if future_features:
        report.fail("future_match_features", "Feature store contains future-dated rows.", count=future_features)
    else:
        report.pass_("future_match_features", "No future-dated feature-store rows found.")


def _check_models(report: ValidationReport, db) -> None:
    active_models = db.scalars(select(MLModelRecord).where(MLModelRecord.is_active.is_(True))).all()
    expected = {"logistic", "random_forest", "xgboost", "lightgbm", "catboost"}
    active_names = {model.model_name for model in active_models}
    missing = sorted(expected - active_names)
    if missing:
        report.fail("active_models", "Expected active model registry entries are missing.", models=missing)
    else:
        report.pass_("active_models", "All expected active model registry entries exist.", count=len(active_models))

    weak_metrics = [
        model.model_name
        for model in active_models
        if model.log_loss is None or model.brier_score is None or model.ensemble_weight is None
    ]
    if weak_metrics:
        report.fail(
            "model_metrics",
            "Active models are missing validation metrics or ensemble weights.",
            models=weak_metrics,
        )
    else:
        report.pass_("model_metrics", "Active models include validation metrics and ensemble weights.")

    feature_versions = sorted({model.feature_version for model in active_models})
    if len(feature_versions) > 1:
        report.warn("model_feature_versions", "Active models use mixed feature versions.", versions=feature_versions)
    elif feature_versions:
        report.pass_("model_feature_versions", "Active models use one feature version.", version=feature_versions[0])


def _feature_columns():
    return [
        column
        for column in MatchFeatures.__table__.columns
        if column.name not in {"id", "match_result_id", "home_team", "away_team", "match_date", "feature_version", "computed_at"}
    ]


def _duplicates(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return sorted(dupes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate WCIP training and inference data.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    parser.add_argument("--null-threshold", type=float, default=0.35, help="Fail columns above this null ratio.")
    args = parser.parse_args()

    report = validate_training_data(null_threshold=args.null_threshold)
    if args.json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        report.print_text()
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
