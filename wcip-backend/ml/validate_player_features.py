"""Validate player data coverage and player-derived ML features."""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.base import SessionLocal  # noqa: E402
from app.models.player import Player  # noqa: E402
from etl.transform.normalize import canonical  # noqa: E402
from ml.features import (  # noqa: E402
    BASE_FEATURE_COUNT,
    FEATURE_NAMES,
    build_feature_vector,
    _get_player_strength_stats,
    _position_group,
)
from wcip.data.wc2026 import list_qualified_team_names  # noqa: E402


PLAYER_FEATURE_KEYS = [
    "average_starting_xi_rating",
    "average_squad_rating",
    "top_5_player_rating_avg",
    "goalkeeper_rating",
    "defensive_unit_rating",
    "midfield_unit_rating",
    "attacking_unit_rating",
    "squad_depth_score",
    "star_player_score",
    "injury_burden_score",
    "player_form_score",
    "player_availability_score",
    "international_experience_score",
    "average_caps",
    "total_international_goals",
    "weighted_player_strength",
]


@dataclass
class PlayerFeatureCheck:
    name: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def validate_player_features(
    *,
    min_players_per_team: int = 18,
    null_heavy_threshold: float = 0.80,
) -> dict[str, Any]:
    checks: list[PlayerFeatureCheck] = []

    def add(status: str, name: str, message: str, **details: Any) -> None:
        checks.append(PlayerFeatureCheck(name=name, status=status, message=message, details=details))

    qualified = [canonical(name) for name in list_qualified_team_names(confirmed_only=True)]
    expected_feature_order = [f"{name}_diff" for name in PLAYER_FEATURE_KEYS]
    actual_player_features = FEATURE_NAMES[BASE_FEATURE_COUNT:]
    if actual_player_features == expected_feature_order:
        add("PASS", "feature_order", "Player feature order matches inference/training schema.", count=len(actual_player_features))
    else:
        add(
            "FAIL",
            "feature_order",
            "Player feature order does not match the expected schema.",
            expected=expected_feature_order,
            actual=actual_player_features,
        )

    db = SessionLocal()
    try:
        players = db.query(Player).all()
    finally:
        db.close()

    if not players:
        add("WARN", "player_records", "No player rows found; inference will use neutral player-strength fallbacks.")
    else:
        add("PASS", "player_records", "Player rows are present.", count=len(players))

    by_team: dict[str, list[Player]] = defaultdict(list)
    for player in players:
        by_team[canonical(player.team_name)].append(player)

    missing_or_sparse = {
        team: len(by_team.get(team, []))
        for team in qualified
        if len(by_team.get(team, [])) < min_players_per_team
    }
    if missing_or_sparse:
        add(
            "WARN",
            "missing_players_per_team",
            "Some WC2026 teams have sparse or missing player records.",
            min_players_per_team=min_players_per_team,
            missing_or_sparse=missing_or_sparse,
        )
    else:
        add("PASS", "missing_players_per_team", "Every WC2026 team has enough player records.", team_count=len(qualified))

    duplicates = [
        {"team": team, "player": name, "count": count}
        for (team, name), count in Counter(
            (canonical(player.team_name), player.name.strip().lower()) for player in players
        ).items()
        if count > 1
    ]
    if duplicates:
        add("FAIL", "duplicate_players", "Duplicate player rows found for the same team.", duplicates=duplicates[:50])
    else:
        add("PASS", "duplicate_players", "No duplicate player rows found.")

    invalid_ratings: list[dict[str, Any]] = []
    invalid_scores: list[dict[str, Any]] = []
    missing_positions: list[dict[str, Any]] = []
    invalid_dates: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for player in players:
        rating = player.player_rating if player.player_rating is not None else player.ea_fc_rating
        if rating is not None and not (0 <= float(rating) <= 100):
            invalid_ratings.append({"player": player.name, "team": player.team_name, "rating": rating})
        if player.fitness_score is not None and not (0 <= float(player.fitness_score) <= 1):
            invalid_scores.append({"player": player.name, "team": player.team_name, "field": "fitness_score", "value": player.fitness_score})
        if player.recent_form_score is not None and not (0 <= float(player.recent_form_score) <= 1):
            invalid_scores.append({"player": player.name, "team": player.team_name, "field": "recent_form_score", "value": player.recent_form_score})
        if _position_group(player.position) == "UNK":
            missing_positions.append({"player": player.name, "team": player.team_name, "position": player.position})
        if player.updated_at and player.updated_at.replace(tzinfo=player.updated_at.tzinfo or timezone.utc) > now:
            invalid_dates.append({"player": player.name, "team": player.team_name, "updated_at": player.updated_at.isoformat()})

    if invalid_ratings:
        add("FAIL", "invalid_ratings", "Player ratings outside 0-100 were found.", rows=invalid_ratings[:50])
    else:
        add("PASS", "invalid_ratings", "All available player ratings are in the expected 0-100 range.")

    if invalid_scores:
        add("FAIL", "invalid_scores", "Player form/fitness scores outside 0-1 were found.", rows=invalid_scores[:50])
    else:
        add("PASS", "invalid_scores", "All player form/fitness scores are in the expected 0-1 range.")

    if missing_positions:
        add("WARN", "missing_positions", "Some players have unmapped or missing positions.", rows=missing_positions[:50])
    else:
        add("PASS", "missing_positions", "All player positions map to GK/DEF/MID/FWD groups.")

    if invalid_dates:
        add("FAIL", "invalid_dates", "Some player updated_at values are in the future.", rows=invalid_dates[:50])
    else:
        add("PASS", "invalid_dates", "Player timestamps are not in the future.")

    player_teams = set(by_team)
    unmapped_teams = sorted(team for team in player_teams if qualified and team not in qualified)
    if unmapped_teams:
        add("WARN", "team_mapping", "Player rows include teams outside the current WC2026 field.", teams=unmapped_teams[:50])
    else:
        add("PASS", "team_mapping", "Player team names map to the current WC2026 field.")

    for field_name in ["age", "club", "market_value_eur", "player_rating", "ea_fc_rating", "data_source"]:
        if not players:
            continue
        null_count = sum(1 for player in players if getattr(player, field_name) in (None, ""))
        ratio = null_count / len(players)
        status = "WARN" if ratio >= null_heavy_threshold else "PASS"
        add(
            status,
            f"null_heavy_{field_name}",
            f"{field_name} null ratio is {ratio:.1%}.",
            null_count=null_count,
            row_count=len(players),
            threshold=null_heavy_threshold,
        )

    finite_failures: list[dict[str, Any]] = []
    teams_to_check = qualified[:]
    if not teams_to_check and by_team:
        teams_to_check = sorted(by_team)[:48]
    for team in teams_to_check:
        stats = _get_player_strength_stats(team)
        bad_keys = [
            key for key, value in stats.items()
            if not isinstance(value, (int, float)) or not math.isfinite(float(value))
        ]
        if bad_keys:
            finite_failures.append({"team": team, "bad_keys": bad_keys})
    if finite_failures:
        add("FAIL", "player_strength_stats", "Player-strength aggregation returned non-finite values.", rows=finite_failures[:50])
    else:
        add("PASS", "player_strength_stats", "Player-strength aggregation returns finite values.")

    if len(teams_to_check) >= 2:
        fv = build_feature_vector(teams_to_check[0], teams_to_check[1])
        player_slice = fv.features[BASE_FEATURE_COUNT:]
        if np.isnan(player_slice).any() or np.isinf(player_slice).any():
            add("FAIL", "feature_vector_values", "Player feature slice contains NaN or infinite values.")
        else:
            add(
                "PASS",
                "feature_vector_values",
                "Player feature slice is finite for a representative match.",
                home=teams_to_check[0],
                away=teams_to_check[1],
            )

    overall = "FAIL" if any(check.status == "FAIL" for check in checks) else "PASS"
    return {
        "status": overall,
        "player_rows": len(players),
        "qualified_teams": len(qualified),
        "checks": [check.__dict__ for check in checks],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate WCIP player-derived ML features.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--min-players-per-team", type=int, default=18)
    parser.add_argument("--null-heavy-threshold", type=float, default=0.80)
    args = parser.parse_args()

    report = validate_player_features(
        min_players_per_team=args.min_players_per_team,
        null_heavy_threshold=args.null_heavy_threshold,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Player feature validation: {report['status']}")
        for check in report["checks"]:
            details = f" {json.dumps(check['details'], sort_keys=True)}" if check["details"] else ""
            print(f"[{check['status']}] {check['name']}: {check['message']}{details}")
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
