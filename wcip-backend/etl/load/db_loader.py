"""Load layer: persist validated records to the database.

All loaders are idempotent (upsert semantics) and support incremental runs.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.match_result import MatchResult, QualifiedTeam
from app.models.player import Coach, Player
from etl.validation.schema import ValidatedMatch

logger = logging.getLogger(__name__)


def load_match_results(records: Iterator[ValidatedMatch], batch_size: int = 500) -> int:
    """Upsert match results. Returns total rows inserted."""
    db: Session = SessionLocal()
    inserted = 0
    batch: list[MatchResult] = []
    seen: set[tuple] = set()  # deduplicate within this run (CSV may have duplicate rows)
    try:
        for rec in records:
            key = (rec.home_team, rec.away_team, rec.match_date)
            if key in seen:
                continue
            seen.add(key)
            exists = db.scalar(
                select(MatchResult.id).where(
                    MatchResult.home_team == rec.home_team,
                    MatchResult.away_team == rec.away_team,
                    MatchResult.match_date == rec.match_date,
                )
            )
            if exists:
                continue
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
                db.add_all(batch)
                db.commit()
                inserted += len(batch)
                logger.info("Loaded %d match results (running total: %d)", len(batch), inserted)
                batch.clear()

        if batch:
            db.add_all(batch)
            db.commit()
            inserted += len(batch)
    finally:
        db.close()
    logger.info("Total match results loaded: %d", inserted)
    return inserted


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
