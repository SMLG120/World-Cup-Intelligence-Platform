"""Single-match simulator.

Samples concrete scorelines from the :class:`ScorelineModel` and resolves
knockout matches that finish level via extra time and penalty shootouts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .elo import expected_score
from .scoreline import ScorelineModel, TeamMatchProfile

# Extra time = 30 of the regular 90 minutes -> scale expected goals by 1/3.
EXTRA_TIME_FACTOR = 30.0 / 90.0


@dataclass
class MatchResult:
    home: str
    away: str
    home_goals: int
    away_goals: int
    winner: Optional[str]          # None only for a group-stage draw
    decided_by: str                # "regulation" | "extra_time" | "penalties"
    home_xg: float
    away_xg: float

    def to_dict(self) -> dict:
        return {
            "home": self.home,
            "away": self.away,
            "homeGoals": self.home_goals,
            "awayGoals": self.away_goals,
            "winner": self.winner,
            "decidedBy": self.decided_by,
            "homeXg": round(self.home_xg, 3),
            "awayXg": round(self.away_xg, 3),
        }


class MatchSimulator:
    def __init__(self, model: Optional[ScorelineModel] = None, rng: Optional[np.random.Generator] = None):
        self.model = model or ScorelineModel()
        self.rng = rng or np.random.default_rng()

    def _sample_goals(self, lam: float) -> int:
        return int(self.rng.poisson(lam))

    def simulate(
        self,
        home: TeamMatchProfile,
        away: TeamMatchProfile,
        knockout: bool = False,
    ) -> MatchResult:
        xg = self.model.expected_goal_pair(home, away)
        hg = self._sample_goals(xg["home_xg"])
        ag = self._sample_goals(xg["away_xg"])
        decided_by = "regulation"

        if hg == ag and knockout:
            # Extra time.
            hg += self._sample_goals(xg["home_xg"] * EXTRA_TIME_FACTOR)
            ag += self._sample_goals(xg["away_xg"] * EXTRA_TIME_FACTOR)
            decided_by = "extra_time"
            if hg == ag:
                # Penalty shootout — weight slightly by Elo, mostly a coin flip.
                p_home = 0.5 + (expected_score(home.elo, away.elo) - 0.5) * 0.5
                if self.rng.random() < p_home:
                    winner = home.name
                else:
                    winner = away.name
                return MatchResult(
                    home.name, away.name, hg, ag, winner, "penalties",
                    xg["home_xg"], xg["away_xg"],
                )

        if hg > ag:
            winner: Optional[str] = home.name
        elif ag > hg:
            winner = away.name
        else:
            winner = None  # legitimate group-stage draw

        return MatchResult(
            home.name, away.name, hg, ag, winner, decided_by,
            xg["home_xg"], xg["away_xg"],
        )
