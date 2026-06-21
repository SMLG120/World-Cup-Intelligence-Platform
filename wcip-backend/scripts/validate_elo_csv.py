#!/usr/bin/env python3
"""Validate the static World Football Elo PDF CSV extract."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.transform.normalize import canonical

CSV_COLUMNS = [
    "rank",
    "team",
    "rating",
    "average_rank",
    "average_rating",
    "one_year_change_rank",
    "one_year_change_rating",
    "matches_total",
    "matches_home",
    "matches_away",
    "matches_neutral",
    "wins",
    "losses",
    "draws",
    "goals_for",
    "goals_against",
    "source_name",
    "source_date",
]

MANDATORY_TOP_ROWS = [
    ("Spain", 1, 2129),
    ("Argentina", 2, 2128),
    ("France", 3, 2084),
    ("England", 4, 2055),
    ("Colombia", 5, 1998),
    ("Brazil", 6, 1986),
]


class EloCsvValidationError(ValueError):
    """Raised when the static Elo CSV is not safe to ingest."""


def _to_int(value: str, field: str, row_number: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise EloCsvValidationError(f"row {row_number}: {field} must be an integer") from exc


def validate_rows(
    rows: list[dict[str, str]],
    *,
    require_full_extract: bool = True,
    check_db_teams: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if require_full_extract and len(rows) <= 200:
        errors.append(f"expected more than 200 teams for a full extract, found {len(rows)}")

    seen: set[str] = set()
    parsed: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=2):
        missing_columns = [column for column in CSV_COLUMNS if column not in row]
        if missing_columns:
            errors.append(f"row {idx}: missing columns {missing_columns}")
            continue

        team = str(row.get("team", "")).strip()
        if not team:
            errors.append(f"row {idx}: team name is empty")
            continue
        team_key = canonical(team)
        if team_key in seen:
            errors.append(f"row {idx}: duplicate team name {team!r}")
        seen.add(team_key)

        try:
            rank = _to_int(row["rank"], "rank", idx)
            rating = _to_int(row["rating"], "rating", idx)
        except EloCsvValidationError as exc:
            errors.append(str(exc))
            continue
        if rank <= 0:
            errors.append(f"row {idx}: rank must be positive")
        if rating < 0:
            errors.append(f"row {idx}: rating must not be negative")
        parsed.append({"team": team, "rank": rank, "rating": rating})

    by_team = {canonical(row["team"]): row for row in parsed}
    for team, expected_rank, expected_rating in MANDATORY_TOP_ROWS:
        actual = by_team.get(canonical(team))
        if not actual:
            errors.append(f"mandatory top row missing: {team}")
            continue
        if actual["rank"] != expected_rank or actual["rating"] != expected_rating:
            errors.append(
                f"mandatory top row mismatch for {team}: "
                f"rank={actual['rank']} rating={actual['rating']} expected rank={expected_rank} rating={expected_rating}"
            )

    unmatched_wc_teams: list[str] = []
    if check_db_teams:
        try:
            from sqlalchemy import select
            from app.db.base import SessionLocal
            from app.models.team import Team
            from wcip.data.wc2026 import CONFIRMED_QUALIFIERS

            db = SessionLocal()
            try:
                db_teams = {canonical(team.name) for team in db.scalars(select(Team)).all()}
                csv_teams = set(by_team)
                for qualifier in CONFIRMED_QUALIFIERS:
                    name = canonical(qualifier["team_name"])
                    if name in db_teams and name not in csv_teams:
                        unmatched_wc_teams.append(qualifier["team_name"])
            finally:
                db.close()
        except Exception as exc:
            warnings.append(f"database team match check skipped: {exc}")

    if unmatched_wc_teams:
        warnings.append(
            f"{len(unmatched_wc_teams)} World Cup teams were not found in the Elo CSV: "
            f"{unmatched_wc_teams[:10]}"
        )

    if errors:
        raise EloCsvValidationError("; ".join(errors))

    return {
        "rows": len(rows),
        "unique_teams": len(seen),
        "warnings": warnings,
        "mandatory_top_rows": len(MANDATORY_TOP_ROWS),
        "unmatched_world_cup_teams": unmatched_wc_teams,
    }


def validate_csv(
    csv_path: str | Path,
    *,
    require_full_extract: bool = True,
    check_db_teams: bool = True,
) -> dict[str, Any]:
    path = Path(csv_path)
    if not path.exists():
        raise EloCsvValidationError(f"CSV does not exist: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CSV_COLUMNS:
            raise EloCsvValidationError(f"unexpected CSV columns: {reader.fieldnames}")
        rows = list(reader)
    return validate_rows(rows, require_full_extract=require_full_extract, check_db_teams=check_db_teams)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv_path",
        nargs="?",
        default="data/processed/world_football_elo_ratings_2026_06_21.csv",
    )
    parser.add_argument("--allow-partial", action="store_true", help="Skip the >200-team full extraction check.")
    parser.add_argument("--skip-db-check", action="store_true", help="Skip WC team matching against the local DB.")
    args = parser.parse_args(argv)

    try:
        result = validate_csv(
            args.csv_path,
            require_full_extract=not args.allow_partial,
            check_db_teams=not args.skip_db_check,
        )
    except EloCsvValidationError as exc:
        print(f"Elo CSV validation failed: {exc}", file=sys.stderr)
        return 1

    print(
        "Elo CSV validation passed: "
        f"rows={result['rows']} unique_teams={result['unique_teams']} "
        f"mandatory_top_rows={result['mandatory_top_rows']}"
    )
    for warning in result["warnings"]:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
