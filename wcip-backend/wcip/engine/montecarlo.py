"""Monte Carlo tournament engine.

Runs the tournament engine N times in parallel and aggregates per-team
probabilities of reaching each stage, with Wilson confidence intervals and
run-to-run variance.
"""
from __future__ import annotations

import math
import logging
import os
import secrets
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from .match import MatchSimulator
from .scoreline import ScorelineModel
from .tournament import TournamentEngine

logger = logging.getLogger(__name__)

# Representative finishing position for each elimination round (averaged ties).
_FINISH_POSITION = {
    "champion": 1.0,
    "final": 2.0,      # lost the final
    "third": 3.0,
    "fourth": 4.0,
    "semi": 3.5,       # fallback for older tournament results
    "quarter": 6.5,    # 5th-8th
    "r16": 12.5,       # 9th-16th
    "group": 24.5,     # 17th-32nd
}


@dataclass
class TeamProbabilities:
    team: str
    champion: float
    final: float
    semi: float
    quarter: float
    round_of_16: float
    round_of_32: float
    expected_finish: float
    champion_ci_low: float
    champion_ci_high: float


def _wilson_interval(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return 0.0, 0.0
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def generate_seed() -> int:
    """Return a system-entropy seed suitable for reproducible replay metadata."""

    return secrets.randbits(63)


def _run_chunk(args) -> dict:
    """Worker: run ``n_runs`` tournaments and tally stage reaches per team."""
    n_runs, seed, teams, groups, bracket, model_kwargs, elo_overrides = args
    rng = np.random.default_rng(seed)
    sim = MatchSimulator(model=ScorelineModel(**model_kwargs), rng=rng)
    engine = TournamentEngine(teams, groups, bracket, simulator=sim,
                              elo_overrides=elo_overrides)

    champ = defaultdict(int)
    final = defaultdict(int)
    semi = defaultdict(int)
    quarter = defaultdict(int)
    r16 = defaultdict(int)
    r32 = defaultdict(int)
    finish_sum = defaultdict(float)
    champ_per_team_runs = defaultdict(list)  # for variance across this chunk

    all_teams = list(teams.keys())

    for _ in range(n_runs):
        res = engine.simulate()
        reached_r16 = set(res.round_of_16)
        reached_r32 = set(getattr(res, "round_of_32", []))
        reached_qf = set(res.quarter_finalists)
        reached_sf = set(res.semi_finalists)
        finalists = {res.champion, res.runner_up}
        third_place = getattr(res, "third_place", None)
        fourth_place = getattr(res, "fourth_place", None)

        for t in all_teams:
            if t == res.champion:
                pos = "champion"
            elif t == res.runner_up:
                pos = "final"
            elif third_place and t == third_place:
                pos = "third"
            elif fourth_place and t == fourth_place:
                pos = "fourth"
            elif t in reached_sf:
                pos = "semi"
            elif t in reached_qf:
                pos = "quarter"
            elif t in reached_r16:
                pos = "r16"
            else:
                pos = "group"
            finish_sum[t] += _FINISH_POSITION[pos]

        for t in reached_r16:
            r16[t] += 1
        for t in reached_r32:
            r32[t] += 1
        for t in reached_qf:
            quarter[t] += 1
        for t in reached_sf:
            semi[t] += 1
        for t in finalists:
            final[t] += 1
        champ[res.champion] += 1

    return {
        "n": n_runs,
        "champ": dict(champ),
        "final": dict(final),
        "semi": dict(semi),
        "quarter": dict(quarter),
        "r16": dict(r16),
        "r32": dict(r32),
        "finish_sum": dict(finish_sum),
    }


class MonteCarloEngine:
    def __init__(
        self,
        teams: Dict[str, object],
        groups: Dict[str, List[str]],
        bracket,
        model: Optional[ScorelineModel] = None,
        elo_overrides: Optional[Dict[str, float]] = None,
    ):
        self.teams = teams
        self.groups = groups
        self.bracket = bracket
        self.model = model or ScorelineModel()
        self.elo_overrides = elo_overrides

    def run(self, n_runs: int = 10000, workers: Optional[int] = None,
            seed: int | None = None) -> Dict[str, TeamProbabilities]:
        seed = generate_seed() if seed is None else int(seed)
        workers = workers or min(os.cpu_count() or 1, 8)
        # Split runs across workers.
        base = n_runs // workers
        rem = n_runs % workers
        chunks = [base + (1 if i < rem else 0) for i in range(workers)]
        chunks = [c for c in chunks if c > 0]

        model_kwargs = {
            "base_goals": self.model.base_goals,
            "elo_to_goals": self.model.elo_to_goals,
            "home_advantage_goals": self.model.home_advantage_goals,
        }
        seed_seq = np.random.SeedSequence(seed)
        child_seeds = seed_seq.spawn(len(chunks))
        args = [
            (c, child_seeds[i], self.teams, self.groups, self.bracket,
             model_kwargs, self.elo_overrides)
            for i, c in enumerate(chunks)
        ]

        if workers == 1 or len(chunks) == 1:
            partials = [_run_chunk(a) for a in args]
        else:
            try:
                with ProcessPoolExecutor(max_workers=workers) as ex:
                    partials = list(ex.map(_run_chunk, args))
            except (PermissionError, NotImplementedError, OSError) as exc:
                logger.warning(
                    "Multiprocess Monte Carlo unavailable (%s); falling back to one worker",
                    exc,
                )
                partials = [_run_chunk((
                    n_runs,
                    np.random.SeedSequence(seed),
                    self.teams,
                    self.groups,
                    self.bracket,
                    model_kwargs,
                    self.elo_overrides,
                ))]

        return self._aggregate(partials, n_runs)

    def _aggregate(self, partials: List[dict], n_runs: int) -> Dict[str, TeamProbabilities]:
        champ = defaultdict(int)
        final = defaultdict(int)
        semi = defaultdict(int)
        quarter = defaultdict(int)
        r16 = defaultdict(int)
        r32 = defaultdict(int)
        finish_sum = defaultdict(float)
        for p in partials:
            for d, key in ((champ, "champ"), (final, "final"), (semi, "semi"),
                           (quarter, "quarter"), (r16, "r16"), (r32, "r32")):
                for t, v in p[key].items():
                    d[t] += v
            for t, v in p["finish_sum"].items():
                finish_sum[t] += v

        out: Dict[str, TeamProbabilities] = {}
        for t in self.teams:
            c = champ.get(t, 0)
            ci_low, ci_high = _wilson_interval(c, n_runs)
            out[t] = TeamProbabilities(
                team=t,
                champion=c / n_runs,
                final=final.get(t, 0) / n_runs,
                semi=semi.get(t, 0) / n_runs,
                quarter=quarter.get(t, 0) / n_runs,
                round_of_16=r16.get(t, 0) / n_runs,
                round_of_32=r32.get(t, 0) / n_runs,
                expected_finish=finish_sum.get(t, 0.0) / n_runs,
                champion_ci_low=ci_low,
                champion_ci_high=ci_high,
            )
        return dict(sorted(out.items(), key=lambda kv: kv[1].champion, reverse=True))
