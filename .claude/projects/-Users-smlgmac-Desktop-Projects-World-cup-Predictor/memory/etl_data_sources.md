---
name: etl-data-sources
description: ETL pipeline state, data source details, DB counts, and known data quality issues
metadata:
  type: project
---

## Live DB State (as of 2026-06-04)

- `match_results`: 49,304 rows — date range 1872-11-30 to 2026-06-03 from 327 unique teams
- `qualified_teams`: 43 rows — WC2026 confirmed qualifiers (5 playoff slots still TBD)
- `ml_models`: 5 rows — all active, trained 2026-06-04
- `teams`: 45 rows — seeded from 2022 WC + 2026 qualifiers
- `players`: 0 rows — requires FOOTBALL_DATA_API_KEY in .env to populate
- `coaches`: 0 rows — requires FOOTBALL_DATA_API_KEY in .env to populate

## Outcome Distribution

- home_win: 24,162 (48.2%)
- draw: 11,208 (22.3%)
- away_win: 13,934 (27.8%)

## ETL State File

`wcip-backend/etl/data/etl_state.json` — stores `last_results_date` for incremental runs.
Delete to force full refresh on next run.

## Data Sources

1. **martj42 CSV** — `https://github.com/martj42/international_results` — CC BY-SA 4.0
   - Cached at `wcip-backend/data/cache/results.csv`
   - 49,306 rows parsed → 49,304 unique (2 in-run duplicates deduplicated)
2. **eloratings.net** — TSV at `https://www.eloratings.net/World.tsv`
   - Falls back to embedded `_ELO_FALLBACK` dict (~50 teams, Jan 2025 snapshot) if fetch fails
3. **football-data.org** — Optional API; requires `FOOTBALL_DATA_API_KEY`

## Known Data Issues

- Some CSV rows have NA scores (future matches) — ETL skips these correctly
- Some teams appear under 2+ spelling variants; `normalize.py` NAME_MAP handles 60+ variants
- Training window starts 2000-01-01 (25,243 of 49,304 total rows used for ML)

**Why:** Historical pre-2000 matches excluded from ML training to reduce pre-modern football noise while retaining for Elo computation.
**How to apply:** When asked about training data size vs total matches, these are the correct numbers.
