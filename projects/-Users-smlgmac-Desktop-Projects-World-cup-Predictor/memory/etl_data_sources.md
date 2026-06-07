---
name: etl-data-sources
description: ETL pipeline state, data source details, DB counts, WC2026 participant list, and known data quality issues
metadata:
  type: project
---

## Live DB State (as of 2026-06-05 — post WC2026 migration)

- `match_results`: 49,304 rows — date range 1872-11-30 to 2026-06-03 from 327 unique teams
- `qualified_teams`: 52 rows — WC2026 finalized field (Italy/Poland/Denmark removed; 12 new nations added)
- `ml_models`: 5 rows — all active, trained 2026-06-04
- `teams`: 57 rows — seeded from 2022 WC + 2026 qualifiers (12 new teams added by migration)
- `players`: 0 rows — requires FOOTBALL_DATA_API_KEY in .env to populate
- `coaches`: 0 rows — requires FOOTBALL_DATA_API_KEY in .env to populate

## WC2026 Finalized Participant List (52 confirmed)

| Confederation | Count | Teams |
|---|---|---|
| UEFA (17) | 17 | Germany, Portugal, France, Spain, England, Netherlands, Belgium, Croatia, Austria, Switzerland, Turkey, Serbia, Scotland, Norway, Sweden, Czechia, Bosnia and Herzegovina |
| CAF (12) | 12 | Morocco, Senegal, Egypt, Nigeria, Ivory Coast, Cameroon, Ghana, Tunisia, South Africa, Algeria, Cape Verde, DR Congo |
| AFC (9) | 9 | Japan, South Korea, Iran, Australia, Saudi Arabia, Qatar, Uzbekistan, Jordan, Iraq |
| CONMEBOL (7) | 7 | Argentina, Brazil, Colombia, Uruguay, Ecuador, Venezuela, Paraguay |
| CONCACAF (6) | 6 | United States, Canada, Mexico, Panama, Haiti, Curaçao |
| OFC (1) | 1 | New Zealand |

**Removed (did not qualify):** Italy, Poland, Denmark

## Canonical Name Changes (June 2026)

These name changes affect how historical CSV data is canonicalized:
- "Czech Republic" → **"Czechia"** (normalize.py updated)
- "Bosnia & Herzegovina" → **"Bosnia and Herzegovina"** (normalize.py updated)
- "Congo DR" / "Democratic Republic of Congo" → **"DR Congo"** (added to normalize.py)
- "Curacao" → **"Curaçao"** (added to normalize.py)

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
   - **Note:** Cached TSV format changed (now uses 2-letter codes); old cache deleted.
   - Falls back to embedded `_ELO_FALLBACK` dict (~70 teams, June 2026 snapshot) if fetch fails.
   - `fetch_elo_ratings()` now falls through to HTTP fetch if cache parse yields empty.
3. **football-data.org** — Optional API; requires `FOOTBALL_DATA_API_KEY`

## Known Data Issues

- Some CSV rows have NA scores (future matches) — ETL skips these correctly
- Some teams appear under 2+ spelling variants; `normalize.py` NAME_MAP handles 80+ variants
- Training window starts 2000-01-01 (25,243 of 49,304 total rows used for ML)
- New WC2026 teams (Iraq, Curaçao, Haiti, Cape Verde, DR Congo) have sparse historical match data

## Migration Script

`wcip-backend/scripts/migrate_wc2026_teams.py` — idempotent migration:
- Removes Italy, Poland, Denmark from `qualified_teams`
- Upserts 12 new teams to `qualified_teams` and `teams`
- Applies canonical name renames in both tables
- Patches Elo/FIFA rank from `_ELO_FALLBACK` / `_FIFA_RANK_FALLBACK`

**Why:** Production WC2026 dataset update — finalized qualification field.
**How to apply:** When asked about WC2026 teams, use the 52-team list above as authoritative.
