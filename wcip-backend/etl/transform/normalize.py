"""Transform layer: team name normalization.

International datasets use different spellings for the same country.
This module provides a canonical name map and fuzzy-match fallback.
"""
from __future__ import annotations

import re
from typing import Dict

# Map variant spellings -> canonical name used throughout this platform.
NAME_MAP: Dict[str, str] = {
    # United States variants
    "USA": "United States",
    "US": "United States",
    "United States of America": "United States",
    "America": "United States",

    # South Korea
    "Korea Republic": "South Korea",
    "Korea DPR": "North Korea",
    "Rep. Korea": "South Korea",

    # Ivory Coast
    "Côte d'Ivoire": "Ivory Coast",
    "Cote d'Ivoire": "Ivory Coast",
    "Cote D'Ivoire": "Ivory Coast",

    # Czech Republic
    "Czechia": "Czech Republic",
    "Czech Rep.": "Czech Republic",

    # North Macedonia
    "Macedonia": "North Macedonia",
    "FYR Macedonia": "North Macedonia",

    # Bosnia
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Bosnia-Herzegovina": "Bosnia & Herzegovina",

    # Trinidad
    "Trinidad and Tobago": "Trinidad & Tobago",
    "T&T": "Trinidad & Tobago",

    # Saudi Arabia
    "KSA": "Saudi Arabia",
    "Kingdom of Saudi Arabia": "Saudi Arabia",

    # Iran
    "IR Iran": "Iran",
    "Islamic Republic of Iran": "Iran",

    # England
    "ENG": "England",

    # Country code -> name
    "ARG": "Argentina",
    "BRA": "Brazil",
    "FRA": "France",
    "ESP": "Spain",
    "GER": "Germany",
    "POR": "Portugal",
    "NED": "Netherlands",
    "BEL": "Belgium",
    "ITA": "Italy",
    "CRO": "Croatia",
    "MAR": "Morocco",
    "JPN": "Japan",
    "MEX": "Mexico",
    "URU": "Uruguay",
    "COL": "Colombia",
    "SUI": "Switzerland",
    "DEN": "Denmark",
    "AUT": "Austria",
    "SEN": "Senegal",
    "POL": "Poland",
    "SRB": "Serbia",
    "AUS": "Australia",
    "QAT": "Qatar",
    "ECU": "Ecuador",
    "WAL": "Wales",
    "CAN": "Canada",
    "KOR": "South Korea",
    "TUN": "Tunisia",
    "CMR": "Cameroon",
    "GHA": "Ghana",
    "NGA": "Nigeria",
    "EGY": "Egypt",
}


def canonical(name: str) -> str:
    """Return the canonical team name for a given input string."""
    stripped = name.strip()
    # Direct lookup first
    if stripped in NAME_MAP:
        return NAME_MAP[stripped]
    # Case-insensitive lookup
    lower = stripped.lower()
    for k, v in NAME_MAP.items():
        if k.lower() == lower:
            return v
    # Already canonical or unknown — return as-is
    return stripped


def normalize_match(raw: dict) -> dict:
    """Apply canonical names to home_team / away_team fields in a raw match dict."""
    return {
        **raw,
        "home_team": canonical(raw.get("home_team", "")),
        "away_team": canonical(raw.get("away_team", "")),
    }


def compute_outcome(home_goals: int, away_goals: int) -> int:
    """Return outcome label: 0=away win, 1=draw, 2=home win."""
    if home_goals > away_goals:
        return 2
    if home_goals < away_goals:
        return 0
    return 1


def is_competitive(tournament: str | None) -> bool:
    """Return True if the tournament is a competitive fixture (not a friendly)."""
    if not tournament:
        return False
    friendly_patterns = [
        r"\bfriendly\b", r"\bkirin cup\b", r"\bjones cup\b",
        r"\binvitational\b", r"\bcelebration\b",
    ]
    low = tournament.lower()
    for pat in friendly_patterns:
        if re.search(pat, low):
            return False
    return True
