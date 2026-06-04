"""Explainable-AI layer.

The production system would attach SHAP / permutation importance to the trained
ensemble. For the transparent statistical core we decompose the prediction into
the factors that actually drive it (Elo gap, expected-goal supremacy, form,
availability) and rank them, then render human-readable text.

This keeps explanations faithful to the model rather than post-hoc storytelling.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .scoreline import ScorelineModel, TeamMatchProfile


@dataclass
class Factor:
    name: str
    detail: str
    impact: float  # positive favours team A, negative favours team B


@dataclass
class Explanation:
    favoured: str
    win_probability: float
    factors: List[Factor]
    summary: str


def explain_match(
    team_a: TeamMatchProfile,
    team_b: TeamMatchProfile,
    model: ScorelineModel | None = None,
) -> Explanation:
    model = model or ScorelineModel()
    probs = model.outcome_probabilities(team_a, team_b)
    xg = {
        "a": model.expected_goals(team_a, team_b, is_home=True),
        "b": model.expected_goals(team_b, team_a, is_home=False),
    }

    factors: List[Factor] = []

    elo_gap = team_a.elo - team_b.elo
    factors.append(Factor(
        "Elo rating",
        f"{team_a.name} {team_a.elo:.0f} vs {team_b.name} {team_b.elo:.0f} "
        f"({elo_gap:+.0f})",
        elo_gap / 100.0,
    ))

    xg_gap = xg["a"] - xg["b"]
    factors.append(Factor(
        "Expected-goal supremacy",
        f"{xg['a']:.2f} xG vs {xg['b']:.2f} xG ({xg_gap:+.2f})",
        xg_gap,
    ))

    form_gap = team_a.attack - team_b.attack
    if abs(form_gap) > 1e-9:
        factors.append(Factor(
            "Recent form",
            f"attack multipliers {team_a.attack:.2f} vs {team_b.attack:.2f}",
            form_gap * 2.0,
        ))

    avail_gap = team_a.injury - team_b.injury
    if abs(avail_gap) > 1e-9:
        factors.append(Factor(
            "Squad availability",
            f"availability {team_a.injury:.2f} vs {team_b.injury:.2f} "
            "(injuries/suspensions)",
            avail_gap * 3.0,
        ))

    morale_gap = team_a.morale - team_b.morale
    if abs(morale_gap) > 1e-9:
        factors.append(Factor(
            "Morale",
            f"{team_a.morale:.2f} vs {team_b.morale:.2f}",
            morale_gap * 1.5,
        ))

    factors.sort(key=lambda f: abs(f.impact), reverse=True)

    favoured = team_a.name if probs["home_win"] >= probs["away_win"] else team_b.name
    win_prob = max(probs["home_win"], probs["away_win"])

    positives = [f for f in factors if f.impact > 0][:3]
    drivers = positives if favoured == team_a.name else \
        [f for f in factors if f.impact < 0][:3]
    if not drivers:
        drivers = factors[:2]

    reasons = "; ".join(f.detail for f in drivers)
    summary = (
        f"{favoured} is favoured ({win_prob*100:.1f}% to win, "
        f"draw {probs['draw']*100:.1f}%). Key drivers: {reasons}."
    )

    return Explanation(
        favoured=favoured,
        win_probability=win_prob,
        factors=factors,
        summary=summary,
    )
