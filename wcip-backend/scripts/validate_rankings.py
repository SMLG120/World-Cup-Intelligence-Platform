#!/usr/bin/env python3
"""Validate Elo ratings and FIFA rankings for WC2026 teams.

Run from `wcip-backend`:
    python -m scripts.validate_rankings
    python scripts/validate_rankings.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.db.base import SessionLocal
from app.db.init_db import init_db
from app.models.ranking import FifaRankingSnapshot, TeamRanking
from app.models.team import EloRatingSnapshot, EloSourceLog, Team, TeamEloRating
from wcip.data.wc2026 import CONFIRMED_QUALIFIERS


def ok(label: str, detail: str = "") -> tuple[bool, str, str]:
    return True, label, detail


def fail(label: str, detail: str = "") -> tuple[bool, str, str]:
    return False, label, detail


def warn(label: str, detail: str = "") -> tuple[bool, str, str]:
    return None, label, detail  # type: ignore[return-value]


def main() -> int:
    init_db()
    expected_teams = {team["team_name"] for team in CONFIRMED_QUALIFIERS}
    checks: list[tuple[bool | None, str, str]] = []

    db = SessionLocal()
    try:
        teams_in_db = db.scalars(select(Team)).all()
        team_by_name = {t.name: t for t in teams_in_db}

        # ══════════════════════════════════════════════════════════════════
        # ELO RATINGS
        # ══════════════════════════════════════════════════════════════════

        # 1. Current Elo snapshot exists
        elo_snapshot = db.scalar(
            select(EloRatingSnapshot)
            .where(EloRatingSnapshot.is_current.is_(True))
            .order_by(EloRatingSnapshot.rating_date.desc(), EloRatingSnapshot.id.desc())
            .limit(1)
        )
        checks.append(
            ok(
                "Current Elo snapshot exists",
                f"snapshot_id={elo_snapshot.snapshot_id!r} date={elo_snapshot.rating_date} source={elo_snapshot.source_url[:60]!r}",
            )
            if elo_snapshot
            else fail("Current Elo snapshot exists", "No current Elo snapshot — run: python -m etl.elo or POST /admin/data/refresh-elo")
        )

        # 2. Elo snapshot has sufficient coverage
        if elo_snapshot:
            elo_entries = db.scalars(
                select(TeamEloRating).where(TeamEloRating.snapshot_id == elo_snapshot.id)
            ).all()
            elo_by_name = {e.team_name: e for e in elo_entries}
            missing_elo = sorted(expected_teams - set(elo_by_name))
            checks.append(
                ok("Elo snapshot covers all WC2026 teams", f"{len(elo_entries)} entries")
                if not missing_elo
                else warn(
                    "Elo snapshot covers all WC2026 teams",
                    f"{len(missing_elo)} teams missing from snapshot: {missing_elo[:10]}",
                )
            )

            # 3. Elo values are within plausible range (800–2500)
            out_of_range = [
                f"{e.team_name}={e.rating:.0f}"
                for e in elo_entries
                if not (800 <= e.rating <= 2500)
            ]
            checks.append(
                fail("Elo ratings are in plausible range (800–2500)", f"{out_of_range}")
                if out_of_range
                else ok("Elo ratings are in plausible range (800–2500)")
            )

            # 4. No NaN or infinite Elo values
            bad_elo = [
                f"{e.team_name}={e.rating}"
                for e in elo_entries
                if not math.isfinite(e.rating)
            ]
            checks.append(
                fail("No NaN/Inf Elo values", f"{bad_elo}")
                if bad_elo
                else ok("No NaN/Inf Elo values")
            )

            # 5. Rank 1 exists and is unique
            rank_ones = [e for e in elo_entries if e.rank == 1]
            checks.append(
                ok("Exactly one Elo rank-1 team", f"{rank_ones[0].team_name}")
                if len(rank_ones) == 1
                else warn("Exactly one Elo rank-1 team", f"found {len(rank_ones)} rank-1 entries")
            )

            # 6. teams.elo column in sync with snapshot
            out_of_sync = []
            for team in teams_in_db:
                snap_entry = elo_by_name.get(team.name)
                if snap_entry and abs(float(team.elo) - float(snap_entry.rating)) > 5:
                    out_of_sync.append(f"{team.name}: teams.elo={team.elo:.0f} snapshot={snap_entry.rating:.0f}")
            checks.append(
                warn("teams.elo is in sync with current snapshot (within 5 pts)", f"{len(out_of_sync)} out of sync: {out_of_sync[:5]}")
                if out_of_sync
                else ok("teams.elo is in sync with current snapshot (within 5 pts)")
            )
        else:
            # If no snapshot, check fallback values on Team
            no_elo_teams = [t.name for t in teams_in_db if not t.elo or t.elo <= 0]
            checks.append(
                fail("Teams have fallback Elo values", f"{no_elo_teams}")
                if no_elo_teams
                else ok("Teams have fallback Elo values (from embedded snapshot)", f"{len(teams_in_db)} teams")
            )

        # 7. Elo snapshot history count
        snapshot_count = db.scalar(select(func.count()).select_from(EloRatingSnapshot))
        checks.append(
            ok("Elo snapshot history exists", f"{snapshot_count} snapshots")
            if snapshot_count and snapshot_count > 0
            else warn("Elo snapshot history", "No snapshots stored yet")
        )

        # 8. Latest Elo source log status
        last_elo_log = db.scalar(
            select(EloSourceLog).order_by(EloSourceLog.started_at.desc()).limit(1)
        )
        if last_elo_log:
            checks.append(
                ok("Last Elo refresh succeeded", f"status={last_elo_log.status} at {last_elo_log.started_at}")
                if last_elo_log.status == "success"
                else warn("Last Elo refresh status", f"status={last_elo_log.status} — check logs")
            )
        else:
            checks.append(warn("Elo source log", "No refresh logs found"))

        # ══════════════════════════════════════════════════════════════════
        # FIFA RANKINGS
        # ══════════════════════════════════════════════════════════════════

        # 9. Current FIFA ranking snapshot
        fifa_snapshot = db.scalar(
            select(FifaRankingSnapshot)
            .where(FifaRankingSnapshot.is_current.is_(True))
            .order_by(FifaRankingSnapshot.ranking_date.desc(), FifaRankingSnapshot.id.desc())
            .limit(1)
        )
        checks.append(
            ok(
                "Current FIFA ranking snapshot exists",
                f"id={fifa_snapshot.ranking_id!r} date={fifa_snapshot.ranking_date}",
            )
            if fifa_snapshot
            else fail(
                "Current FIFA ranking snapshot exists",
                "No FIFA snapshot — run: POST /admin/data/refresh-fifa-rankings",
            )
        )

        # 10. FIFA ranking coverage of WC2026 teams
        if fifa_snapshot:
            team_rankings = db.scalars(
                select(TeamRanking).where(TeamRanking.snapshot_id == fifa_snapshot.id)
            ).all()
            ranked_names = {r.team_name for r in team_rankings}
            missing_ranked = sorted(expected_teams - ranked_names)
            checks.append(
                ok("FIFA rankings cover all WC2026 teams", f"{len(team_rankings)} entries")
                if not missing_ranked
                else warn(
                    "FIFA rankings cover all WC2026 teams",
                    f"{len(missing_ranked)} missing: {missing_ranked[:10]}",
                )
            )

            # 11. FIFA rank values are positive integers
            bad_ranks = [
                f"{r.team_name}={r.rank}"
                for r in team_rankings
                if r.rank is None or r.rank <= 0
            ]
            checks.append(
                fail("All FIFA ranks are positive integers", f"{bad_ranks[:10]}")
                if bad_ranks
                else ok("All FIFA ranks are positive integers")
            )

            # 12. FIFA rank-1 team
            rank_1 = [r for r in team_rankings if r.rank == 1]
            checks.append(
                ok("FIFA rank-1 team exists in snapshot", f"{rank_1[0].team_name}")
                if len(rank_1) == 1
                else warn("FIFA rank-1 team", f"found {len(rank_1)} rank-1 entries")
            )

            # 13. teams.fifa_rank column has been updated
            zero_rank_teams = [t.name for t in teams_in_db if t.fifa_rank <= 0]
            checks.append(
                ok("teams.fifa_rank column is populated")
                if not zero_rank_teams
                else warn("teams.fifa_rank populated", f"{len(zero_rank_teams)} teams have rank=0: {zero_rank_teams[:5]}")
            )

        # ══════════════════════════════════════════════════════════════════
        # CROSS-CHECKS
        # ══════════════════════════════════════════════════════════════════

        # 14. Statistical predictions use latest Elo (smoke test)
        try:
            from app.services.prediction import predict_match

            result = predict_match("France", "Brazil", {}, {})
            probs = result["probabilities"]
            total = sum(float(v) for v in probs.values())
            all_finite = all(math.isfinite(float(v)) for v in probs.values())
            all_bounded = all(0 <= float(v) <= 1 for v in probs.values())
            checks.append(
                ok(
                    "Prediction smoke test (France vs Brazil) passes",
                    f"sum={total:.6f} finite={all_finite} bounded={all_bounded}",
                )
                if all_finite and all_bounded and abs(total - 1.0) < 1e-4
                else fail("Prediction smoke test (France vs Brazil)", f"sum={total:.6f} finite={all_finite} bounded={all_bounded}")
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(fail("Prediction smoke test", str(exc)))

        # 15. Elo-based ordering sanity (Argentina, France, England should all be top-20)
        if elo_snapshot and elo_entries:
            top20_elo = sorted(elo_entries, key=lambda e: e.rating, reverse=True)[:20]
            top20_names = {e.team_name for e in top20_elo}
            expected_top = {"Argentina", "France", "England", "Spain", "Brazil"}
            checks.append(
                ok("Top football nations appear in Elo top 20", f"top20={[e.team_name for e in top20_elo[:5]]}")
                if len(expected_top & top20_names) >= 3
                else warn(
                    "Top football nations in Elo top 20",
                    f"only {expected_top & top20_names} of {expected_top} found in top 20",
                )
            )

    finally:
        db.close()

    # ── Report ────────────────────────────────────────────────────────────────
    print("Rankings & Elo Validation Report")
    print("=" * 55)
    failures = 0
    warnings = 0
    for passed, label, detail in checks:
        if passed is True:
            marker = "PASS"
        elif passed is False:
            marker = "FAIL"
            failures += 1
        else:
            marker = "WARN"
            warnings += 1
        print(f"[{marker}] {label}")
        if detail:
            print(f"       {detail}")

    print("=" * 55)
    total = len(checks)
    passed_count = sum(1 for p, _, _ in checks if p is True)
    print(
        f"Result: {passed_count}/{total} passed"
        + (f" | {warnings} warning(s)" if warnings else "")
        + (f" | {failures} failure(s)" if failures else "")
    )
    print("Status:", "ALL CHECKS PASSED" if failures == 0 else "FAILURES DETECTED — see above")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
