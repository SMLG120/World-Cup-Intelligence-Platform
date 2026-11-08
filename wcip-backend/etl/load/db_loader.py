"""Load layer: persist validated records to the database.

All loaders are idempotent (upsert semantics) and support incremental runs.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.match_result import MatchResult, QualifiedTeam
from app.models.player import Coach, Player
from etl.players.profiles import build_player_profile
from etl.validation.schema import ValidatedMatch

logger = logging.getLogger(__name__)


class SuspiciousBackfillError(RuntimeError):
    """A sync tried to insert many old matches into an already-full table."""


# Once full history is stored, legitimate syncs add recent matches; a burst of
# year-old "new" rows almost always means the upstream source renamed a team,
# and inserting them would duplicate history under the new name.
BACKFILL_GUARD_MIN_EXISTING = 40_000
BACKFILL_GUARD_MAX_OLD_INSERTS = 50


def load_match_results(
    records: Iterator[ValidatedMatch],
    batch_size: int = 500,
    *,
    guard_backfill: bool = False,
) -> int:
    """Upsert match results. Returns total rows inserted.

    Existing ``(home_team, away_team, match_date)`` keys are preloaded in one
    query for the incoming date range instead of one SELECT per CSV row; on a
    remote Postgres a full 49k-row load previously cost 49k round trips.
    """
    db: Session = SessionLocal()
    inserted = 0
    batch: list[MatchResult] = []
    records = list(records)
    if not records:
        db.close()
        logger.info("Total match results loaded: 0")
        return 0
    min_date = min(rec.match_date for rec in records)
    seen: set[tuple] = {
        (home, away, match_date)
        for home, away, match_date in db.execute(
            select(MatchResult.home_team, MatchResult.away_team, MatchResult.match_date)
            .where(MatchResult.match_date >= min_date)
        )
    }
    if guard_backfill and len(seen) >= BACKFILL_GUARD_MIN_EXISTING:
        cutoff = date.today() - timedelta(days=365)
        old_new = {
            (rec.home_team, rec.away_team, rec.match_date)
            for rec in records
            if rec.match_date < cutoff and (rec.home_team, rec.away_team, rec.match_date) not in seen
        }
        if len(old_new) > BACKFILL_GUARD_MAX_OLD_INSERTS:
            db.close()
            known = {team for key in seen for team in key[:2]}
            unknown = sorted({team for key in old_new for team in key[:2]} - known)
            raise SuspiciousBackfillError(
                f"Refusing to insert {len(old_new)} matches older than {cutoff} into a table "
                f"with {len(seen)} rows; the source probably renamed teams. Team names not "
                f"in the database: {unknown[:10]}. Map them in etl/transform/normalize.py NAME_MAP."
            )
    try:
        for rec in records:
            key = (rec.home_team, rec.away_team, rec.match_date)
            if key in seen:  # already stored, or duplicate row within this CSV
                continue
            seen.add(key)
            batch.append(MatchResult(
                match_date=rec.match_date,
                home_team=rec.home_team,
                away_team=rec.away_team,
                home_goals=rec.home_goals,
                away_goals=rec.away_goals,
                tournament=rec.tournament,
                city=rec.city,
                country=rec.country,
                neutral=rec.neutral,
                outcome=rec.outcome,
                data_source="international_results",
            ))
            if len(batch) >= batch_size:
                inserted += _commit_match_batch(db, batch)
                logger.info("Loaded %d match results (running total: %d)", len(batch), inserted)
                batch.clear()

        if batch:
            inserted += _commit_match_batch(db, batch)
    finally:
        db.close()
    logger.info("Total match results loaded: %d", inserted)
    return inserted


def _commit_match_batch(db: Session, batch: list[MatchResult]) -> int:
    db.add_all(batch)
    db.commit()
    for row in batch:
        if _should_update_live_ratings(row):
            try:
                from app.services.rating_update_service import update_ratings_after_match

                update_ratings_after_match(row.id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Live Elo update failed for match %s: %s", row.id, exc)
    return len(batch)


def _should_update_live_ratings(row: MatchResult) -> bool:
    tournament = (row.tournament or "").lower()
    return row.match_date.year == 2026 and "world cup" in tournament


def load_players(records: list[dict], team_name: str, data_source: str = "football-data") -> int:
    """Upsert player records for a team. Returns rows inserted/updated."""
    db: Session = SessionLocal()
    upserted = 0
    try:
        for raw in records:
            ext_id = str(raw.get("external_id") or raw.get("id") or "")
            existing = None
            if ext_id:
                existing = db.scalar(
                    select(Player).where(
                        Player.external_id == ext_id,
                        Player.data_source == data_source,
                    )
                )
            if not existing:
                existing = db.scalar(
                    select(Player).where(
                        Player.name == raw.get("name", ""),
                        Player.team_name == team_name,
                    )
                )

            if existing:
                _update_player(existing, raw, team_name, data_source)
            else:
                player = Player(
                    name=raw.get("name", ""),
                    team_name=team_name,
                    position=raw.get("position", ""),
                    club=raw.get("club"),
                    age=raw.get("age"),
                    nationality=raw.get("nationality"),
                    external_id=ext_id or None,
                    data_source=data_source,
                )
                _update_player(player, raw, team_name, data_source)
                db.add(player)
            upserted += 1

        db.commit()
    finally:
        db.close()
    return upserted


def _update_player(player: Player, raw: dict, team_name: str, data_source: str) -> None:
    player.team_name = team_name
    player.data_source = data_source
    player.is_active = True
    for field in ("position", "club", "age", "nationality", "goals", "assists",
                  "xg", "xag", "minutes_played", "key_passes", "progressive_passes",
                  "progressive_carries", "tackles", "interceptions", "yellow_cards",
                  "red_cards", "international_caps", "international_goals",
                  "market_value_eur", "fitness_score"):
        if field in raw:
            setattr(player, field, raw[field])
    if "injured" in raw:
        player.injured = bool(raw["injured"])
    if "suspended" in raw:
        player.suspended = bool(raw["suspended"])
    player.profile_description = build_player_profile(player)


def load_qualified_teams(teams: list[dict], tournament_year: int = 2026) -> int:
    """Upsert qualified teams. Returns rows inserted."""
    db: Session = SessionLocal()
    inserted = 0
    try:
        for t in teams:
            name = t.get("team_name", "").strip()
            if not name:
                continue
            existing = db.scalar(
                select(QualifiedTeam).where(
                    QualifiedTeam.team_name == name,
                    QualifiedTeam.tournament_year == tournament_year,
                )
            )
            if existing:
                for field in ("group_label", "pot", "confederation", "host_nation",
                              "confirmed", "qualification_path", "team_code"):
                    if field in t:
                        setattr(existing, field, t[field])
            else:
                db.add(QualifiedTeam(
                    team_name=name,
                    team_code=t.get("team_code", ""),
                    confederation=t.get("confederation", ""),
                    tournament_year=tournament_year,
                    group_label=t.get("group_label"),
                    pot=t.get("pot"),
                    host_nation=t.get("host_nation", False),
                    confirmed=t.get("confirmed", True),
                    qualification_path=t.get("qualification_path"),
                ))
                inserted += 1
        db.commit()
    finally:
        db.close()
    return inserted
