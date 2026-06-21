#!/usr/bin/env python3
"""Validate World Cup 2026 match results, group standings, and data integrity.

Run from `wcip-backend`:
    python -m scripts.validate_world_cup_data
    python scripts/validate_world_cup_data.py
"""
from __future__ import annotations

import math
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.db.base import SessionLocal
from app.db.init_db import init_db
from app.models.match_result import MatchResult, QualifiedTeam
from app.models.team import Team
from wcip.data.wc2026 import CONFIRMED_QUALIFIERS


def ok(label: str, detail: str = "") -> tuple[bool, str, str]:
    return True, label, detail


def fail(label: str, detail: str = "") -> tuple[bool, str, str]:
    return False, label, detail


def warn(label: str, detail: str = "") -> tuple[bool, str, str]:
    """Non-fatal check — shown as WARN, does not count as failure."""
    return None, label, detail  # type: ignore[return-value]


def main() -> int:
    init_db()
    expected_teams = {team["team_name"] for team in CONFIRMED_QUALIFIERS}
    checks: list[tuple[bool | None, str, str]] = []

    db = SessionLocal()
    try:
        # ── 1. Teams table ─────────────────────────────────────────────────
        teams = db.scalars(select(Team)).all()
        team_names_db = {team.name for team in teams}

        missing_teams = sorted(expected_teams - team_names_db)
        checks.append(
            fail("All 48 WC2026 teams in `teams` table", f"missing: {missing_teams}")
            if missing_teams
            else ok("All 48 WC2026 teams in `teams` table", f"{len(team_names_db)} teams found")
        )

        # ── 2. Qualified teams registry ────────────────────────────────────
        qualified = db.scalars(
            select(QualifiedTeam).where(QualifiedTeam.tournament_year == 2026)
        ).all()
        qualified_names = [q.team_name for q in qualified]

        duplicate_qualified = [name for name, cnt in Counter(qualified_names).items() if cnt > 1]
        checks.append(
            fail("No duplicate qualified team entries", f"{duplicate_qualified}")
            if duplicate_qualified
            else ok("No duplicate qualified team entries")
        )

        checks.append(
            ok("Exactly 48 qualified teams", f"count={len(qualified_names)}")
            if len(qualified_names) == 48
            else fail("Exactly 48 qualified teams", f"found {len(qualified_names)}, expected 48")
        )

        # ── 3. Group assignments ────────────────────────────────────────────
        teams_without_group = [q.team_name for q in qualified if not q.group_label]
        checks.append(
            fail("All qualified teams have a group", f"{teams_without_group}")
            if teams_without_group
            else ok("All qualified teams have a group")
        )

        from collections import defaultdict

        groups: dict[str, list[str]] = defaultdict(list)
        for q in qualified:
            if q.group_label:
                groups[q.group_label].append(q.team_name)

        wrong_size = {lbl: names for lbl, names in groups.items() if len(names) != 4}
        checks.append(
            fail("All 12 groups have exactly 4 teams", f"bad groups: {wrong_size}")
            if wrong_size or len(groups) != 12
            else ok("All 12 groups have exactly 4 teams", f"{len(groups)} groups")
        )

        # ── 4. Match results ────────────────────────────────────────────────
        all_matches = db.scalars(select(MatchResult)).all()
        total_matches = len(all_matches)
        checks.append(
            ok("Match results table is populated", f"{total_matches:,} rows")
            if total_matches > 0
            else fail("Match results table is populated", "No rows found — run ETL pipeline")
        )

        # Check for duplicate match entries (same home/away/date)
        dup_query = (
            select(
                MatchResult.home_team,
                MatchResult.away_team,
                MatchResult.match_date,
                func.count().label("cnt"),
            )
            .group_by(MatchResult.home_team, MatchResult.away_team, MatchResult.match_date)
            .having(func.count() > 1)
        )
        duplicates = db.execute(dup_query).all()
        if duplicates:
            dup_strs = [f"{r.home_team} vs {r.away_team} on {r.match_date}" for r in duplicates[:5]]
            checks.append(fail("No duplicate match results", f"found {len(duplicates)}: {'; '.join(dup_strs)}"))
        else:
            checks.append(ok("No duplicate match results"))

        # ── 5. Score sanity ─────────────────────────────────────────────────
        bad_scores = [
            m for m in all_matches
            if m.home_goals is not None and m.away_goals is not None
            and (m.home_goals < 0 or m.away_goals < 0)
        ]
        checks.append(
            fail("All match scores are non-negative", f"{len(bad_scores)} bad scores")
            if bad_scores
            else ok("All match scores are non-negative")
        )

        # ── 6. Outcome label consistency ────────────────────────────────────
        mislabeled = []
        for m in all_matches:
            if m.home_goals is None or m.away_goals is None or m.outcome is None:
                continue
            expected_outcome = (
                2 if m.home_goals > m.away_goals
                else 0 if m.away_goals > m.home_goals
                else 1
            )
            if m.outcome != expected_outcome:
                mislabeled.append(m.id)
        checks.append(
            fail(
                "Match outcome labels match scores",
                f"{len(mislabeled)} mismatches (first 5: {mislabeled[:5]})",
            )
            if mislabeled
            else ok("Match outcome labels match scores")
        )

        # ── 7. Date range sanity ────────────────────────────────────────────
        if all_matches:
            dates = [m.match_date for m in all_matches if m.match_date]
            if dates:
                min_date = min(dates)
                max_date = max(dates)
                checks.append(
                    ok("Match date range is plausible", f"{min_date} → {max_date}")
                    if min_date >= date(1872, 1, 1) and max_date <= date(2030, 1, 1)
                    else fail("Match date range is plausible", f"min={min_date}, max={max_date}")
                )

        # ── 8. WC2026 specific matches (if tournament has started) ──────────
        wc_matches = [
            m for m in all_matches
            if m.tournament and "2026" in str(m.tournament) and "World Cup" in str(m.tournament)
        ]
        if wc_matches:
            checks.append(ok("WC2026 match results found", f"{len(wc_matches)} matches"))
        else:
            checks.append(warn("WC2026 matches", "No WC2026 match results yet — tournament may not have started or ETL not run"))

        # ── 9. Recent data freshness ─────────────────────────────────────────
        latest_date = db.scalar(select(func.max(MatchResult.match_date)))
        if latest_date:
            today = date.today()
            days_ago = (today - latest_date).days
            if days_ago <= 7:
                checks.append(ok("Match data is fresh", f"latest result: {latest_date} ({days_ago}d ago)"))
            elif days_ago <= 30:
                checks.append(warn("Match data freshness", f"latest result: {latest_date} ({days_ago} days ago — consider refreshing)"))
            else:
                checks.append(fail("Match data is fresh", f"latest result: {latest_date} ({days_ago} days ago — ETL refresh needed)"))

        # ── 10. Match features coverage ──────────────────────────────────────
        from app.models.match_result import MatchFeatures

        feature_count = db.scalar(select(func.count()).select_from(MatchFeatures))
        match_count_with_scores = sum(
            1 for m in all_matches if m.home_goals is not None and m.away_goals is not None
        )
        if feature_count and match_count_with_scores:
            coverage = feature_count / match_count_with_scores
            checks.append(
                ok("Match feature coverage > 50%", f"{feature_count:,} feature rows / {match_count_with_scores:,} scored matches ({coverage:.0%})")
                if coverage >= 0.5
                else warn("Match feature coverage", f"only {coverage:.0%} of scored matches have feature rows — run feature rebuild")
            )
        else:
            checks.append(warn("Match features", "No feature rows found — run ML feature build pipeline"))

    finally:
        db.close()

    # ── Report ────────────────────────────────────────────────────────────────
    print("World Cup Data Validation Report")
    print("=" * 50)
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

    print("=" * 50)
    total = len(checks)
    passed_count = sum(1 for p, _, _ in checks if p is True)
    print(
        f"Result: {passed_count}/{total} passed"
        + (f" | {warnings} warning(s)" if warnings else "")
        + (f" | {failures} failure(s)" if failures else "")
    )
    if failures == 0:
        print("Status: ALL CHECKS PASSED")
    else:
        print("Status: FAILURES DETECTED — see above")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
