"""Legal CSV import for player ratings and form data.

This importer intentionally avoids scraping. Use it with licensed/public data
or a manually maintained file such as `data/external/ea_player_ratings.csv`.
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.cache import cache
from app.db.base import SessionLocal
from app.models.player import Player, PlayerRatingImport, PlayerRatingRecord
from etl.players.profiles import build_player_profile
from etl.transform.normalize import canonical

logger = logging.getLogger(__name__)

DEFAULT_RATING_FILE = Path(__file__).parents[2] / "data" / "external" / "ea_player_ratings.csv"
PLACEHOLDER_SOURCE = "world_cup_2026_placeholder"


@dataclass(frozen=True)
class PlayerRatingRow:
    player_name: str
    team_name: str
    position: str
    club: str | None
    age: int | None
    international_caps: int
    international_goals: int
    recent_form_score: float
    injured: bool
    suspended: bool
    minutes_played: float
    goals: float
    assists: float
    xg: float
    xag: float
    market_value_eur: float | None
    player_rating: float | None
    ea_fc_rating: float | None
    raw: dict[str, Any]


def import_player_ratings_csv(
    source_path: str | Path = DEFAULT_RATING_FILE,
    *,
    source_name: str = "manual_csv",
    source_version: str | None = None,
    source_url: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Import player ratings from a CSV file with validation and history."""

    path = Path(source_path)
    version = source_version or path.stem
    imported_at = datetime.now(timezone.utc)

    db = SessionLocal()
    batch = PlayerRatingImport(
        source_name=source_name,
        source_url=source_url,
        source_file=str(path),
        source_version=version,
        status="started",
        imported_at=imported_at,
        notes=notes,
    )
    db.add(batch)
    db.commit()

    row_count = 0
    valid_rows = 0
    skipped_rows = 0
    touched_teams: set[str] = set()

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                row_count += 1
                try:
                    parsed = _parse_row(raw)
                except ValueError as exc:
                    skipped_rows += 1
                    logger.warning("Skipping player rating row %s: %s", row_count, exc)
                    continue

                player = _upsert_player(db, parsed, source_name, version, imported_at)
                db.flush()
                db.add(
                    PlayerRatingRecord(
                        import_id=batch.id,
                        player_id=player.id,
                        player_name=parsed.player_name,
                        team_name=parsed.team_name,
                        position=parsed.position,
                        club=parsed.club,
                        rating=parsed.player_rating,
                        ea_fc_rating=parsed.ea_fc_rating,
                        recent_form_score=parsed.recent_form_score,
                        source_row_hash=_row_hash(raw),
                        raw_payload=json.dumps(raw, ensure_ascii=False, sort_keys=True),
                    )
                )
                valid_rows += 1
                touched_teams.add(parsed.team_name)

        if touched_teams:
            for placeholder in db.scalars(
                select(Player).where(
                    Player.team_name.in_(touched_teams),
                    Player.data_source == PLACEHOLDER_SOURCE,
                )
            ).all():
                placeholder.is_active = False

        batch.status = "success"
        batch.row_count = row_count
        batch.valid_rows = valid_rows
        batch.skipped_rows = skipped_rows
        db.commit()
    except Exception as exc:
        db.rollback()
        batch.status = "failed"
        batch.row_count = row_count
        batch.valid_rows = valid_rows
        batch.skipped_rows = skipped_rows
        batch.error_message = str(exc)
        db.add(batch)
        db.commit()
        raise
    finally:
        db.close()

    result = {
        "source_file": str(path),
        "source_name": source_name,
        "source_version": version,
        "row_count": row_count,
        "valid_rows": valid_rows,
        "skipped_rows": skipped_rows,
        "teams_updated": len(touched_teams),
        "status": batch.status,
    }
    cache.invalidate_prefix("teams:")
    logger.info("Player rating import complete: %s", result)
    return result


def _parse_row(raw: dict[str, Any]) -> PlayerRatingRow:
    name = _text(raw, "player_name", "name")
    team = _text(raw, "team_name", "team", "national_team", "country")
    if not name:
        raise ValueError("missing player name")
    if not team:
        raise ValueError("missing team name")

    rating = _optional_float(raw, "player_rating", "rating", "overall_rating")
    ea_rating = _optional_float(raw, "ea_fc_rating", "ea_rating", "fc_rating")
    if rating is None and ea_rating is not None:
        rating = ea_rating
    if rating is not None and not 0 <= rating <= 100:
        raise ValueError(f"rating outside 0..100: {rating}")
    if ea_rating is not None and not 0 <= ea_rating <= 100:
        raise ValueError(f"ea_fc_rating outside 0..100: {ea_rating}")

    form = _optional_float(raw, "recent_form_score", "form", "player_form")
    if form is None:
        form = 0.5
    form = min(1.0, max(0.0, form if form <= 1 else form / 100))

    return PlayerRatingRow(
        player_name=name,
        team_name=canonical(team),
        position=_normalize_position(_text(raw, "position", default="UNK")),
        club=_text(raw, "club") or None,
        age=_optional_int(raw, "age"),
        international_caps=_optional_int(raw, "international_caps", "caps") or 0,
        international_goals=_optional_int(raw, "international_goals", "intl_goals") or 0,
        recent_form_score=form,
        injured=_optional_bool(raw, "injured", "is_injured") or False,
        suspended=_optional_bool(raw, "suspended", "is_suspended") or False,
        minutes_played=_optional_float(raw, "minutes_played", "minutes") or 0.0,
        goals=_optional_float(raw, "goals") or 0.0,
        assists=_optional_float(raw, "assists") or 0.0,
        xg=_optional_float(raw, "xg") or 0.0,
        xag=_optional_float(raw, "xag", "xa") or 0.0,
        market_value_eur=_optional_float(raw, "market_value_eur", "market_value"),
        player_rating=rating,
        ea_fc_rating=ea_rating,
        raw=raw,
    )


def _upsert_player(
    db,
    row: PlayerRatingRow,
    source_name: str,
    source_version: str,
    imported_at: datetime,
) -> Player:
    external_id = _stable_player_external_id(row)
    player = None
    if external_id:
        player = db.scalar(select(Player).where(Player.external_id == external_id))
    if player is None:
        player = db.scalar(
            select(Player).where(
                Player.team_name == row.team_name,
                Player.name == row.player_name,
            )
        )
    if not player:
        player = Player(
            name=row.player_name,
            team_name=row.team_name,
            position=row.position,
        )
        db.add(player)

    player.name = row.player_name
    player.team_name = row.team_name
    player.external_id = external_id or player.external_id
    player.is_active = True
    player.position = row.position or player.position
    player.club = row.club
    player.age = row.age
    player.nationality = row.team_name
    player.minutes_played = row.minutes_played
    player.goals = row.goals
    player.assists = row.assists
    player.xg = row.xg
    player.xag = row.xag
    player.injured = row.injured
    player.suspended = row.suspended
    player.market_value_eur = row.market_value_eur
    player.international_caps = row.international_caps
    player.international_goals = row.international_goals
    player.recent_form_score = row.recent_form_score
    player.fitness_score = 0.0 if row.injured or row.suspended else 1.0
    player.player_rating = row.player_rating
    player.ea_fc_rating = row.ea_fc_rating
    player.player_rating_source = source_name
    player.player_rating_version = source_version
    player.player_rating_updated_at = imported_at
    player.data_source = source_name
    player.profile_description = build_player_profile(player)
    return player


def _stable_player_external_id(row: PlayerRatingRow) -> str | None:
    dob = _text(row.raw, "date_of_birth", "dob", "birth_date")
    team_code = _text(row.raw, "fifa_team_code", "team_code", "country_code")
    if not dob and not team_code:
        return None
    code = (team_code or row.team_name).strip().upper()
    name = re.sub(r"\s+", "-", row.player_name.strip().lower())
    return f"player-rating:{code}:{dob or 'unknown-dob'}:{name}"


def _text(raw: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = raw.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _optional_float(raw: dict[str, Any], *keys: str) -> float | None:
    text = _text(raw, *keys)
    if not text:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _optional_int(raw: dict[str, Any], *keys: str) -> int | None:
    value = _optional_float(raw, *keys)
    return int(value) if value is not None else None


def _optional_bool(raw: dict[str, Any], *keys: str) -> bool | None:
    text = _text(raw, *keys).lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "y", "injured", "suspended"}:
        return True
    if text in {"0", "false", "no", "n", "fit", "available"}:
        return False
    return None


def _normalize_position(value: str) -> str:
    text = value.upper().strip()
    if text in {"GOALKEEPER", "KEEPER"}:
        return "GK"
    if text in {"DEFENDER", "CB", "LB", "RB", "LWB", "RWB"}:
        return "DEF"
    if text in {"MIDFIELDER", "DM", "CM", "AM", "CDM", "CAM", "LM", "RM"}:
        return "MID"
    if text in {"FORWARD", "STRIKER", "ATTACKER", "ST", "LW", "RW", "CF"}:
        return "FWD"
    if text in {"GK", "DEF", "MID", "FWD"}:
        return text
    return "UNK"


def _row_hash(raw: dict[str, Any]) -> str:
    payload = json.dumps(raw, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
