"""Load FIFA WC2026 squad players and coaches directly from the squad PDF.

This module is a thin orchestrator:
  1. Parses the PDF (or pre-extracted text) using `fifa_squad_pdf.py`
  2. Upserts all players into the `players` table including the new
     FIFA-specific fields (height_cm, date_of_birth, shirt_number, etc.)
  3. Parses head-coach rows and upserts them into the `coaches` table
  4. Returns a summary dict with row counts

Minimum player threshold: if fewer than MIN_PLAYER_COUNT players are parsed,
the load is aborted and a ValueError is raised so the caller can surface the
parse failure without writing partial data.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db.base import SessionLocal
from app.models.player import Coach, Player, PlayerRatingRecord
from app.models.team import Team
from etl.players.fifa_squad_pdf import (
    DEFAULT_PDF_PATH,
    FIFA_SQUAD_PDF_URL,
    SOURCE_VERSION,
    FifaSquadPlayer,
    download_fifa_squad_pdf,
    extract_text_from_pdf,
    parse_squad_text,
    _iter_clean_lines,
    _parse_team_header,
    _looks_like_player_row,
)
from etl.transform.normalize import canonical

logger = logging.getLogger(__name__)

MIN_PLAYER_COUNT = 1_000
SOURCE_NAME = "FIFA World Cup 2026 Squad PDF"
PLACEHOLDER_SOURCE = "world_cup_2026_placeholder"

_COACH_ROLES = re.compile(
    r"^(?P<role>Head\s*Coach|Assistant\s*Coach|Goalkeeper\s*Coach|Fitness\s*Coach|Coach)\s*"
    r"(?P<rest>.+)$",
    re.IGNORECASE,
)
_NAME_NATIONALITY_RE = re.compile(
    r"^(?P<head>.+?)\s+(?P<nationality>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?P<dob>\d{2}/\d{2}/\d{4})$"
)


def load_squad_from_pdf(
    *,
    source_pdf: str | Path | None = None,
    source_text: str | Path | None = None,
    source_version: str = SOURCE_VERSION,
    download: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Parse the FIFA squad PDF and upsert all players and head coaches.

    Args:
        source_pdf: Path to the PDF file. Defaults to DEFAULT_PDF_PATH.
        source_text: Path to pre-extracted plain text (bypasses PDF parsing).
        source_version: Version string for tracking purposes.
        download: If True, download the PDF from FIFA if not already present.
        dry_run: If True, parse and validate but do not write to the database.

    Returns:
        Dict with keys: players_parsed, players_upserted, coaches_upserted,
        teams_covered, source_version, dry_run, warning (if any).

    Raises:
        ValueError: If fewer than MIN_PLAYER_COUNT players are parsed.
        FileNotFoundError: If the PDF cannot be found and download=False.
    """
    text = _get_source_text(source_pdf, source_text, download)
    players, coaches = _parse_all(text, source_version=source_version)

    if len(players) < MIN_PLAYER_COUNT:
        raise ValueError(
            f"Only {len(players)} players parsed — expected at least {MIN_PLAYER_COUNT}. "
            "This likely indicates a PDF parsing failure. "
            "Aborting load to avoid writing incomplete data."
        )

    teams_covered = len({p.team_name for p in players})
    logger.info(
        "Parsed %d players across %d teams, %d coaches",
        len(players), teams_covered, len(coaches),
    )

    if dry_run:
        return {
            "players_parsed": len(players),
            "players_upserted": 0,
            "coaches_upserted": 0,
            "teams_covered": teams_covered,
            "source_version": source_version,
            "dry_run": True,
        }

    players_upserted = _upsert_players(players, source_version)
    coaches_upserted = _upsert_coaches(coaches, source_version)
    _invalidate_squad_caches()

    result = {
        "players_parsed": len(players),
        "players_upserted": players_upserted,
        "coaches_upserted": coaches_upserted,
        "teams_covered": teams_covered,
        "source_version": source_version,
        "dry_run": False,
    }
    logger.info("Squad load complete: %s", result)
    return result


def _invalidate_squad_caches() -> None:
    try:
        from app.core.cache import cache

        cache.invalidate_prefix("teams:")
    except Exception:
        logger.debug("Could not invalidate squad-related cache", exc_info=True)


def _get_source_text(
    source_pdf: str | Path | None,
    source_text: str | Path | None,
    download: bool,
) -> str:
    if source_text:
        return Path(source_text).read_text(encoding="utf-8")

    pdf_path = Path(source_pdf) if source_pdf else DEFAULT_PDF_PATH
    if download and not pdf_path.exists():
        logger.info("Downloading FIFA squad PDF to %s", pdf_path)
        download_fifa_squad_pdf(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"FIFA squad PDF not found at {pdf_path}. "
            f"Download it from {FIFA_SQUAD_PDF_URL} or pass --download."
        )
    return extract_text_from_pdf(pdf_path)


def _parse_all(
    text: str,
    *,
    source_version: str,
) -> tuple[list[FifaSquadPlayer], list[dict[str, Any]]]:
    """Parse players and head coaches from extracted PDF text."""
    players = parse_squad_text(text, source_version=source_version)

    coaches: list[dict[str, Any]] = []
    current_team = ""
    current_code = ""
    for line in _iter_clean_lines(text):
        maybe_team = _parse_team_header(line)
        if maybe_team:
            current_team, current_code = maybe_team
            continue
        if not current_team or _looks_like_player_row(line):
            continue
        coach = _try_parse_coach_line(line, current_team, current_code)
        if coach:
            coaches.append(coach)

    return players, coaches


def _try_parse_coach_line(
    line: str,
    team_name: str,
    team_code: str,
) -> dict[str, Any] | None:
    role_match = _COACH_ROLES.match(line)
    if not role_match:
        return None
    role = _normalize_coach_role(role_match.group("role"))
    rest = role_match.group("rest").strip()

    name_match = _NAME_NATIONALITY_RE.match(rest)
    if name_match:
        head = name_match.group("head").strip()
        nationality = name_match.group("nationality").strip()
        dob = name_match.group("dob")
    else:
        head = rest
        nationality = _infer_coach_nationality(rest, team_name)
        if nationality and head.endswith(nationality):
            head = head[: -len(nationality)].strip()
        dob = None

    display_name, first_names, last_names = _parse_coach_display_name(head)

    return {
        "name": display_name or head,
        "team_name": canonical(team_name),
        "team_code": team_code,
        "first_names": first_names,
        "last_names": last_names,
        "role": role,
        "nationality": nationality,
        "date_of_birth": dob,
    }


def _parse_coach_display_name(head: str) -> tuple[str, str, str]:
    """Parse FIFA coach name fields into a stable display name."""
    tokens = head.split()
    if not tokens:
        return head, "", head

    surname_tokens: list[str] = []
    while tokens and _is_upperish_token(tokens[0]):
        surname_tokens.append(tokens.pop(0))

    if not surname_tokens:
        return head.title(), "", head

    given_tokens: list[str] = []
    for token in tokens:
        if _is_upperish_token(token):
            break
        given_tokens.append(token)

    given_tokens = _dedupe_repeated_prefix(given_tokens)
    surname_keys = {_normalise_name_token(token) for token in surname_tokens}
    given_tokens = [
        token for token in given_tokens
        if _normalise_name_token(token) not in surname_keys
    ]
    first_names = " ".join(given_tokens)
    last_names = " ".join(surname_tokens)
    display = f"{first_names} {_smart_name(last_names)}".strip()
    return display or _smart_name(last_names), first_names, last_names


def _dedupe_repeated_prefix(tokens: list[str]) -> list[str]:
    if len(tokens) < 2:
        return tokens
    max_size = len(tokens) // 2
    norm_tokens = [_normalise_name_token(token) for token in tokens]
    for size in range(max_size, 0, -1):
        if norm_tokens[:size] == norm_tokens[size:size * 2]:
            return tokens[:size] + tokens[size * 2:]
    return tokens


def _is_upperish_token(token: str) -> bool:
    letters = [char for char in token if char.isalpha()]
    return bool(letters) and token.upper() == token


def _smart_name(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split())


def _normalise_name_token(token: str) -> str:
    return re.sub(r"[^a-z0-9]", "", token.lower())


def _normalize_coach_role(role: str) -> str:
    words = re.findall(r"[A-Za-z]+", role)
    return " ".join(word.capitalize() for word in words) or "Head Coach"


def _infer_coach_nationality(rest: str, team_name: str) -> str | None:
    candidates = {
        team_name,
        canonical(team_name),
        "Argentina",
        "Brazil",
        "Cabo Verde",
        "Canada",
        "Colombia",
        "Croatia",
        "England",
        "France",
        "Germany",
        "Italy",
        "Portugal",
        "Spain",
        "Switzerland",
        "USA",
        "United States",
    }
    for candidate in sorted(candidates, key=len, reverse=True):
        if rest.endswith(candidate):
            return candidate
    tokens = rest.split()
    return tokens[-1] if tokens else None


def _upsert_players(players: list[FifaSquadPlayer], source_version: str) -> int:
    db = SessionLocal()
    upserted = 0
    imported_at = datetime.now(timezone.utc)
    try:
        teams = db.scalars(select(Team)).all()
        team_by_name = {canonical(t.name): t for t in teams}
        affected_teams: set[str] = set()

        for p in players:
            canon_team = canonical(p.team_name)
            affected_teams.add(canon_team)
            _delete_placeholder_players(db, canon_team)
            external_id = _stable_player_external_id(
                team_code=p.fifa_team_code,
                team_name=canon_team,
                player_name=p.player_name,
                date_of_birth=p.dob,
            )
            existing = db.scalar(select(Player).where(Player.external_id == external_id).limit(1))
            if existing is None:
                existing = db.scalar(
                    select(Player)
                    .where(
                        Player.team_name.in_(_team_name_variants(canon_team)),
                        Player.name == p.player_name,
                    )
                    .limit(1)
                )
            if existing is None:
                existing = Player(name=p.player_name, team_name=canon_team)
                db.add(existing)

            existing.team_name = canon_team
            existing.position = p.position
            existing.club = p.club
            existing.age = p.age
            existing.nationality = canon_team
            existing.international_caps = p.international_caps
            existing.international_goals = p.international_goals
            existing.goals = float(p.international_goals)
            existing.recent_form_score = p.recent_form_score
            existing.player_rating = p.player_rating
            existing.player_rating_source = SOURCE_NAME
            existing.player_rating_version = source_version
            existing.player_rating_updated_at = imported_at
            existing.data_source = SOURCE_NAME
            # FIFA squad PDF specific fields
            existing.height_cm = p.height_cm
            existing.date_of_birth = p.dob
            existing.last_names = p.source_player_name.split()[0] if p.source_player_name else None
            existing.first_names = " ".join(p.source_player_name.split()[1:]) if p.source_player_name else None
            existing.fitness_score = 1.0
            existing.is_active = True
            existing.external_id = external_id
            upserted += 1

        _dedupe_players(db, affected_teams)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return upserted


def _upsert_coaches(coaches: list[dict[str, Any]], source_version: str) -> int:
    db = SessionLocal()
    upserted = 0
    imported_at = datetime.now(timezone.utc)
    try:
        teams = db.scalars(select(Team)).all()
        team_by_name = {canonical(t.name): t for t in teams}

        seen_teams: set[str] = set()
        for c in coaches:
            canon_team = c["team_name"]
            # Keep only one coach per team (prefer Head Coach; skip duplicates)
            if canon_team in seen_teams and c.get("role", "") != "Head Coach":
                continue

            team = team_by_name.get(canon_team)
            existing = db.scalar(
                select(Coach)
                .where(
                    Coach.team_name.in_(_team_name_variants(canon_team)),
                    Coach.data_source != PLACEHOLDER_SOURCE,
                )
                .limit(1)
            )
            _delete_placeholder_coach(db, canon_team)
            db.flush()
            if existing is None:
                existing = Coach(name=c["name"], team_name=canon_team)
                db.add(existing)

            existing.name = c["name"]
            existing.team_name = canon_team
            existing.team_id = team.id if team else None
            existing.first_names = c.get("first_names") or None
            existing.last_names = c.get("last_names") or None
            existing.role = c.get("role") or "Head Coach"
            existing.nationality = c.get("nationality") or None
            existing.date_of_birth = c.get("date_of_birth") or None
            existing.data_source = SOURCE_NAME
            seen_teams.add(canon_team)
            upserted += 1

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return upserted


def _team_name_variants(team_name: str) -> list[str]:
    canon = canonical(team_name)
    variants = {team_name, canon, canon.replace(" and ", " And ")}
    if canon == "Bosnia and Herzegovina":
        variants.update({
            "Bosnia And Herzegovina",
            "Bosnia & Herzegovina",
            "Bosnia-Herzegovina",
            "BIH",
        })
    return sorted(variants)


def _delete_placeholder_players(db, team_name: str) -> None:
    for row in db.scalars(
        select(Player).where(
            Player.team_name == canonical(team_name),
            Player.data_source == PLACEHOLDER_SOURCE,
        )
    ).all():
        row.is_active = False


def _delete_placeholder_coach(db, team_name: str) -> None:
    row = db.scalar(
        select(Coach)
        .where(
            Coach.team_name == canonical(team_name),
            Coach.data_source == PLACEHOLDER_SOURCE,
        )
        .limit(1)
    )
    if row:
        db.delete(row)


def _dedupe_players(db, team_names: set[str]) -> None:
    for team_name in team_names:
        rows = db.scalars(
            select(Player).where(Player.team_name.in_(_team_name_variants(team_name)))
        ).all()
        grouped: dict[str, list[Player]] = {}
        for row in rows:
            grouped.setdefault(_normalised_player_key(row.name), []).append(row)
        for duplicates in grouped.values():
            if len(duplicates) <= 1:
                continue
            keep = sorted(
                duplicates,
                key=lambda row: (
                    0 if row.data_source == SOURCE_NAME else 1,
                    0 if row.height_cm is not None else 1,
                    0 if row.date_of_birth else 1,
                    row.id,
                ),
            )[0]
            keep.team_name = canonical(keep.team_name)
            for row in duplicates:
                if row.id != keep.id:
                    db.query(PlayerRatingRecord).filter(
                        PlayerRatingRecord.player_id == row.id
                    ).update(
                        {PlayerRatingRecord.player_id: keep.id},
                        synchronize_session=False,
                    )
                    row.is_active = False


def _stable_player_external_id(
    *,
    team_code: str | None,
    team_name: str,
    player_name: str,
    date_of_birth: str | None,
) -> str:
    code = (team_code or team_name).strip().upper()
    dob = (date_of_birth or "unknown-dob").strip()
    name = _normalised_player_key(player_name).replace(" ", "-")
    return f"fifa-wc2026:{code}:{dob}:{name}"


def _normalised_player_key(name: str | None) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Load FIFA WC2026 squad from PDF into DB")
    parser.add_argument("--source-pdf", default=str(DEFAULT_PDF_PATH))
    parser.add_argument("--source-text")
    parser.add_argument("--source-version", default=SOURCE_VERSION)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = load_squad_from_pdf(
        source_pdf=args.source_pdf if not args.source_text else None,
        source_text=args.source_text,
        source_version=args.source_version,
        download=args.download,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, default=str))
