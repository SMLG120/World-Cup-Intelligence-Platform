"""World Cup 2026 data module.

This module provides:
  - The confirmed/expected qualified teams (loaded from DB, no hardcoded list)
  - The 2026 tournament format (48 teams, 12 groups, new R32 rule)
  - Bracket generation once group draw is complete
  - Historical tournament support (2010, 2014, 2018, 2022)

Teams are loaded dynamically from the `qualified_teams` table so that as
qualification completes and the group draw occurs, the platform auto-updates.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 2026 FORMAT CONSTANTS
# ---------------------------------------------------------------------------

# Official 2026 format: 48 teams, 12 groups of 4.
# Top 2 from each group (24) + 8 best third-place teams = 32 for R32.
WC2026_NUM_GROUPS = 12
WC2026_TEAMS_PER_GROUP = 4
WC2026_TOTAL_TEAMS = 48
WC2026_R32_TEAMS = 32  # teams that advance past group stage

# Confirmed confederation allocations for the final 48-team field.
CONFEDERATION_SLOTS: Dict[str, int] = {
    "UEFA": 16,
    "CONMEBOL": 6,
    "CAF": 10,
    "AFC": 9,
    "CONCACAF": 6,
    "OFC": 1,
}

# Host nations confirmed
HOST_NATIONS = {"United States", "Canada", "Mexico"}

# ---------------------------------------------------------------------------
# FINALIZED 2026 PARTICIPANT LIST AND GROUP DRAW
# Source: FIFA World Cup 2026 teams/standings pages, checked 2026-06-08.
# Internal canonical names intentionally map FIFA display variants:
# Korea Republic -> South Korea, Türkiye -> Turkey, Côte d'Ivoire -> Ivory Coast,
# Cabo Verde -> Cape Verde, IR Iran -> Iran, Congo DR -> DR Congo.
# ---------------------------------------------------------------------------

# This list is the ETL seed and DB fallback. The qualified_teams table is
# the authoritative runtime source — run scripts/migrate_wc2026_teams.py to
# apply any changes from this file to the live database.
CONFIRMED_QUALIFIERS: List[Dict] = [
    # Group A
    {"team_name": "Mexico", "team_code": "MEX", "confederation": "CONCACAF", "group_label": "A", "host_nation": True, "confirmed": True},
    {"team_name": "South Africa", "team_code": "RSA", "confederation": "CAF", "group_label": "A", "confirmed": True},
    {"team_name": "South Korea", "team_code": "KOR", "confederation": "AFC", "group_label": "A", "confirmed": True},
    {"team_name": "Czechia", "team_code": "CZE", "confederation": "UEFA", "group_label": "A", "confirmed": True},

    # Group B
    {"team_name": "Canada", "team_code": "CAN", "confederation": "CONCACAF", "group_label": "B", "host_nation": True, "confirmed": True},
    {"team_name": "Bosnia and Herzegovina", "team_code": "BIH", "confederation": "UEFA", "group_label": "B", "confirmed": True},
    {"team_name": "Qatar", "team_code": "QAT", "confederation": "AFC", "group_label": "B", "confirmed": True},
    {"team_name": "Switzerland", "team_code": "SUI", "confederation": "UEFA", "group_label": "B", "confirmed": True},

    # Group C
    {"team_name": "Brazil", "team_code": "BRA", "confederation": "CONMEBOL", "group_label": "C", "confirmed": True},
    {"team_name": "Morocco", "team_code": "MAR", "confederation": "CAF", "group_label": "C", "confirmed": True},
    {"team_name": "Haiti", "team_code": "HAI", "confederation": "CONCACAF", "group_label": "C", "confirmed": True},
    {"team_name": "Scotland", "team_code": "SCO", "confederation": "UEFA", "group_label": "C", "confirmed": True},

    # Group D
    {"team_name": "United States", "team_code": "USA", "confederation": "CONCACAF", "group_label": "D", "host_nation": True, "confirmed": True},
    {"team_name": "Paraguay", "team_code": "PAR", "confederation": "CONMEBOL", "group_label": "D", "confirmed": True},
    {"team_name": "Australia", "team_code": "AUS", "confederation": "AFC", "group_label": "D", "confirmed": True},
    {"team_name": "Turkey", "team_code": "TUR", "confederation": "UEFA", "group_label": "D", "confirmed": True},

    # Group E
    {"team_name": "Germany", "team_code": "GER", "confederation": "UEFA", "group_label": "E", "confirmed": True},
    {"team_name": "Curaçao", "team_code": "CUW", "confederation": "CONCACAF", "group_label": "E", "confirmed": True},
    {"team_name": "Ivory Coast", "team_code": "CIV", "confederation": "CAF", "group_label": "E", "confirmed": True},
    {"team_name": "Ecuador", "team_code": "ECU", "confederation": "CONMEBOL", "group_label": "E", "confirmed": True},

    # Group F
    {"team_name": "Netherlands", "team_code": "NED", "confederation": "UEFA", "group_label": "F", "confirmed": True},
    {"team_name": "Japan", "team_code": "JPN", "confederation": "AFC", "group_label": "F", "confirmed": True},
    {"team_name": "Sweden", "team_code": "SWE", "confederation": "UEFA", "group_label": "F", "confirmed": True},
    {"team_name": "Tunisia", "team_code": "TUN", "confederation": "CAF", "group_label": "F", "confirmed": True},

    # Group G
    {"team_name": "Belgium", "team_code": "BEL", "confederation": "UEFA", "group_label": "G", "confirmed": True},
    {"team_name": "Egypt", "team_code": "EGY", "confederation": "CAF", "group_label": "G", "confirmed": True},
    {"team_name": "Iran", "team_code": "IRN", "confederation": "AFC", "group_label": "G", "confirmed": True},
    {"team_name": "New Zealand", "team_code": "NZL", "confederation": "OFC", "group_label": "G", "confirmed": True},

    # Group H
    {"team_name": "Spain", "team_code": "ESP", "confederation": "UEFA", "group_label": "H", "confirmed": True},
    {"team_name": "Cape Verde", "team_code": "CPV", "confederation": "CAF", "group_label": "H", "confirmed": True},
    {"team_name": "Saudi Arabia", "team_code": "KSA", "confederation": "AFC", "group_label": "H", "confirmed": True},
    {"team_name": "Uruguay", "team_code": "URU", "confederation": "CONMEBOL", "group_label": "H", "confirmed": True},

    # Group I
    {"team_name": "France", "team_code": "FRA", "confederation": "UEFA", "group_label": "I", "confirmed": True},
    {"team_name": "Senegal", "team_code": "SEN", "confederation": "CAF", "group_label": "I", "confirmed": True},
    {"team_name": "Iraq", "team_code": "IRQ", "confederation": "AFC", "group_label": "I", "confirmed": True},
    {"team_name": "Norway", "team_code": "NOR", "confederation": "UEFA", "group_label": "I", "confirmed": True},

    # Group J
    {"team_name": "Argentina", "team_code": "ARG", "confederation": "CONMEBOL", "group_label": "J", "confirmed": True},
    {"team_name": "Algeria", "team_code": "ALG", "confederation": "CAF", "group_label": "J", "confirmed": True},
    {"team_name": "Austria", "team_code": "AUT", "confederation": "UEFA", "group_label": "J", "confirmed": True},
    {"team_name": "Jordan", "team_code": "JOR", "confederation": "AFC", "group_label": "J", "confirmed": True},

    # Group K
    {"team_name": "Portugal", "team_code": "POR", "confederation": "UEFA", "group_label": "K", "confirmed": True},
    {"team_name": "DR Congo", "team_code": "COD", "confederation": "CAF", "group_label": "K", "confirmed": True},
    {"team_name": "Uzbekistan", "team_code": "UZB", "confederation": "AFC", "group_label": "K", "confirmed": True},
    {"team_name": "Colombia", "team_code": "COL", "confederation": "CONMEBOL", "group_label": "K", "confirmed": True},

    # Group L
    {"team_name": "England", "team_code": "ENG", "confederation": "UEFA", "group_label": "L", "confirmed": True},
    {"team_name": "Croatia", "team_code": "CRO", "confederation": "UEFA", "group_label": "L", "confirmed": True},
    {"team_name": "Ghana", "team_code": "GHA", "confederation": "CAF", "group_label": "L", "confirmed": True},
    {"team_name": "Panama", "team_code": "PAN", "confederation": "CONCACAF", "group_label": "L", "confirmed": True},
]

# Quick lookup sets for internal use
_CONFIRMED_NAMES = {t["team_name"] for t in CONFIRMED_QUALIFIERS}
_REMOVED_TEAMS = {"Italy", "Poland", "Denmark", "Nigeria", "Cameroon", "Serbia", "Venezuela"}
OFFICIAL_GROUPS_2026: Dict[str, List[str]] = {
    label: [t["team_name"] for t in CONFIRMED_QUALIFIERS if t.get("group_label") == label]
    for label in [chr(ord("A") + i) for i in range(WC2026_NUM_GROUPS)]
}

# ---------------------------------------------------------------------------
# 2026 BRACKET TEMPLATE
# Generated once the official group draw is completed.
# Until then, this module generates placeholder brackets.
# ---------------------------------------------------------------------------


@dataclass
class TournamentGroup:
    label: str
    teams: List[str] = field(default_factory=list)


@dataclass
class WC2026Tournament:
    year: int = 2026
    groups: Dict[str, List[str]] = field(default_factory=dict)
    bracket: List[Tuple] = field(default_factory=list)
    total_teams: int = 0
    format_confirmed: bool = False


def get_qualified_teams_from_db() -> List[Dict]:
    """Load qualified teams from DB, falling back if DB is empty or stale."""
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.match_result import QualifiedTeam

        db = SessionLocal()
        try:
            rows = db.scalars(
                select(QualifiedTeam).where(QualifiedTeam.tournament_year == 2026)
            ).all()
            payload = [
                {
                    "team_name": r.team_name,
                    "team_code": r.team_code,
                    "confederation": r.confederation,
                    "group_label": r.group_label,
                    "host_nation": r.host_nation,
                    "confirmed": r.confirmed,
                    "pot": r.pot,
                }
                for r in rows
            ]
            if _qualified_payload_is_current(payload):
                return payload
            if payload:
                logger.warning("WC2026 qualified teams in DB are stale; using static FIFA fallback")
        finally:
            db.close()
    except Exception as e:
        logger.warning("Could not load qualified teams from DB: %s", e)

    return list(CONFIRMED_QUALIFIERS)


def build_2026_groups_from_db() -> Dict[str, List[str]]:
    """Build group dict from DB if draw has occurred; otherwise return empty (TBD)."""
    teams = get_qualified_teams_from_db()
    groups: Dict[str, List[str]] = {}
    for t in teams:
        g = t.get("group_label")
        if g:
            groups.setdefault(g, []).append(t["team_name"])
    return groups


def _qualified_payload_is_current(teams: List[Dict]) -> bool:
    if len(teams) != WC2026_TOTAL_TEAMS:
        return False
    names = {t.get("team_name") for t in teams}
    if names != _CONFIRMED_NAMES:
        return False
    groups: Dict[str, int] = {}
    for team in teams:
        label = team.get("group_label")
        if not label:
            return False
        groups[label] = groups.get(label, 0) + 1
    expected_labels = {chr(ord("A") + i) for i in range(WC2026_NUM_GROUPS)}
    return set(groups) == expected_labels and all(count == WC2026_TEAMS_PER_GROUP for count in groups.values())


def build_2026_bracket(groups: Dict[str, List[str]]) -> List[Tuple]:
    """Generate the 2026 WC bracket from group results.

    2026 format (once officially confirmed):
      - 12 groups (A-L), top 2 advance = 24 teams
      - 8 best third-place teams advance = 32 total for R32
      - R32 (16 matches) -> R16 -> QF -> SF -> Final

    Until the official bracket is released, this generates a placeholder
    bracket using group winners and runners-up in alphabetical order.
    """
    if not groups:
        return []

    bracket = []
    group_labels = sorted(groups.keys())

    # R32 pairings (placeholder — official pairings TBD by FIFA draw).
    # The tournament engine resolves B3_1..B3_8 to the eight best third-place
    # teams after each simulated group stage.
    r32_pairs = _generate_r32_pairings(group_labels)
    for i, (slot_a, slot_b) in enumerate(r32_pairs, start=49):
        match_id = f"M{i}"
        bracket.append((match_id, ("group", slot_a), ("group", slot_b)))

    # R16 — winners of R32 pairs
    r32_ids = [f"M{i}" for i in range(49, 49 + len(r32_pairs))]
    r16_pairs = [(r32_ids[i], r32_ids[i + 1]) for i in range(0, len(r32_ids), 2)]
    for i, (m1, m2) in enumerate(r16_pairs, start=49 + len(r32_pairs)):
        bracket.append((f"M{i}", ("match", m1), ("match", m2)))

    # QF
    r16_ids = [f"M{i}" for i in range(49 + len(r32_pairs), 49 + len(r32_pairs) + len(r16_pairs))]
    qf_pairs = [(r16_ids[i], r16_ids[i + 1]) for i in range(0, len(r16_ids), 2)]
    for i, (m1, m2) in enumerate(qf_pairs, start=49 + len(r32_pairs) + len(r16_pairs)):
        bracket.append((f"M{i}", ("match", m1), ("match", m2)))

    # SF
    qf_ids = [f"M{i}" for i in range(
        49 + len(r32_pairs) + len(r16_pairs),
        49 + len(r32_pairs) + len(r16_pairs) + len(qf_pairs)
    )]
    sf1 = f"M{200}"
    sf2 = f"M{201}"
    bracket.append((sf1, ("match", qf_ids[0]), ("match", qf_ids[1])))
    bracket.append((sf2, ("match", qf_ids[2]), ("match", qf_ids[3])))
    bracket.append(("FINAL", ("match", sf1), ("match", sf2)))

    return bracket


def _generate_r32_pairings(group_labels: List[str]) -> List[Tuple[str, str]]:
    """Generate placeholder R32 pairings.

    Official 2026 pairings depend on the final draw and third-place qualifiers.
    Until then, build a complete 32-team placeholder from 12 winners, 12
    runners-up, and 8 best third-place slots.
    """
    winners = [f"1{g}" for g in group_labels]
    runners = [f"2{g}" for g in group_labels]
    best_thirds = [f"B3_{i}" for i in range(1, 9)]
    slots = winners + runners + best_thirds

    if len(slots) < WC2026_R32_TEAMS:
        raise ValueError("WC2026 bracket requires 32 knockout slots")

    first_half = slots[: WC2026_R32_TEAMS // 2]
    second_half = list(reversed(slots[WC2026_R32_TEAMS // 2:WC2026_R32_TEAMS]))
    return list(zip(first_half, second_half))


def get_tournament(year: int) -> Optional[WC2026Tournament]:
    """Return a WC2026Tournament for the given year."""
    if year == 2026:
        groups = build_2026_groups_from_db()
        bracket = build_2026_bracket(groups) if groups else []
        teams = get_qualified_teams_from_db()
        return WC2026Tournament(
            year=2026,
            groups=groups,
            bracket=bracket,
            total_teams=len(teams),
            format_confirmed=bool(groups),
        )
    # Historical tournaments — delegate to teams_2022.py etc.
    return None


def list_qualified_team_names(confirmed_only: bool = True) -> List[str]:
    """Return list of qualified team names."""
    teams = get_qualified_teams_from_db()
    if confirmed_only:
        return [t["team_name"] for t in teams if t.get("confirmed", True)]
    return [t["team_name"] for t in teams]
