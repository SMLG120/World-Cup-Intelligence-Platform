---
name: etl-data-sources
description: ETL pipeline state, data source details, DB counts, WC2026 participant list, and known data quality issues
metadata:
  type: project
---

## Live DB State (as of 2026-06-08 — post FIFA ranking audit)

- `match_results`: 49,306 rows — date range 1872-11-30 to 2026-06-03 from 327 unique teams
- `qualified_teams`: 48 rows — official WC2026 field with Group A-L labels
- `ml_models`: 5 rows — all active, trained 2026-06-04
- `teams`: 57 rows — seeded from 2022 WC + 2026 qualifiers (12 new teams added by migration)
- `players`: 48 startup placeholder rows until verified squad snapshot import
- `coaches`: 48 startup placeholder rows until verified coach snapshot import
- `fifa_ranking_snapshots`: 0 rows locally at audit time; migration and loader are ready
- `fifa_ranking_entries`: 0 rows locally at audit time; populated by ranking snapshot ingestion

## FIFA Ranking Audit (June 2026)

- Latest official FIFA men's ranking publication checked during the audit: 2026-04-01
- Next listed FIFA update during the audit: 2026-06-11
- Official top status from FIFA article/page metadata: France #1, Spain #2,
  Argentina #3, Portugal #5, Brazil #6
- Local DB before ingestion: Brazil #1, Belgium #2, Argentina #3, France #4
- Local cache before ingestion: Argentina #1, France #2, England #3, Belgium #4, Brazil #5
- Fix: rankings now ingest into `fifa_ranking_snapshots` and
  `fifa_ranking_entries`; `teams.fifa_rank` is current-display cache only

## WC2026 Official Participant List (48 teams)

| Confederation | Count | Teams |
|---|---|---|
| UEFA (16) | 16 | Czechia, Bosnia and Herzegovina, Switzerland, Scotland, Turkey, Germany, Netherlands, Sweden, Belgium, Spain, Norway, France, Austria, Portugal, England, Croatia |
| CAF (10) | 10 | South Africa, Morocco, Ivory Coast, Tunisia, Egypt, Cape Verde, Senegal, Algeria, DR Congo, Ghana |
| AFC (9) | 9 | Japan, South Korea, Iran, Australia, Saudi Arabia, Qatar, Uzbekistan, Jordan, Iraq |
| CONMEBOL (6) | 6 | Brazil, Paraguay, Ecuador, Uruguay, Argentina, Colombia |
| CONCACAF (6) | 6 | United States, Canada, Mexico, Panama, Haiti, Curaçao |
| OFC (1) | 1 | New Zealand |

**Removed from stale local data:** Italy, Poland, Denmark, Nigeria, Cameroon, Serbia, Venezuela

## WC2026 Official Groups

- Group A: Mexico, South Africa, South Korea, Czechia
- Group B: Canada, Bosnia and Herzegovina, Qatar, Switzerland
- Group C: Brazil, Morocco, Haiti, Scotland
- Group D: United States, Paraguay, Australia, Turkey
- Group E: Germany, Curaçao, Ivory Coast, Ecuador
- Group F: Netherlands, Japan, Sweden, Tunisia
- Group G: Belgium, Egypt, Iran, New Zealand
- Group H: Spain, Cape Verde, Saudi Arabia, Uruguay
- Group I: France, Senegal, Iraq, Norway
- Group J: Argentina, Algeria, Austria, Jordan
- Group K: Portugal, DR Congo, Uzbekistan, Colombia
- Group L: England, Croatia, Ghana, Panama

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
   - 49,306 local DB rows observed during the ranking audit
2. **eloratings.net** — TSV at `https://www.eloratings.net/World.tsv`
   - **Note:** Cached TSV format changed (now uses 2-letter codes); old cache deleted.
   - Falls back to embedded `_ELO_FALLBACK` dict (~70 teams, June 2026 snapshot) if fetch fails.
   - `fetch_elo_ratings()` now falls through to HTTP fetch if cache parse yields empty.
3. **Official FIFA men's rankings** — `https://inside.fifa.com/fifa-world-ranking/men`
   - Extractor resolves the latest FIFA ranking schedule id and stores immutable snapshots
   - Snapshot tables preserve ranks historically for features, backtests, and retraining
4. **football-data.org** — Optional API; requires `FOOTBALL_DATA_API_KEY`
5. **FIFA standings** — Official WC2026 team/group reference
6. **WC2026 placeholder seed** — one `world_cup_2026_placeholder` player and
   coach per team for local startup; real imports replace placeholders by team

## Known Data Issues

- Some CSV rows have NA scores (future matches) — ETL skips these correctly
- Some teams appear under 2+ spelling variants; `normalize.py` NAME_MAP handles 80+ variants
- Active stored models were trained on 25,243 rows; current local feature generation sees 25,245 rows from 2000+
- New WC2026 teams (Iraq, Curaçao, Haiti, Cape Verde, DR Congo) have sparse historical match data
- Startup player/coach rows are placeholders, not verified squad or staff data
- Historical FIFA ranking snapshots still need backfill; missing historical periods use neutral ranking values to avoid leakage

## Migration Script

`wcip-backend/scripts/migrate_wc2026_teams.py` — idempotent migration:
- Removes Italy, Poland, Denmark from `qualified_teams`
- Upserts 12 new teams to `qualified_teams` and `teams`
- Applies canonical name renames in both tables
- Patches Elo/FIFA rank from `_ELO_FALLBACK` / `_FIFA_RANK_FALLBACK`

## Ranking Snapshot Migration

`wcip-backend/alembic/versions/3f8b9d9c2a11_add_fifa_ranking_snapshots.py`
adds:

- `fifa_ranking_snapshots`
- `fifa_ranking_entries`

Run ranking ingestion with:

```bash
cd wcip-backend
python -c "from etl.pipeline import run_fifa_rankings_update; print(run_fifa_rankings_update(force_refresh=True))"
```

**Why:** Production WC2026 dataset update — finalized qualification field.
**How to apply:** When asked about WC2026 teams, use the 48-team official list and groups above as authoritative.
