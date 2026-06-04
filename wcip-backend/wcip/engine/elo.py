"""Elo rating engine.

Implements the World-Football-Elo style rating system used by eloratings.net:
a base K-factor scaled by match importance and a goal-difference multiplier.

References for the math (all public):
  - Expected score:        E_A = 1 / (1 + 10 ** ((R_B - R_A) / 400))
  - Update:                R'  = R + K * G * (S - E)
  - Goal-diff multiplier G:  1            for |GD| <= 1
                             1.5          for |GD| == 2
                             (11 + |GD|)/8 for |GD| >= 3
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# Match-importance weights (the K-factor base before goal multiplier).
# Higher importance -> ratings move faster.
IMPORTANCE: Dict[str, float] = {
    "friendly": 10.0,
    "qualifier": 25.0,
    "continental": 40.0,
    "confederations": 50.0,
    "world_cup_group": 55.0,
    "world_cup_knockout": 60.0,
    "world_cup_final": 60.0,
}


def expected_score(rating_a: float, rating_b: float) -> float:
    """Probability-like expected score for A against B (0..1)."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def goal_difference_multiplier(goal_diff: int) -> float:
    """Goal-difference multiplier G from the World Football Elo formula."""
    g = abs(goal_diff)
    if g <= 1:
        return 1.0
    if g == 2:
        return 1.5
    return (11.0 + g) / 8.0


@dataclass
class EloEngine:
    """Stateful Elo engine that tracks ratings and full update history."""

    ratings: Dict[str, float] = field(default_factory=dict)
    default_rating: float = 1500.0
    history: List[dict] = field(default_factory=list)

    def get(self, team: str) -> float:
        return self.ratings.get(team, self.default_rating)

    def seed(self, ratings: Dict[str, float]) -> None:
        """Seed initial ratings (e.g. a published snapshot)."""
        self.ratings.update(ratings)

    def update_match(
        self,
        home: str,
        away: str,
        home_goals: int,
        away_goals: int,
        importance: str = "world_cup_group",
        neutral: bool = True,
        home_advantage: float = 100.0,
    ) -> Tuple[float, float]:
        """Apply one match result and return the new (home, away) ratings.

        ``home_advantage`` is added to the home rating only for the expectation
        calculation (set neutral=True at a World Cup to disable it).
        """
        r_home = self.get(home)
        r_away = self.get(away)
        adv = 0.0 if neutral else home_advantage

        exp_home = expected_score(r_home + adv, r_away)
        exp_away = 1.0 - exp_home

        if home_goals > away_goals:
            score_home, score_away = 1.0, 0.0
        elif home_goals < away_goals:
            score_home, score_away = 0.0, 1.0
        else:
            score_home = score_away = 0.5

        k = IMPORTANCE.get(importance, 30.0)
        g = goal_difference_multiplier(home_goals - away_goals)

        delta_home = k * g * (score_home - exp_home)
        delta_away = k * g * (score_away - exp_away)

        new_home = r_home + delta_home
        new_away = r_away + delta_away
        self.ratings[home] = new_home
        self.ratings[away] = new_away

        self.history.append(
            {
                "home": home,
                "away": away,
                "home_goals": home_goals,
                "away_goals": away_goals,
                "importance": importance,
                "home_before": r_home,
                "away_before": r_away,
                "home_after": new_home,
                "away_after": new_away,
                "home_delta": delta_home,
                "away_delta": delta_away,
            }
        )
        return new_home, new_away

    def recalculate(self, matches: List[dict]) -> None:
        """Historical recalculation: replay a chronological list of matches.

        Each match dict needs: home, away, home_goals, away_goals, and
        optionally importance / neutral.
        """
        self.history.clear()
        for m in matches:
            self.update_match(
                m["home"],
                m["away"],
                int(m["home_goals"]),
                int(m["away_goals"]),
                importance=m.get("importance", "world_cup_group"),
                neutral=m.get("neutral", True),
            )

    def trend(self, team: str) -> List[float]:
        """Rating-after-each-match trend for a single team."""
        out: List[float] = []
        for h in self.history:
            if h["home"] == team:
                out.append(h["home_after"])
            elif h["away"] == team:
                out.append(h["away_after"])
        return out
