"""Idempotent Elo updates after match results change."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.db.base import SessionLocal
from app.models.match_result import MatchFeatures, MatchResult
from app.models.team import EloHistory, EloRatingSnapshot, Team, TeamEloRating
from etl.transform.normalize import canonical
from ml.features import build_feature_vector
from wcip.engine.elo import EloEngine


@dataclass
class RatingUpdateResult:
    match_id: int
    status: str
    snapshot_id: str | None = None
    data_version: str | None = None
    home_team: str | None = None
    away_team: str | None = None
    home_elo_after: float | None = None
    away_elo_after: float | None = None
    features_refreshed: int = 0
    cache_keys_invalidated: int = 0
    messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_id": self.match_id,
            "status": self.status,
            "snapshot_id": self.snapshot_id,
            "data_version": self.data_version,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "home_elo_after": self.home_elo_after,
            "away_elo_after": self.away_elo_after,
            "features_refreshed": self.features_refreshed,
            "cache_keys_invalidated": self.cache_keys_invalidated,
            "messages": self.messages,
        }


def update_ratings_after_match(match_id: int) -> RatingUpdateResult:
    """Update Elo history and current display ratings for one match result."""

    db = SessionLocal()
    try:
        return _update_ratings_after_match(db, match_id)
    finally:
        db.close()


def _update_ratings_after_match(db: Session, match_id: int) -> RatingUpdateResult:
    match = db.get(MatchResult, match_id)
    if match is None:
        return RatingUpdateResult(match_id=match_id, status="not_found", messages=["Match result not found"])

    if match.home_goals is None or match.away_goals is None:
        return RatingUpdateResult(match_id=match_id, status="skipped", messages=["Match has no final score"])

    home_name = canonical(match.home_team)
    away_name = canonical(match.away_team)
    result_hash = _match_hash(match)
    snapshot_id = f"match-{match.id}-{result_hash[:12]}"

    existing = db.scalar(
        select(EloRatingSnapshot).where(EloRatingSnapshot.snapshot_id == snapshot_id)
    )
    if existing:
        return RatingUpdateResult(
            match_id=match_id,
            status="already_processed",
            snapshot_id=snapshot_id,
            data_version=existing.data_version,
            home_team=home_name,
            away_team=away_name,
            messages=["Same match result was already processed"],
        )

    home_team = _team_by_name(db, home_name)
    away_team = _team_by_name(db, away_name)
    if home_team is None or away_team is None:
        return RatingUpdateResult(
            match_id=match_id,
            status="missing_team_mapping",
            home_team=home_name,
            away_team=away_name,
            messages=["Home or away team is missing from teams table"],
        )

    home_before = _latest_elo_before(db, home_team, match.match_date)
    away_before = _latest_elo_before(db, away_team, match.match_date)
    engine = EloEngine({home_name: home_before, away_name: away_before})
    importance = _importance(match.tournament)
    home_after, away_after = engine.update_match(
        home_name,
        away_name,
        int(match.home_goals),
        int(match.away_goals),
        importance=importance,
        neutral=bool(match.neutral),
    )

    snapshot = EloRatingSnapshot(
        snapshot_id=snapshot_id,
        rating_date=match.match_date,
        source_url=f"match_result:{match.id}",
        source_hash=result_hash,
        team_count=2,
        is_current=False,
        data_version=snapshot_id,
    )
    db.add(snapshot)
    db.flush()

    for rank, team, rating, opponent in (
        (None, home_team, home_after, away_name),
        (None, away_team, away_after, home_name),
    ):
        db.add(
            TeamEloRating(
                snapshot_id=snapshot.id,
                team_id=team.id,
                team_name=team.name,
                team_code=team.code,
                rank=rank,
                rating=rating,
                rating_date=match.match_date,
                source_url=snapshot.source_url,
                data_version=snapshot.data_version,
                raw_payload=None,
            )
        )
        db.add(
            EloHistory(
                team_id=team.id,
                rating=rating,
                opponent=opponent,
                recorded_at=datetime.combine(match.match_date, time.max).replace(tzinfo=timezone.utc),
            )
        )

    latest_current = db.scalar(
        select(EloRatingSnapshot)
        .where(EloRatingSnapshot.is_current.is_(True))
        .order_by(EloRatingSnapshot.rating_date.desc(), EloRatingSnapshot.id.desc())
        .limit(1)
    )
    if latest_current is None or match.match_date >= latest_current.rating_date:
        db.query(EloRatingSnapshot).update({EloRatingSnapshot.is_current: False})
        snapshot.is_current = True
        home_team.elo = home_after
        away_team.elo = away_after

    refreshed = _refresh_match_features(db, match, home_after=home_after, away_after=away_after)
    db.commit()
    invalidated = cache.invalidate_prefix("match:", "teams:", "wc2026", "prediction:")

    return RatingUpdateResult(
        match_id=match_id,
        status="updated",
        snapshot_id=snapshot_id,
        data_version=snapshot_id,
        home_team=home_name,
        away_team=away_name,
        home_elo_after=round(home_after, 3),
        away_elo_after=round(away_after, 3),
        features_refreshed=refreshed,
        cache_keys_invalidated=invalidated,
        messages=["Group standings update hook not configured for stored fixtures"],
    )


def _refresh_match_features(
    db: Session,
    match: MatchResult,
    *,
    home_after: float,
    away_after: float,
) -> int:
    fv = build_feature_vector(
        match.home_team,
        match.away_team,
        match.match_date,
        home_overrides={"elo": home_after},
        away_overrides={"elo": away_after},
    )
    existing = db.scalar(
        select(MatchFeatures).where(
            MatchFeatures.home_team == match.home_team,
            MatchFeatures.away_team == match.away_team,
            MatchFeatures.match_date == match.match_date,
        )
    )
    if not existing:
        existing = MatchFeatures(
            match_result_id=match.id,
            home_team=match.home_team,
            away_team=match.away_team,
            match_date=match.match_date,
        )
        db.add(existing)
    values = list(map(float, fv.features))
    for column, value in zip(_feature_columns(), values):
        setattr(existing, column, value)
    existing.feature_version = fv.version
    return 1


def _feature_columns() -> list[str]:
    from ml.features import FEATURE_NAMES

    return FEATURE_NAMES


def _team_by_name(db: Session, name: str) -> Team | None:
    return db.scalar(select(Team).where(Team.name == name))


def _latest_elo_before(db: Session, team: Team, match_date) -> float:
    asof = datetime.combine(match_date, time.max).replace(tzinfo=timezone.utc)
    row = db.scalar(
        select(EloHistory)
        .where(EloHistory.team_id == team.id, EloHistory.recorded_at <= asof)
        .order_by(EloHistory.recorded_at.desc(), EloHistory.id.desc())
        .limit(1)
    )
    return float(row.rating if row else team.elo or 1500.0)


def _importance(tournament: str | None) -> str:
    text = (tournament or "").lower()
    if "world cup" in text and "final" in text:
        return "world_cup_final"
    if "world cup" in text and any(term in text for term in ("knockout", "semi", "quarter", "round")):
        return "world_cup_knockout"
    if "world cup" in text:
        return "world_cup_group"
    if "qual" in text:
        return "qualifier"
    if any(term in text for term in ("euro", "copa", "afcon", "asian cup", "gold cup")):
        return "continental"
    return "friendly"


def _match_hash(match: MatchResult) -> str:
    payload = "|".join(
        [
            str(match.id),
            str(match.match_date),
            canonical(match.home_team),
            canonical(match.away_team),
            str(match.home_goals),
            str(match.away_goals),
            str(match.tournament or ""),
            str(match.neutral),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
