"""Real-world seed data for the 2022 FIFA World Cup.

The 32 nations, their official groups, the official knockout bracket template,
and an approximate published Elo snapshot (eloratings.net, Nov 2022) used as
the starting point. The Elo engine recomputes from here as matches are played.

This is a concrete, runnable example. The structures (groups, bracket) are
data-driven so a different tournament (e.g. the 48-team 2026 format) can be
plugged in by supplying new group/bracket definitions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class Team:
    name: str
    code: str          # FIFA 3-letter code
    confederation: str
    elo: float
    fifa_rank: int = 0
    # Optional richer features (default neutral). Populated by ETL in a full build.
    attack: float = 1.0
    defence: float = 1.0
    chemistry: float = 1.0
    coach_quality: float = 1.0


# (name, code, confederation, seed_elo, fifa_rank)
_TEAMS: List[Tuple[str, str, str, float, int]] = [
    ("Qatar", "QAT", "AFC", 1680, 50),
    ("Ecuador", "ECU", "CONMEBOL", 1764, 44),
    ("Senegal", "SEN", "CAF", 1687, 18),
    ("Netherlands", "NED", "UEFA", 2040, 8),
    ("England", "ENG", "UEFA", 1925, 5),
    ("Iran", "IRN", "AFC", 1689, 20),
    ("United States", "USA", "CONCACAF", 1798, 16),
    ("Wales", "WAL", "UEFA", 1790, 19),
    ("Argentina", "ARG", "CONMEBOL", 2138, 3),
    ("Saudi Arabia", "KSA", "AFC", 1612, 51),
    ("Mexico", "MEX", "CONCACAF", 1820, 13),
    ("Poland", "POL", "UEFA", 1745, 26),
    ("France", "FRA", "UEFA", 2005, 4),
    ("Australia", "AUS", "AFC", 1714, 38),
    ("Denmark", "DEN", "UEFA", 1942, 10),
    ("Tunisia", "TUN", "CAF", 1664, 30),
    ("Spain", "ESP", "UEFA", 2045, 7),
    ("Costa Rica", "CRC", "CONCACAF", 1655, 31),
    ("Germany", "GER", "UEFA", 1958, 11),
    ("Japan", "JPN", "AFC", 1779, 24),
    ("Belgium", "BEL", "UEFA", 1989, 2),
    ("Canada", "CAN", "CONCACAF", 1750, 41),
    ("Morocco", "MAR", "CAF", 1736, 22),
    ("Croatia", "CRO", "UEFA", 1922, 12),
    ("Brazil", "BRA", "CONMEBOL", 2169, 1),
    ("Serbia", "SRB", "UEFA", 1804, 21),
    ("Switzerland", "SUI", "UEFA", 1887, 15),
    ("Cameroon", "CMR", "CAF", 1610, 43),
    ("Portugal", "POR", "UEFA", 2004, 9),
    ("Ghana", "GHA", "CAF", 1567, 61),
    ("Uruguay", "URU", "CONMEBOL", 1900, 14),
    ("South Korea", "KOR", "AFC", 1745, 28),
]

# Official 2022 group assignments (group label -> ordered list of team names).
GROUPS_2022: Dict[str, List[str]] = {
    "A": ["Qatar", "Ecuador", "Senegal", "Netherlands"],
    "B": ["England", "Iran", "United States", "Wales"],
    "C": ["Argentina", "Saudi Arabia", "Mexico", "Poland"],
    "D": ["France", "Australia", "Denmark", "Tunisia"],
    "E": ["Spain", "Costa Rica", "Germany", "Japan"],
    "F": ["Belgium", "Canada", "Morocco", "Croatia"],
    "G": ["Brazil", "Serbia", "Switzerland", "Cameroon"],
    "H": ["Portugal", "Ghana", "Uruguay", "South Korea"],
}

# Official 2022 knockout bracket template.
# A slot is ("group", "1A") for a group winner/runner-up, or ("match", "M49")
# for a prior match's winner. Match ids are processed in declaration order.
BRACKET_2022: List[Tuple[str, Tuple[str, str], Tuple[str, str]]] = [
    ("M49", ("group", "1A"), ("group", "2B")),
    ("M50", ("group", "1C"), ("group", "2D")),
    ("M51", ("group", "1D"), ("group", "2C")),
    ("M52", ("group", "1B"), ("group", "2A")),
    ("M53", ("group", "1E"), ("group", "2F")),
    ("M54", ("group", "1G"), ("group", "2H")),
    ("M55", ("group", "1F"), ("group", "2E")),
    ("M56", ("group", "1H"), ("group", "2G")),
    ("M57", ("match", "M53"), ("match", "M54")),
    ("M58", ("match", "M49"), ("match", "M50")),
    ("M59", ("match", "M55"), ("match", "M56")),
    ("M60", ("match", "M51"), ("match", "M52")),
    ("M61", ("match", "M57"), ("match", "M58")),
    ("M62", ("match", "M59"), ("match", "M60")),
    ("FINAL", ("match", "M61"), ("match", "M62")),
]

# Which match ids belong to which round (used for probability tallies).
ROUND_OF_16 = {"M49", "M50", "M51", "M52", "M53", "M54", "M55", "M56"}
QUARTER_FINALS = {"M57", "M58", "M59", "M60"}
SEMI_FINALS = {"M61", "M62"}
FINAL = {"FINAL"}


def build_teams() -> Dict[str, Team]:
    return {
        name: Team(name=name, code=code, confederation=conf, elo=elo, fifa_rank=rank)
        for (name, code, conf, elo, rank) in _TEAMS
    }
