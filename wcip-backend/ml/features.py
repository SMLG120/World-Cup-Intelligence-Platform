"""Feature engineering pipeline.

Builds a 17-feature vector for any (home_team, away_team, date) triplet.
Features are expressed as (home - away) differentials so a positive value
always favours the home team.

Feature list (v1):
  0  elo_diff
  1  fifa_rank_diff          (negative = home team has better rank, inverted)
  2  xg_diff                 (last-10-match avg xG)
  3  xga_diff                (last-10-match avg xGA — negative = better defence)
  4  goals_scored_diff
  5  goals_conceded_diff
  6  form_diff               (points from last 5 competitive matches)
  7  avg_age_diff
  8  market_value_diff       (log10)
  9  injury_burden_diff      (injured starters ratio)
 10  coach_impact_diff
 11  squad_chemistry_diff
 12  travel_distance_km      (absolute km for home team travel to venue)
 13  rest_days               (home team rest days since last match)
 14  tournament_exp_diff     (WC appearances)
 15  starting_xi_strength_diff
 16  bench_strength_diff
"""
from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Dict, List, NamedTuple, Optional

import numpy as np

logger = logging.getLogger(__name__)

FEATURE_VERSION = "v1"
FEATURE_NAMES = [
    "elo_diff",
    "fifa_rank_diff",
    "xg_diff",
    "xga_diff",
    "goals_scored_diff",
    "goals_conceded_diff",
    "form_diff",
    "avg_age_diff",
    "market_value_diff",
    "injury_burden_diff",
    "coach_impact_diff",
    "squad_chemistry_diff",
    "travel_distance_km",
    "rest_days",
    "tournament_exp_diff",
    "starting_xi_strength_diff",
    "bench_strength_diff",
]

N_FEATURES = len(FEATURE_NAMES)


class FeatureVector(NamedTuple):
    home_team: str
    away_team: str
    match_date: date
    features: np.ndarray     # shape (N_FEATURES,)
    version: str = FEATURE_VERSION


# ---------------------------------------------------------------------------
# Team stat caches (populated from DB)
# ---------------------------------------------------------------------------

def _get_team_elo(team_name: str) -> float:
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.team import Team
        db = SessionLocal()
        try:
            t = db.scalar(select(Team).where(Team.name == team_name))
            return t.elo if t else 1500.0
        finally:
            db.close()
    except Exception:
        return 1500.0


def _get_team_fifa_rank(team_name: str) -> int:
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.team import Team
        db = SessionLocal()
        try:
            t = db.scalar(select(Team).where(Team.name == team_name))
            return t.fifa_rank if t else 100
        finally:
            db.close()
    except Exception:
        return 100


def _get_recent_match_stats(
    team_name: str,
    before_date: date,
    n_matches: int = 10,
) -> Dict[str, float]:
    """Return avg xG, xGA, goals scored, goals conceded from last n matches."""
    try:
        from sqlalchemy import or_, select
        from app.db.base import SessionLocal
        from app.models.match_result import MatchResult
        db = SessionLocal()
        try:
            rows = db.scalars(
                select(MatchResult)
                .where(
                    or_(
                        MatchResult.home_team == team_name,
                        MatchResult.away_team == team_name,
                    ),
                    MatchResult.match_date < before_date,
                )
                .order_by(MatchResult.match_date.desc())
                .limit(n_matches)
            ).all()

            if not rows:
                return {"xg": 1.35, "xga": 1.35, "gf": 1.2, "ga": 1.2}

            gf, ga = [], []
            for r in rows:
                if r.home_team == team_name:
                    gf.append(r.home_goals)
                    ga.append(r.away_goals)
                else:
                    gf.append(r.away_goals)
                    ga.append(r.home_goals)

            avg_gf = float(np.mean(gf)) if gf else 1.2
            avg_ga = float(np.mean(ga)) if ga else 1.2
            return {"xg": avg_gf, "xga": avg_ga, "gf": avg_gf, "ga": avg_ga}
        finally:
            db.close()
    except Exception as e:
        logger.debug("Recent match stats failed for %s: %s", team_name, e)
        return {"xg": 1.35, "xga": 1.35, "gf": 1.2, "ga": 1.2}


def _get_form(team_name: str, before_date: date, n: int = 5) -> float:
    """Return points per game from last n competitive matches (0..3)."""
    try:
        from sqlalchemy import or_, select
        from app.db.base import SessionLocal
        from app.models.match_result import MatchResult
        db = SessionLocal()
        try:
            rows = db.scalars(
                select(MatchResult)
                .where(
                    or_(
                        MatchResult.home_team == team_name,
                        MatchResult.away_team == team_name,
                    ),
                    MatchResult.match_date < before_date,
                    MatchResult.tournament.isnot(None),
                )
                .order_by(MatchResult.match_date.desc())
                .limit(n)
            ).all()

            if not rows:
                return 1.0  # neutral default

            pts = []
            for r in rows:
                if r.home_team == team_name:
                    if r.home_goals > r.away_goals:
                        pts.append(3)
                    elif r.home_goals == r.away_goals:
                        pts.append(1)
                    else:
                        pts.append(0)
                else:
                    if r.away_goals > r.home_goals:
                        pts.append(3)
                    elif r.away_goals == r.home_goals:
                        pts.append(1)
                    else:
                        pts.append(0)

            return float(np.mean(pts))
        finally:
            db.close()
    except Exception:
        return 1.0


def _get_squad_stats(team_name: str) -> Dict[str, float]:
    """Return aggregated squad stats from the players table."""
    try:
        from sqlalchemy import func, select
        from app.db.base import SessionLocal
        from app.models.player import Player
        db = SessionLocal()
        try:
            rows = db.scalars(
                select(Player).where(Player.team_name == team_name)
            ).all()
            if not rows:
                return {
                    "avg_age": 27.0,
                    "market_value_log": 8.0,
                    "injury_burden": 0.0,
                    "avg_fitness": 1.0,
                }
            ages = [p.age for p in rows if p.age]
            mvs = [p.market_value_eur for p in rows if p.market_value_eur and p.market_value_eur > 0]
            injured_count = sum(1 for p in rows if p.injured)
            fitness_scores = [p.fitness_score for p in rows]

            avg_age = float(np.mean(ages)) if ages else 27.0
            total_mv = sum(mvs) if mvs else 1e8
            market_value_log = math.log10(max(total_mv, 1.0))
            injury_burden = injured_count / max(len(rows), 1)
            avg_fitness = float(np.mean(fitness_scores)) if fitness_scores else 1.0

            return {
                "avg_age": avg_age,
                "market_value_log": market_value_log,
                "injury_burden": injury_burden,
                "avg_fitness": avg_fitness,
            }
        finally:
            db.close()
    except Exception:
        return {
            "avg_age": 27.0,
            "market_value_log": 8.0,
            "injury_burden": 0.0,
            "avg_fitness": 1.0,
        }


def _get_coach_impact(team_name: str) -> float:
    """Return the coach impact score for a team."""
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.player import Coach
        db = SessionLocal()
        try:
            coach = db.scalar(select(Coach).where(Coach.team_name == team_name))
            return coach.impact_score if coach else 1.0
        finally:
            db.close()
    except Exception:
        return 1.0


def _get_team_chemistry(team_name: str) -> float:
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.team import Team
        db = SessionLocal()
        try:
            t = db.scalar(select(Team).where(Team.name == team_name))
            return t.chemistry if t else 1.0
        finally:
            db.close()
    except Exception:
        return 1.0


def _get_tournament_experience(team_name: str) -> int:
    """Count World Cup appearances from historical match results."""
    try:
        from sqlalchemy import func, or_, select
        from app.db.base import SessionLocal
        from app.models.match_result import MatchResult
        db = SessionLocal()
        try:
            count = db.scalar(
                select(func.count(MatchResult.id.distinct())).where(
                    or_(
                        MatchResult.home_team == team_name,
                        MatchResult.away_team == team_name,
                    ),
                    MatchResult.tournament.ilike("%FIFA World Cup%"),
                )
            ) or 0
            # Rough WC appearances: matches / ~7 avg per tournament
            return max(0, count // 7)
        finally:
            db.close()
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Main feature builder
# ---------------------------------------------------------------------------

def build_feature_vector(
    home_team: str,
    away_team: str,
    match_date: Optional[date] = None,
    home_overrides: Optional[Dict] = None,
    away_overrides: Optional[Dict] = None,
) -> FeatureVector:
    """Compute a full feature vector for a match.

    Overrides dict can contain any of the player/team modifier keys to
    simulate injury/suspension/form scenarios (Player Impact Lab).
    """
    if match_date is None:
        match_date = date.today()

    ho = home_overrides or {}
    ao = away_overrides or {}

    # Elo
    h_elo = ho.get("elo", _get_team_elo(home_team))
    a_elo = ao.get("elo", _get_team_elo(away_team))
    elo_diff = h_elo - a_elo

    # FIFA rank (lower = better, so invert)
    h_rank = ho.get("fifa_rank", _get_team_fifa_rank(home_team))
    a_rank = ao.get("fifa_rank", _get_team_fifa_rank(away_team))
    fifa_rank_diff = a_rank - h_rank  # positive = home has better rank

    # Recent match stats
    h_stats = _get_recent_match_stats(home_team, match_date)
    a_stats = _get_recent_match_stats(away_team, match_date)
    xg_diff = h_stats["xg"] - a_stats["xg"]
    xga_diff = h_stats["xga"] - a_stats["xga"]
    goals_scored_diff = h_stats["gf"] - a_stats["gf"]
    goals_conceded_diff = h_stats["ga"] - a_stats["ga"]

    # Form
    h_form = ho.get("form", _get_form(home_team, match_date))
    a_form = ao.get("form", _get_form(away_team, match_date))
    form_diff = h_form - a_form

    # Squad stats
    h_squad = _get_squad_stats(home_team)
    a_squad = _get_squad_stats(away_team)

    avg_age_diff = h_squad["avg_age"] - a_squad["avg_age"]
    market_value_diff = h_squad["market_value_log"] - a_squad["market_value_log"]

    h_injury = ho.get("injury_burden", h_squad["injury_burden"])
    a_injury = ao.get("injury_burden", a_squad["injury_burden"])
    injury_burden_diff = h_injury - a_injury

    # Coach
    h_coach = ho.get("coach_impact", _get_coach_impact(home_team))
    a_coach = ao.get("coach_impact", _get_coach_impact(away_team))
    coach_impact_diff = h_coach - a_coach

    # Chemistry
    h_chem = ho.get("chemistry", _get_team_chemistry(home_team))
    a_chem = ao.get("chemistry", _get_team_chemistry(away_team))
    squad_chemistry_diff = h_chem - a_chem

    # Travel & rest (simplified — 0 for now unless overridden)
    travel_distance_km = float(ho.get("travel_km", 0.0))
    rest_days = float(ho.get("rest_days", 7.0))

    # Tournament experience
    h_exp = ho.get("tournament_exp", _get_tournament_experience(home_team))
    a_exp = ao.get("tournament_exp", _get_tournament_experience(away_team))
    tournament_exp_diff = h_exp - a_exp

    # Starting XI / bench strength (proxy from squad stats)
    h_fitness = h_squad["avg_fitness"] * (1 - h_injury)
    a_fitness = a_squad["avg_fitness"] * (1 - a_injury)
    starting_xi_strength_diff = (h_elo / 2000) * h_fitness - (a_elo / 2000) * a_fitness
    bench_strength_diff = market_value_diff * 0.1  # proxy

    vec = np.array([
        elo_diff,
        fifa_rank_diff,
        xg_diff,
        xga_diff,
        goals_scored_diff,
        goals_conceded_diff,
        form_diff,
        avg_age_diff,
        market_value_diff,
        injury_burden_diff,
        coach_impact_diff,
        squad_chemistry_diff,
        travel_distance_km,
        rest_days,
        float(tournament_exp_diff),
        starting_xi_strength_diff,
        bench_strength_diff,
    ], dtype=np.float32)

    return FeatureVector(
        home_team=home_team,
        away_team=away_team,
        match_date=match_date,
        features=vec,
        version=FEATURE_VERSION,
    )


def build_feature_matrix_from_db(
    since_date: Optional[date] = None,
    max_rows: int = 50_000,
) -> tuple[np.ndarray, np.ndarray, list]:
    """Build X (feature matrix) and y (labels) from all historical match results.

    Returns (X, y, match_ids) for ML training.
    Uses a simplified/fast version without per-match Elo reconstruction to
    avoid O(n²) complexity. Elo diff is approximated by current team Elo ratings.
    """
    from sqlalchemy import select
    from app.db.base import SessionLocal
    from app.models.match_result import MatchResult

    db = SessionLocal()
    try:
        query = select(MatchResult).where(MatchResult.outcome.isnot(None))
        if since_date:
            query = query.where(MatchResult.match_date >= since_date)
        query = query.order_by(MatchResult.match_date.asc()).limit(max_rows)
        rows = db.scalars(query).all()

        X_list, y_list, ids = [], [], []
        for r in rows:
            fv = build_feature_vector(r.home_team, r.away_team, r.match_date)
            X_list.append(fv.features)
            y_list.append(r.outcome)
            ids.append(r.id)

        if not X_list:
            return np.empty((0, N_FEATURES), dtype=np.float32), np.empty(0, dtype=np.int32), []

        X = np.stack(X_list)
        y = np.array(y_list, dtype=np.int32)
        return X, y, ids
    finally:
        db.close()


def persist_features(home_team: str, away_team: str, match_date: date,
                     fv: FeatureVector, match_result_id: Optional[int] = None) -> None:
    """Save a computed feature vector to the match_features table."""
    from app.db.base import SessionLocal
    from app.models.match_result import MatchFeatures
    from sqlalchemy import select

    db = SessionLocal()
    try:
        existing = db.scalar(
            select(MatchFeatures).where(
                MatchFeatures.home_team == home_team,
                MatchFeatures.away_team == away_team,
                MatchFeatures.match_date == match_date,
            )
        )
        if existing:
            record = existing
        else:
            record = MatchFeatures(
                home_team=home_team,
                away_team=away_team,
                match_date=match_date,
                match_result_id=match_result_id,
            )
            db.add(record)

        f = fv.features
        record.elo_diff = float(f[0])
        record.fifa_rank_diff = float(f[1])
        record.xg_diff = float(f[2])
        record.xga_diff = float(f[3])
        record.goals_scored_diff = float(f[4])
        record.goals_conceded_diff = float(f[5])
        record.form_diff = float(f[6])
        record.avg_age_diff = float(f[7])
        record.market_value_diff = float(f[8])
        record.injury_burden_diff = float(f[9])
        record.coach_impact_diff = float(f[10])
        record.squad_chemistry_diff = float(f[11])
        record.travel_distance_km = float(f[12])
        record.rest_days = float(f[13])
        record.tournament_exp_diff = float(f[14])
        record.starting_xi_strength_diff = float(f[15])
        record.bench_strength_diff = float(f[16])
        record.feature_version = FEATURE_VERSION

        db.commit()
    finally:
        db.close()
