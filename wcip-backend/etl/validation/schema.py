"""Validation layer: schema checks and business-rule assertions.

All validate_* functions raise ValidationError on failure.
They return the (possibly coerced) clean record on success.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


class ValidationError(ValueError):
    pass


@dataclass
class ValidatedMatch:
    match_date: date
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    tournament: str | None
    city: str | None
    country: str | None
    neutral: bool
    outcome: int  # 0=away, 1=draw, 2=home


def validate_match(raw: dict[str, Any]) -> ValidatedMatch:
    required = ["match_date", "home_team", "away_team", "home_goals", "away_goals"]
    for field in required:
        if field not in raw:
            raise ValidationError(f"Missing field: {field}")

    home = str(raw["home_team"]).strip()
    away = str(raw["away_team"]).strip()
    if not home:
        raise ValidationError("home_team is empty")
    if not away:
        raise ValidationError("away_team is empty")
    if home == away:
        raise ValidationError(f"home_team == away_team: {home}")

    try:
        hg = int(raw["home_goals"])
        ag = int(raw["away_goals"])
    except (TypeError, ValueError) as e:
        raise ValidationError(f"Invalid goal values: {e}") from e

    if hg < 0 or ag < 0:
        raise ValidationError(f"Negative goal count: {hg}-{ag}")
    if hg > 30 or ag > 30:
        raise ValidationError(f"Implausible score: {hg}-{ag}")

    md = raw["match_date"]
    if not isinstance(md, date):
        try:
            md = date.fromisoformat(str(md))
        except ValueError as e:
            raise ValidationError(f"Invalid date: {raw['match_date']}") from e

    if md > date.today():
        raise ValidationError(f"Future match date in historical dataset: {md}")

    from etl.transform.normalize import compute_outcome
    outcome = compute_outcome(hg, ag)

    return ValidatedMatch(
        match_date=md,
        home_team=home,
        away_team=away,
        home_goals=hg,
        away_goals=ag,
        tournament=raw.get("tournament") or None,
        city=raw.get("city") or None,
        country=raw.get("country") or None,
        neutral=bool(raw.get("neutral", True)),
        outcome=outcome,
    )


def validate_player(raw: dict[str, Any]) -> dict[str, Any]:
    name = str(raw.get("name", "")).strip()
    team = str(raw.get("team_name", "")).strip()
    if not name:
        raise ValidationError("player name is empty")
    if not team:
        raise ValidationError("player team_name is empty")

    clean = dict(raw)
    clean["name"] = name
    clean["team_name"] = team

    # Coerce numeric fields to sane values
    for field in ("goals", "assists", "xg", "xag", "minutes_played",
                  "key_passes", "progressive_passes", "progressive_carries",
                  "tackles", "interceptions"):
        v = clean.get(field, 0)
        try:
            clean[field] = max(0.0, float(v) if v else 0.0)
        except (TypeError, ValueError):
            clean[field] = 0.0

    return clean
