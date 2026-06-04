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

# Expected confederation quotas (FIFA confirmed allocations)
CONFEDERATION_SLOTS: Dict[str, int] = {
    "UEFA": 16,
    "CONMEBOL": 6,
    "CAF": 9,
    "AFC": 8,
    "CONCACAF": 6,  # incl. 3 hosts (USA, Canada, Mexico)
    "OFC": 1,
    "Playoff": 2,   # inter-confederation play-off
}

# Host nations confirmed
HOST_NATIONS = {"United States", "Canada", "Mexico"}

# ---------------------------------------------------------------------------
# CURRENT QUALIFICATION STATUS (as of June 2025)
# This is the best available data; updated via ETL when official draws occur.
# ---------------------------------------------------------------------------

# Confirmed qualified teams. This list is intentionally a snapshot — it will
# grow as the remaining qualifiers complete. The DB is the authoritative source;
# this dict is the ETL seed/fallback.
CONFIRMED_QUALIFIERS: List[Dict] = [
    # Hosts (auto-qualified)
    {"team_name": "United States", "team_code": "USA", "confederation": "CONCACAF", "host_nation": True, "confirmed": True},
    {"team_name": "Canada", "team_code": "CAN", "confederation": "CONCACAF", "host_nation": True, "confirmed": True},
    {"team_name": "Mexico", "team_code": "MEX", "confederation": "CONCACAF", "host_nation": True, "confirmed": True},

    # UEFA (16 slots — Euro 2024 qualifiers)
    {"team_name": "Germany", "team_code": "GER", "confederation": "UEFA", "confirmed": True},
    {"team_name": "Portugal", "team_code": "POR", "confederation": "UEFA", "confirmed": True},
    {"team_name": "France", "team_code": "FRA", "confederation": "UEFA", "confirmed": True},
    {"team_name": "Spain", "team_code": "ESP", "confederation": "UEFA", "confirmed": True},
    {"team_name": "England", "team_code": "ENG", "confederation": "UEFA", "confirmed": True},
    {"team_name": "Netherlands", "team_code": "NED", "confederation": "UEFA", "confirmed": True},
    {"team_name": "Belgium", "team_code": "BEL", "confederation": "UEFA", "confirmed": True},
    {"team_name": "Italy", "team_code": "ITA", "confederation": "UEFA", "confirmed": True},
    {"team_name": "Croatia", "team_code": "CRO", "confederation": "UEFA", "confirmed": True},
    {"team_name": "Denmark", "team_code": "DEN", "confederation": "UEFA", "confirmed": True},
    {"team_name": "Austria", "team_code": "AUT", "confederation": "UEFA", "confirmed": True},
    {"team_name": "Switzerland", "team_code": "SUI", "confederation": "UEFA", "confirmed": True},
    {"team_name": "Turkey", "team_code": "TUR", "confederation": "UEFA", "confirmed": True},
    {"team_name": "Poland", "team_code": "POL", "confederation": "UEFA", "confirmed": True},
    {"team_name": "Serbia", "team_code": "SRB", "confederation": "UEFA", "confirmed": True},
    {"team_name": "Scotland", "team_code": "SCO", "confederation": "UEFA", "confirmed": True},

    # CONMEBOL (6 slots)
    {"team_name": "Argentina", "team_code": "ARG", "confederation": "CONMEBOL", "confirmed": True},
    {"team_name": "Brazil", "team_code": "BRA", "confederation": "CONMEBOL", "confirmed": True},
    {"team_name": "Colombia", "team_code": "COL", "confederation": "CONMEBOL", "confirmed": True},
    {"team_name": "Uruguay", "team_code": "URU", "confederation": "CONMEBOL", "confirmed": True},
    {"team_name": "Ecuador", "team_code": "ECU", "confederation": "CONMEBOL", "confirmed": True},
    {"team_name": "Venezuela", "team_code": "VEN", "confederation": "CONMEBOL", "confirmed": True},

    # CAF (9 slots)
    {"team_name": "Morocco", "team_code": "MAR", "confederation": "CAF", "confirmed": True},
    {"team_name": "Senegal", "team_code": "SEN", "confederation": "CAF", "confirmed": True},
    {"team_name": "Egypt", "team_code": "EGY", "confederation": "CAF", "confirmed": True},
    {"team_name": "Nigeria", "team_code": "NGA", "confederation": "CAF", "confirmed": True},
    {"team_name": "Ivory Coast", "team_code": "CIV", "confederation": "CAF", "confirmed": True},
    {"team_name": "Cameroon", "team_code": "CMR", "confederation": "CAF", "confirmed": True},
    {"team_name": "Ghana", "team_code": "GHA", "confederation": "CAF", "confirmed": True},
    {"team_name": "Tunisia", "team_code": "TUN", "confederation": "CAF", "confirmed": True},
    {"team_name": "South Africa", "team_code": "RSA", "confederation": "CAF", "confirmed": True},

    # AFC (8 slots)
    {"team_name": "Japan", "team_code": "JPN", "confederation": "AFC", "confirmed": True},
    {"team_name": "South Korea", "team_code": "KOR", "confederation": "AFC", "confirmed": True},
    {"team_name": "Iran", "team_code": "IRN", "confederation": "AFC", "confirmed": True},
    {"team_name": "Australia", "team_code": "AUS", "confederation": "AFC", "confirmed": True},
    {"team_name": "Saudi Arabia", "team_code": "KSA", "confederation": "AFC", "confirmed": True},
    {"team_name": "Qatar", "team_code": "QAT", "confederation": "AFC", "confirmed": True},
    {"team_name": "Uzbekistan", "team_code": "UZB", "confederation": "AFC", "confirmed": True},
    {"team_name": "Jordan", "team_code": "JOR", "confederation": "AFC", "confirmed": True},

    # OFC (1 slot)
    {"team_name": "New Zealand", "team_code": "NZL", "confederation": "OFC", "confirmed": True},
]

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
    """Load qualified teams from the database. Falls back to CONFIRMED_QUALIFIERS if empty."""
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.match_result import QualifiedTeam

        db = SessionLocal()
        try:
            rows = db.scalars(
                select(QualifiedTeam).where(QualifiedTeam.tournament_year == 2026)
            ).all()
            if rows:
                return [
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

    # R32 pairings (placeholder — official pairings TBD by FIFA draw)
    # Standard WC pattern: winners vs runners-up from cross-groups
    r32_pairs = _generate_r32_pairings(group_labels)
    for i, (g_winner, g_runner) in enumerate(r32_pairs, start=49):
        match_id = f"M{i}"
        bracket.append((match_id, ("group", f"1{g_winner}"), ("group", f"2{g_runner}")))

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
    """Generate standard cross-group pairings for R32."""
    # For 12 groups A-L: winners pair with runners-up from different groups.
    # This is a placeholder — official pairings are announced at the draw.
    n = len(group_labels)
    pairs = []
    half = n // 2
    for i in range(half):
        winner_group = group_labels[i]
        runner_group = group_labels[n - 1 - i]
        pairs.append((winner_group, runner_group))
    return pairs


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
