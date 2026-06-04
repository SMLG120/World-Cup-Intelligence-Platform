"""Poisson scoreline model.

Turns two teams' Elo ratings (plus optional form/attack/defence adjustments,
injury/morale/fatigue modifiers) into:

  * expected goals (lambda) for each side
  * a full scoreline probability matrix (independent Poisson)
  * win / draw / win probabilities derived from that matrix

This is the bridge between the abstract Elo number and a concrete, simulatable
match. Independent-Poisson is the standard, well-behaved baseline for football
scorelines; the attack/defence and modifier hooks let richer features feed in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import numpy as np
from scipy.stats import poisson

# Average goals scored by one side in a competitive international match.
BASE_GOALS = 1.35
# A 100-point Elo edge translates to roughly this goal supremacy.
ELO_TO_GOALS = 0.45 / 100.0
MAX_GOALS = 10  # truncation point for the scoreline matrix


@dataclass
class TeamMatchProfile:
    """Per-match modifiers for a team. All multipliers default to neutral 1.0."""

    name: str
    elo: float
    attack: float = 1.0   # >1 = sharper attack (form, xG overperformance)
    defence: float = 1.0  # >1 = leakier defence (so it raises opponent's lambda)
    injury: float = 1.0   # 0..1 availability of key players (1 = full strength)
    morale: float = 1.0   # 0.9..1.1 typical
    fatigue: float = 1.0  # 0..1 (1 = fresh)
    chemistry: float = 1.0
    coaching: float = 1.0

    def strength_multiplier(self) -> float:
        """Combined non-attack multiplier applied to this team's own lambda."""
        return (
            self.attack
            * self.injury
            * self.morale
            * self.fatigue
            * self.chemistry
            * self.coaching
        )


@dataclass
class ScorelineModel:
    base_goals: float = BASE_GOALS
    elo_to_goals: float = ELO_TO_GOALS
    home_advantage_goals: float = 0.0  # set >0 only for a true host match

    def expected_goals(
        self, team: TeamMatchProfile, opp: TeamMatchProfile, is_home: bool = False
    ) -> float:
        """Expected goals for ``team`` against ``opp``."""
        supremacy = (team.elo - opp.elo) * self.elo_to_goals
        lam = self.base_goals + supremacy / 2.0
        if is_home:
            lam += self.home_advantage_goals / 2.0
        # Own attacking quality x opponent's defensive leakiness.
        lam *= team.strength_multiplier() * opp.defence
        return max(0.12, lam)

    def scoreline_matrix(
        self, home: TeamMatchProfile, away: TeamMatchProfile
    ) -> np.ndarray:
        """Joint probability matrix P[i, j] = P(home scores i, away scores j)."""
        lam_h = self.expected_goals(home, away, is_home=True)
        lam_a = self.expected_goals(away, home, is_home=False)
        ks = np.arange(0, MAX_GOALS + 1)
        p_home = poisson.pmf(ks, lam_h)
        p_away = poisson.pmf(ks, lam_a)
        matrix = np.outer(p_home, p_away)
        return matrix / matrix.sum()  # renormalise after truncation

    def outcome_probabilities(
        self, home: TeamMatchProfile, away: TeamMatchProfile
    ) -> Dict[str, float]:
        """Return home-win / draw / away-win probabilities."""
        m = self.scoreline_matrix(home, away)
        draw = float(np.trace(m))
        home_win = float(np.tril(m, -1).sum())  # home goals (row) > away (col)
        away_win = float(np.triu(m, 1).sum())
        return {"home_win": home_win, "draw": draw, "away_win": away_win}

    def expected_goal_pair(
        self, home: TeamMatchProfile, away: TeamMatchProfile
    ) -> Dict[str, float]:
        return {
            "home_xg": self.expected_goals(home, away, is_home=True),
            "away_xg": self.expected_goals(away, home, is_home=False),
        }
