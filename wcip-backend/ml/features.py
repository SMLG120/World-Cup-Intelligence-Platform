"""Feature engineering pipeline.

Builds a feature vector for any (home_team, away_team, date) triplet.
Features are expressed as (home - away) differentials so a positive value
always favours the home team.

Feature list (v2):
  0  elo_diff
  1  fifa_rank_diff          (positive = home team has better rank, inverted)
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
 17  average_starting_xi_rating_diff
 18  average_squad_rating_diff
 19  top_5_player_rating_avg_diff
 20  goalkeeper_rating_diff
 21  defensive_unit_rating_diff
 22  midfield_unit_rating_diff
 23  attacking_unit_rating_diff
 24  squad_depth_score_diff
 25  star_player_score_diff
 26  injury_burden_score_diff
 27  player_form_score_diff
 28  player_availability_score_diff
 29  international_experience_score_diff
 30  average_caps_diff
 31  total_international_goals_diff
 32  weighted_player_strength_diff
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, NamedTuple, Optional

import numpy as np

logger = logging.getLogger(__name__)

FEATURE_VERSION = "v2"
BASE_FEATURE_COUNT = 17
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

N_FEATURES = len(FEATURE_NAMES)
_WARNED_PLAYER_DATA: set[str] = set()


class FeatureVector(NamedTuple):
    home_team: str
    away_team: str
    match_date: date
    features: np.ndarray     # shape (N_FEATURES,)
    version: str = FEATURE_VERSION


# ---------------------------------------------------------------------------
# Team stat caches (populated from DB)
# ---------------------------------------------------------------------------

def _asof_datetime(as_of_date: date | None) -> datetime | None:
    if as_of_date is None:
        return None
    return datetime.combine(as_of_date, time.max).replace(tzinfo=timezone.utc)


def _is_historical(as_of_date: date | None) -> bool:
    return as_of_date is not None and as_of_date < date.today()


def _get_team_elo(team_name: str, as_of_date: date | None = None) -> float:
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.team import EloHistory, EloRatingSnapshot, Team, TeamEloRating
        from etl.transform.normalize import canonical
        canonical_name = canonical(team_name)
        db = SessionLocal()
        try:
            snapshot_query = select(EloRatingSnapshot)
            if as_of_date is not None:
                snapshot_query = snapshot_query.where(EloRatingSnapshot.rating_date <= as_of_date)
            else:
                snapshot_query = snapshot_query.where(EloRatingSnapshot.is_current.is_(True))
            snapshot = db.scalar(
                snapshot_query
                .order_by(EloRatingSnapshot.rating_date.desc(), EloRatingSnapshot.id.desc())
                .limit(1)
            )
            if snapshot:
                rating = db.scalar(
                    select(TeamEloRating)
                    .where(
                        TeamEloRating.snapshot_id == snapshot.id,
                        TeamEloRating.team_name == canonical_name,
                    )
                    .limit(1)
                )
                if rating:
                    return rating.rating

            asof = _asof_datetime(as_of_date)
            if asof is not None:
                historical = db.scalar(
                    select(EloHistory)
                    .join(Team, EloHistory.team_id == Team.id)
                    .where(Team.name == canonical_name, EloHistory.recorded_at <= asof)
                    .order_by(EloHistory.recorded_at.desc(), EloHistory.id.desc())
                    .limit(1)
                )
                if historical:
                    return historical.rating
                if _is_historical(as_of_date):
                    return 1500.0

            t = db.scalar(select(Team).where(Team.name == canonical_name))
            return t.elo if t else 1500.0
        finally:
            db.close()
    except Exception:
        return 1500.0


def _get_latest_elo_snapshot_meta(as_of_date: date | None = None) -> dict:
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.team import EloRatingSnapshot

        db = SessionLocal()
        try:
            query = select(EloRatingSnapshot)
            if as_of_date is not None:
                query = query.where(EloRatingSnapshot.rating_date <= as_of_date)
            else:
                query = query.where(EloRatingSnapshot.is_current.is_(True))
            snapshot = db.scalar(
                query.order_by(EloRatingSnapshot.rating_date.desc(), EloRatingSnapshot.id.desc()).limit(1)
            )
            if not snapshot:
                return {}
            return {
                "snapshot_id": snapshot.snapshot_id,
                "data_version": snapshot.data_version,
                "rating_date": snapshot.rating_date.isoformat(),
                "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
                "source_url": snapshot.source_url,
            }
        finally:
            db.close()
    except Exception:
        return {}


def _get_team_elo_metadata(team_name: str, as_of_date: date | None = None) -> dict:
    try:
        import json

        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.team import EloRatingSnapshot, Team, TeamEloRating
        from etl.transform.normalize import canonical

        canonical_name = canonical(team_name)
        db = SessionLocal()
        try:
            query = select(EloRatingSnapshot)
            if as_of_date is not None:
                query = query.where(EloRatingSnapshot.rating_date <= as_of_date)
            else:
                query = query.where(EloRatingSnapshot.is_current.is_(True))
            snapshot = db.scalar(
                query.order_by(EloRatingSnapshot.rating_date.desc(), EloRatingSnapshot.id.desc()).limit(1)
            )
            if snapshot:
                rating = db.scalar(
                    select(TeamEloRating)
                    .where(
                        TeamEloRating.snapshot_id == snapshot.id,
                        TeamEloRating.team_name == canonical_name,
                    )
                    .limit(1)
                )
                if rating:
                    raw_payload = {}
                    if rating.raw_payload:
                        try:
                            raw_payload = json.loads(rating.raw_payload)
                        except Exception:
                            raw_payload = {}
                    return {
                        "elo_rating_used": rating.rating,
                        "elo_rank_used": rating.rank,
                        "elo_source": raw_payload.get("source_name") or "World Football Elo",
                        "elo_source_date": snapshot.rating_date.isoformat(),
                        "elo_snapshot_version": snapshot.data_version,
                        "elo_source_url": snapshot.source_url,
                    }

            team = db.scalar(select(Team).where(Team.name == canonical_name))
            if team:
                return {
                    "elo_rating_used": team.elo,
                    "elo_rank_used": None,
                    "elo_source": "teams.elo fallback",
                    "elo_source_date": None,
                    "elo_snapshot_version": None,
                    "elo_source_url": None,
                }
            return {}
        finally:
            db.close()
    except Exception:
        return {}


def _get_latest_fifa_snapshot_meta(as_of_date: date | None = None) -> dict:
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.ranking import FifaRankingSnapshot

        db = SessionLocal()
        try:
            query = select(FifaRankingSnapshot)
            if as_of_date is not None:
                query = query.where(FifaRankingSnapshot.ranking_date <= as_of_date)
            else:
                query = query.where(FifaRankingSnapshot.is_current.is_(True))
            snapshot = db.scalar(
                query.order_by(FifaRankingSnapshot.ranking_date.desc(), FifaRankingSnapshot.id.desc()).limit(1)
            )
            if not snapshot:
                return {}
            return {
                "ranking_id": snapshot.ranking_id,
                "data_version": snapshot.ranking_id,
                "ranking_date": snapshot.ranking_date.isoformat(),
                "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
                "source_url": snapshot.source_url,
            }
        finally:
            db.close()
    except Exception:
        return {}


def _get_player_data_freshness(team_names: list[str]) -> str | None:
    try:
        from sqlalchemy import func, select
        from app.db.base import SessionLocal
        from app.models.player import Player

        db = SessionLocal()
        try:
            latest = db.scalar(
                select(func.max(Player.updated_at)).where(
                    Player.team_name.in_(team_names),
                    Player.is_active.is_(True),
                )
            )
            return latest.isoformat() if latest else None
        finally:
            db.close()
    except Exception:
        return None


def build_feature_metadata(
    home_team: str,
    away_team: str,
    match_date: date | None = None,
) -> dict:
    if match_date is None:
        match_date = date.today()
    elo_meta = _get_latest_elo_snapshot_meta(match_date)
    fifa_meta = _get_latest_fifa_snapshot_meta(match_date)
    return {
        "home_elo_rating_used": _get_team_elo(home_team, match_date),
        "away_elo_rating_used": _get_team_elo(away_team, match_date),
        "home_fifa_ranking_used": _get_team_fifa_rank(home_team, match_date),
        "away_fifa_ranking_used": _get_team_fifa_rank(away_team, match_date),
        "elo_snapshot": elo_meta,
        "fifa_snapshot": fifa_meta,
        "player_data_freshness": _get_player_data_freshness([home_team, away_team]),
        "feature_version": FEATURE_VERSION,
        "data_snapshot_version": "|".join(
            part for part in [
                f"elo:{elo_meta.get('data_version')}" if elo_meta else None,
                f"fifa:{fifa_meta.get('data_version')}" if fifa_meta else None,
                f"feature:{FEATURE_VERSION}",
            ]
            if part
        ),
    }


def _get_team_fifa_rank(team_name: str, as_of_date: date | None = None) -> int:
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.ranking import FifaRankingEntry, FifaRankingSnapshot
        from app.models.team import Team
        from etl.transform.normalize import canonical
        canonical_name = canonical(team_name)
        db = SessionLocal()
        try:
            snapshot = db.scalar(
                select(FifaRankingSnapshot)
                .where(
                    FifaRankingSnapshot.ranking_date <= (as_of_date or date.today()),
                )
                .order_by(FifaRankingSnapshot.ranking_date.desc(), FifaRankingSnapshot.id.desc())
                .limit(1)
            )
            if snapshot:
                entry = db.scalar(
                    select(FifaRankingEntry)
                    .where(
                        FifaRankingEntry.snapshot_id == snapshot.id,
                        FifaRankingEntry.team_name == canonical_name,
                    )
                    .limit(1)
                )
                if entry:
                    return entry.rank
            if _is_historical(as_of_date):
                return 100

            t = db.scalar(select(Team).where(Team.name == canonical_name))
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
                select(Player).where(
                    Player.team_name == team_name,
                    Player.is_active.is_(True),
                )
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


def _warn_once(key: str, message: str) -> None:
    if key in _WARNED_PLAYER_DATA:
        return
    _WARNED_PLAYER_DATA.add(key)
    logger.warning(message)


def _player_rating(player) -> float | None:
    rating = getattr(player, "player_rating", None)
    if rating is None:
        rating = getattr(player, "ea_fc_rating", None)
    if rating is None:
        return None
    return float(min(100.0, max(0.0, rating)))


def _position_group(position: str | None) -> str:
    text = (position or "").upper()
    if text in {"GK", "GOALKEEPER"}:
        return "GK"
    if text in {"DEF", "DF", "CB", "LB", "RB", "LWB", "RWB", "DEFENDER"}:
        return "DEF"
    if text in {"MID", "MF", "DM", "CM", "AM", "CDM", "CAM", "MIDFIELDER"}:
        return "MID"
    if text in {"FWD", "FW", "ST", "CF", "LW", "RW", "FORWARD", "ATTACKER"}:
        return "FWD"
    return "UNK"


def _mean_or(values: list[float], default: float) -> float:
    return float(np.mean(values)) if values else default


def _get_player_strength_stats(team_name: str) -> Dict[str, float]:
    """Aggregate player rows into team-level strength features.

    Missing ratings or sparse squads use neutral values so predictions never
    crash because a licensed source file has not been imported yet.
    """
    neutral = {
        "average_starting_xi_rating": 70.0,
        "average_squad_rating": 70.0,
        "top_5_player_rating_avg": 70.0,
        "goalkeeper_rating": 70.0,
        "defensive_unit_rating": 70.0,
        "midfield_unit_rating": 70.0,
        "attacking_unit_rating": 70.0,
        "squad_depth_score": 0.70,
        "star_player_score": 0.70,
        "injury_burden_score": 1.0,
        "player_form_score": 0.50,
        "player_availability_score": 1.0,
        "international_experience_score": 0.0,
        "average_caps": 0.0,
        "total_international_goals": 0.0,
        "weighted_player_strength": 70.0,
    }
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.player import Player
        db = SessionLocal()
        try:
            rows = db.scalars(
                select(Player).where(
                    Player.team_name == team_name,
                    Player.is_active.is_(True),
                )
            ).all()
        finally:
            db.close()
    except Exception as exc:
        _warn_once(f"{team_name}:player-query", f"Player strength query failed for {team_name}: {exc}")
        return neutral

    if not rows:
        _warn_once(f"{team_name}:no-players", f"No player rows for {team_name}; using neutral player-strength defaults")
        return neutral

    rated = [(p, _player_rating(p)) for p in rows]
    rated_values = [rating for _, rating in rated if rating is not None]
    if not rated_values:
        _warn_once(f"{team_name}:no-ratings", f"No player ratings for {team_name}; using neutral rating defaults")

    def ratings_for(group: str) -> list[float]:
        values = [
            rating for player, rating in rated
            if rating is not None and _position_group(player.position) == group
        ]
        return values

    sorted_ratings = sorted(rated_values, reverse=True)
    average_squad = _mean_or(rated_values, 70.0)
    starting_xi = _mean_or(sorted_ratings[:11], average_squad)
    top_5 = _mean_or(sorted_ratings[:5], average_squad)
    goalkeeper = max(ratings_for("GK") or [average_squad])
    defence = _mean_or(ratings_for("DEF"), average_squad)
    midfield = _mean_or(ratings_for("MID"), average_squad)
    attack = _mean_or(ratings_for("FWD"), average_squad)

    available_rows = [p for p in rows if not p.injured and not p.suspended]
    availability = len(available_rows) / max(len(rows), 1)
    injury_burden_score = availability
    form_scores = [
        min(1.0, max(0.0, float(p.recent_form_score if p.recent_form_score is not None else 0.5)))
        for p in rows
    ]
    player_form_score = _mean_or(form_scores, 0.5)
    caps = [float(p.international_caps or 0) for p in rows]
    goals = [float(p.international_goals or 0) for p in rows]
    average_caps = _mean_or(caps, 0.0)
    total_goals = float(sum(goals))
    total_caps = float(sum(caps))
    international_experience_score = min(1.0, math.log1p(total_caps) / math.log1p(1500.0))

    weighted_values = []
    for player, rating in rated:
        base = rating if rating is not None else 70.0
        available = 0.0 if player.injured or player.suspended else 1.0
        form = min(1.0, max(0.0, float(player.recent_form_score or 0.5)))
        caps_boost = min(1.10, 1.0 + math.log1p(player.international_caps or 0) / 100.0)
        weighted_values.append(base * available * (0.75 + 0.25 * form) * caps_boost)

    depth_pool = sorted_ratings[11:23] if len(sorted_ratings) > 11 else sorted_ratings
    squad_depth_score = min(1.0, (len(rows) / 23.0) * (_mean_or(depth_pool, average_squad) / 100.0))
    star_player_score = max(sorted_ratings or [70.0]) / 100.0

    return {
        "average_starting_xi_rating": starting_xi,
        "average_squad_rating": average_squad,
        "top_5_player_rating_avg": top_5,
        "goalkeeper_rating": goalkeeper,
        "defensive_unit_rating": defence,
        "midfield_unit_rating": midfield,
        "attacking_unit_rating": attack,
        "squad_depth_score": squad_depth_score,
        "star_player_score": star_player_score,
        "injury_burden_score": injury_burden_score,
        "player_form_score": player_form_score,
        "player_availability_score": availability,
        "international_experience_score": international_experience_score,
        "average_caps": average_caps,
        "total_international_goals": total_goals,
        "weighted_player_strength": _mean_or(weighted_values, 70.0),
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
    h_elo = ho["elo"] if "elo" in ho else _get_team_elo(home_team, match_date)
    a_elo = ao["elo"] if "elo" in ao else _get_team_elo(away_team, match_date)
    elo_diff = h_elo - a_elo

    # FIFA rank (lower = better, so invert)
    h_rank = ho["fifa_rank"] if "fifa_rank" in ho else _get_team_fifa_rank(home_team, match_date)
    a_rank = ao["fifa_rank"] if "fifa_rank" in ao else _get_team_fifa_rank(away_team, match_date)
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

    h_player = _get_player_strength_stats(home_team)
    a_player = _get_player_strength_stats(away_team)
    player_feature_names = [
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
    player_diffs = [
        float(h_player[name] - a_player[name])
        for name in player_feature_names
    ]

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
        *player_diffs,
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
    Uses point-in-time FIFA ranking snapshots and Elo history when available.
    If no historical snapshot exists for a match date, neutral defaults are
    used instead of leaking today's team rank into old training rows.
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
        if len(f) > BASE_FEATURE_COUNT:
            record.average_starting_xi_rating_diff = float(f[17])
            record.average_squad_rating_diff = float(f[18])
            record.top_5_player_rating_avg_diff = float(f[19])
            record.goalkeeper_rating_diff = float(f[20])
            record.defensive_unit_rating_diff = float(f[21])
            record.midfield_unit_rating_diff = float(f[22])
            record.attacking_unit_rating_diff = float(f[23])
            record.squad_depth_score_diff = float(f[24])
            record.star_player_score_diff = float(f[25])
            record.injury_burden_score_diff = float(f[26])
            record.player_form_score_diff = float(f[27])
            record.player_availability_score_diff = float(f[28])
            record.international_experience_score_diff = float(f[29])
            record.average_caps_diff = float(f[30])
            record.total_international_goals_diff = float(f[31])
            record.weighted_player_strength_diff = float(f[32])
        record.feature_version = FEATURE_VERSION

        db.commit()
    finally:
        db.close()
