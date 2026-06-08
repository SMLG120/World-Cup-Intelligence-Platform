"""Tournament engine.

Runs a full World Cup from a group definition + bracket template:

  1. Group stage: round-robin, ranked by FIFA tie-breakers
     (points -> goal difference -> goals for -> head-to-head).
  2. Knockout: resolves the data-driven bracket, advancing winners.

Produces a complete, replayable tournament state.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .match import MatchResult, MatchSimulator
from .scoreline import TeamMatchProfile


@dataclass
class GroupRow:
    team: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    gf: int = 0
    ga: int = 0

    @property
    def points(self) -> int:
        return self.won * 3 + self.drawn

    @property
    def gd(self) -> int:
        return self.gf - self.ga


@dataclass
class TournamentResult:
    group_tables: Dict[str, List[GroupRow]]
    knockout: Dict[str, MatchResult]
    champion: str
    runner_up: str
    semi_finalists: List[str]
    quarter_finalists: List[str]
    round_of_16: List[str]


def _profile(team_obj, elo_lookup: Dict[str, float]) -> TeamMatchProfile:
    """Build a per-match profile from a Team object using current Elo."""
    return TeamMatchProfile(
        name=team_obj.name,
        elo=elo_lookup.get(team_obj.name, team_obj.elo),
        attack=team_obj.attack,
        defence=team_obj.defence,
        chemistry=team_obj.chemistry,
        coaching=team_obj.coach_quality,
    )


class TournamentEngine:
    def __init__(
        self,
        teams: Dict[str, object],
        groups: Dict[str, List[str]],
        bracket: List[Tuple[str, Tuple[str, str], Tuple[str, str]]],
        simulator: Optional[MatchSimulator] = None,
        elo_overrides: Optional[Dict[str, float]] = None,
    ):
        self.teams = teams
        self.groups = groups
        self.bracket = bracket
        self.sim = simulator or MatchSimulator()
        self.elo = elo_overrides or {name: t.elo for name, t in teams.items()}

    # ---- group stage -------------------------------------------------------
    def _play_group(self, group_teams: List[str]) -> List[GroupRow]:
        rows = {name: GroupRow(team=name) for name in group_teams}
        # Round-robin: every unordered pair once.
        for i in range(len(group_teams)):
            for j in range(i + 1, len(group_teams)):
                a, b = group_teams[i], group_teams[j]
                res = self.sim.simulate(
                    _profile(self.teams[a], self.elo),
                    _profile(self.teams[b], self.elo),
                    knockout=False,
                )
                self._record(rows[a], rows[b], res)
        return self._rank_group(rows)

    @staticmethod
    def _record(row_a: GroupRow, row_b: GroupRow, res: MatchResult) -> None:
        row_a.played += 1
        row_b.played += 1
        row_a.gf += res.home_goals
        row_a.ga += res.away_goals
        row_b.gf += res.away_goals
        row_b.ga += res.home_goals
        if res.winner == row_a.team:
            row_a.won += 1
            row_b.lost += 1
        elif res.winner == row_b.team:
            row_b.won += 1
            row_a.lost += 1
        else:
            row_a.drawn += 1
            row_b.drawn += 1

    @staticmethod
    def _rank_group(rows: Dict[str, GroupRow]) -> List[GroupRow]:
        return sorted(
            rows.values(),
            key=lambda r: (r.points, r.gd, r.gf),
            reverse=True,
        )

    # ---- knockout ----------------------------------------------------------
    def _resolve_slot(
        self,
        slot: Tuple[str, str],
        positions: Dict[str, str],
        winners: Dict[str, str],
    ) -> str:
        kind, ref = slot
        if kind == "group":
            return positions[ref]          # e.g. "1A" -> team name
        return winners[ref]                # e.g. "M49" -> winning team name

    def simulate(self) -> TournamentResult:
        # 1. Group stage.
        tables: Dict[str, List[GroupRow]] = {}
        positions: Dict[str, str] = {}
        third_place_rows: List[GroupRow] = []
        for label, group_teams in self.groups.items():
            ranked = self._play_group(group_teams)
            tables[label] = ranked
            positions[f"1{label}"] = ranked[0].team
            positions[f"2{label}"] = ranked[1].team
            if len(ranked) > 2:
                third_place_rows.append(ranked[2])

        best_thirds = sorted(
            third_place_rows,
            key=lambda r: (r.points, r.gd, r.gf),
            reverse=True,
        )
        for i, row in enumerate(best_thirds[:8], start=1):
            positions[f"B3_{i}"] = row.team

        # 2. Knockout.
        knockout: Dict[str, MatchResult] = {}
        winners: Dict[str, str] = {}
        for match_id, slot_a, slot_b in self.bracket:
            team_a = self._resolve_slot(slot_a, positions, winners)
            team_b = self._resolve_slot(slot_b, positions, winners)
            res = self.sim.simulate(
                _profile(self.teams[team_a], self.elo),
                _profile(self.teams[team_b], self.elo),
                knockout=True,
            )
            knockout[match_id] = res
            winners[match_id] = res.winner

        champion = winners["FINAL"]
        final_res = knockout["FINAL"]
        runner_up = final_res.away if final_res.winner == final_res.home else final_res.home
        semi_ids = self._previous_match_ids("FINAL")
        quarter_ids = self._previous_match_ids(*semi_ids)
        round_of_16_ids = self._previous_match_ids(*quarter_ids)

        sf = self._participants(knockout, semi_ids)
        qf = self._participants(knockout, quarter_ids)
        r16 = self._participants(knockout, round_of_16_ids)

        return TournamentResult(
            group_tables=tables,
            knockout=knockout,
            champion=champion,
            runner_up=runner_up,
            semi_finalists=sf,
            quarter_finalists=qf,
            round_of_16=r16,
        )

    def _previous_match_ids(self, *match_ids: str) -> List[str]:
        """Return match refs that feed the given downstream matches."""
        wanted = set(match_ids)
        previous: List[str] = []
        for match_id, slot_a, slot_b in self.bracket:
            if match_id not in wanted:
                continue
            for kind, ref in (slot_a, slot_b):
                if kind == "match":
                    previous.append(ref)
        return previous

    @staticmethod
    def _participants(knockout: Dict[str, MatchResult], match_ids: List[str]) -> List[str]:
        participants: List[str] = []
        for match_id in match_ids:
            if match_id in knockout:
                participants.extend([knockout[match_id].home, knockout[match_id].away])
        return participants
