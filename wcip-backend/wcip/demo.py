"""Runnable demo for the simulation core.

Usage:
    python -m wcip.demo                 # 10k Monte Carlo run + a sample match
    python -m wcip.demo --runs 50000    # heavier run
    python -m wcip.demo --runs 2000 --workers 4
"""
from __future__ import annotations

import argparse
import time

from .data.teams_2022 import BRACKET_2022, GROUPS_2022, build_teams
from .engine.explain import explain_match
from .engine.montecarlo import MonteCarloEngine
from .engine.scoreline import ScorelineModel, TeamMatchProfile


def sample_match(teams) -> None:
    model = ScorelineModel()
    fra = teams["France"]
    arg = teams["Argentina"]
    a = TeamMatchProfile(name=fra.name, elo=fra.elo)
    b = TeamMatchProfile(name=arg.name, elo=arg.elo)
    probs = model.outcome_probabilities(a, b)
    print("\n=== Sample match: France vs Argentina (neutral) ===")
    print(f"  France win : {probs['home_win']*100:5.1f}%")
    print(f"  Draw       : {probs['draw']*100:5.1f}%")
    print(f"  Argentina  : {probs['away_win']*100:5.1f}%")
    print("  Explanation:")
    print("   ", explain_match(a, b, model).summary)

    print("\n  Scenario — Argentina missing key players (availability 0.80):")
    b_injured = TeamMatchProfile(name=arg.name, elo=arg.elo, injury=0.80)
    p2 = model.outcome_probabilities(a, b_injured)
    print(f"    France win {p2['home_win']*100:5.1f}% (was {probs['home_win']*100:.1f}%)"
          f"  |  Argentina {p2['away_win']*100:5.1f}% (was {probs['away_win']*100:.1f}%)")


def monte_carlo(teams, runs: int, workers: int | None) -> None:
    engine = MonteCarloEngine(teams, GROUPS_2022, BRACKET_2022)
    print(f"\n=== Monte Carlo: {runs:,} tournament simulations ===")
    t0 = time.time()
    probs = engine.run(n_runs=runs, workers=workers)
    dt = time.time() - t0
    print(f"  completed in {dt:.2f}s "
          f"({runs/dt:,.0f} tournaments/sec)\n")
    print(f"  {'Team':<16}{'Champion':>10}{'95% CI':>16}{'Final':>8}"
          f"{'Semi':>8}{'E[finish]':>11}")
    print("  " + "-" * 69)
    for tp in list(probs.values())[:12]:
        ci = f"[{tp.champion_ci_low*100:4.1f},{tp.champion_ci_high*100:4.1f}]"
        print(f"  {tp.team:<16}{tp.champion*100:9.2f}%{ci:>16}"
              f"{tp.final*100:7.1f}%{tp.semi*100:7.1f}%{tp.expected_finish:10.1f}")
    total = sum(tp.champion for tp in probs.values())
    print(f"\n  (champion probabilities sum to {total*100:.1f}%)")


def main() -> None:
    ap = argparse.ArgumentParser(description="World Cup Intelligence — core demo")
    ap.add_argument("--runs", type=int, default=10000)
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args()

    teams = build_teams()
    sample_match(teams)
    monte_carlo(teams, args.runs, args.workers)


if __name__ == "__main__":
    main()
