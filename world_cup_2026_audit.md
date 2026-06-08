# World Cup 2026 — Full System Audit

**Date:** 2026-06-07 (4 days before tournament start)
**Auditor:** Principal Engineering Audit

---

## 1. Executive Summary

| Area | Status | Gap Severity |
|---|---|---|
| Team Registry (48 teams) | Partial — all 48 in CONFIRMED_QUALIFIERS, only 32 seeded into teams table | HIGH |
| Player Registry | Critical gap — schema exists, zero records | CRITICAL |
| Coach Registry | Critical gap — schema exists, zero records | CRITICAL |
| Group Assignments | Pending — `group_label` NULL for all rows | HIGH |
| Elo Ratings | Good — fallback snapshot covers all 48 qualifiers | LOW |
| FIFA Rankings | Good — fallback snapshot covers all 48 qualifiers | LOW |
| ETL Pipeline | Partial — historical results + Elo update work; no squad/coach ingestion | HIGH |
| ML Feature Engineering | Functional — graceful fallbacks when player/coach data absent | MEDIUM |
| Tournament Engine | Bug — hardcodes 32-team match IDs (M49-M62); wrong for 48-team 2026 | HIGH |
| Prediction Service | Partial — only "2022" edition registered in `_EDITIONS`; 2026 uses separate route | MEDIUM |
| API Coverage | Good — `/world-cup/*` routes exist; missing `/world-cup/predictions` | MEDIUM |
| Frontend — Landing Page | Gap — no WC2026 Intelligence Center section | MEDIUM |
| Frontend — WC2026 Page | Good — fully functional, handles no-draw state gracefully | LOW |
| Automated Tests | Gap — no tests verifying all 48 teams exist and are simulatable | HIGH |

---

## 2. Team Registry Audit

### 2.1 Existing Records

**`qualified_teams` table (seeded at startup):**
- All 48 confirmed qualifiers present via `CONFIRMED_QUALIFIERS` in `wcip/data/wc2026.py`
- `group_label` = NULL for all rows (draw known but not persisted)
- `pot` = NULL for all rows

**`teams` table (seeded at startup):**
- 32 teams from `wcip/data/teams_2022.py` (2022 WC field)
- 16 additional WC2026-only teams added by `seed_2026_teams_into_team_table()`
- Total: up to 48 if migration ran; may be 32 if not
- Missing fields: `wc_appearances`, `squad_market_value_eur`, `recent_form_5`, `goals_scored_10`, `goals_conceded_10`, `squad_strength_score`

### 2.2 Missing / Inconsistent Records

| Issue | Teams Affected |
|---|---|
| Only in 2022 seed (may not be in 2026 qualified list): Poland, Denmark, Italy | 3 teams (correctly absent from WC2026 — did not qualify) |
| In WC2026 qualified list but NOT in 2022 seed (need 2026-only seed): Czechia, Sweden, Norway, Algeria, Paraguay, Bosnia and Herzegovina, South Africa, Cameroon, Algeria, Cape Verde, DR Congo, Panama, Haiti, Curaçao, Iraq, Uzbekistan, Jordan, New Zealand, Qatar, Venezuela | ~20 teams |
| `teams` table missing extended stats columns | All 48 teams |

### 2.3 Required Migrations

1. Add columns to `teams` table:
   - `wc_appearances` INTEGER DEFAULT 0
   - `squad_market_value_eur` FLOAT (total squad value)
   - `recent_form_5` FLOAT (pts/game last 5 matches, 0–3)
   - `goals_scored_10` FLOAT (avg goals scored per match, last 10)
   - `goals_conceded_10` FLOAT (avg goals conceded per match, last 10)
   - `squad_strength_score` FLOAT (0–100 composite score)

2. Seed `group_label` for all 48 teams (official draw December 2024 — provisional serpentine-by-Elo until official data confirmed)

---

## 3. Player Registry Audit

### 3.1 Existing Schema

```
players table: id, name, team_name, position, club, age, nationality,
  minutes_played, goals, assists, xg, xag, key_passes, shots_on_target,
  progressive_passes, progressive_carries, tackles, interceptions, clearances,
  yellow_cards, red_cards, injured, suspended, injury_notes,
  market_value_eur, international_caps, international_goals,
  recent_form_score, fitness_score, data_source, external_id, updated_at
```

Schema is comprehensive and correct.

### 3.2 Current State

**Players in DB: 0**

No ETL source has been wired to populate player records. The `load_players()` function in `etl/load/db_loader.py` exists but is never called from any pipeline.

### 3.3 Required Work

- Create `etl/world_cup_2026/seed_data.py` with ~1,100 player records (48 teams × ~23 players)
- Wire into `init_db()` and `etl/pipeline.py`
- Ensure idempotent upsert (name + team_name uniqueness)

---

## 4. Coach Registry Audit

### 4.1 Existing Schema

```
coaches table: id, name, team_name, nationality, preferred_formation,
  win_pct, draw_pct, loss_pct, matches_managed, tournament_experience,
  knockout_record, tactical_flexibility, recent_form_score, impact_score,
  data_source, updated_at
```

### 4.2 Current State

**Coaches in DB: 0**

### 4.3 Required Work

- Seed all 48 national team coaches in `etl/world_cup_2026/seed_data.py`
- Coach impact score feeds into `coach_impact_diff` feature (Feature 10 of 17)
- Currently falls back to 1.0 for all teams (neutral)

---

## 5. ETL Pipeline Audit

### 5.1 Existing Pipelines

| Pipeline | Status | Notes |
|---|---|---|
| `run_historical_results()` | Working | Downloads Kaggle CSV of all international results |
| `run_elo_update()` | Working | Updates Team.elo from eloratings.net |
| FIFA rankings fetch | Working | Fallback snapshot covers all 48 WC2026 nations |
| Squad/player ingestion | Missing | `etl/extract/football_data.py` exists but not wired |
| Coach ingestion | Missing | No extractor or loader |
| WC2026-specific pipeline | Missing | `etl/world_cup_2026/` does not exist |

### 5.2 Required ETL Additions

```
etl/world_cup_2026/
├── __init__.py
├── seed_data.py        # authoritative WC2026 data (squads, coaches, groups)
├── ingest.py           # pipeline: extract -> validate -> load
└── validate.py         # completeness checks
```

---

## 6. Tournament Engine Audit

### 6.1 Critical Bug — Hardcoded 32-team Match IDs

In `wcip/engine/tournament.py`, `simulate()` references:
```python
sf = [knockout["M61"].home, knockout["M61"].away,   # ← 32-team SF IDs
      knockout["M62"].home, knockout["M62"].away]
qf = [knockout[m].home for m in ("M57","M58","M59","M60")]
r16 = [knockout[m].home for m in ("M49"....."M56")]
```

For 48-team 2026 format the match IDs are different:
- R32: 16 matches (M49–M64)
- R16: 8 matches (M65–M72)
- QF: 4 matches (M73–M76)
- SF: 2 matches (M77, M78)
- Final: FINAL

### 6.2 Bracket Generator Bug

`build_2026_bracket()` calls `_generate_r32_pairings()` which returns only 6 pairs (half of 12 groups), yielding 6 R32 matches instead of 16. The 8 best 3rd-place teams are not handled.

### 6.3 Required Fixes

1. Extend bracket format to carry `round_name` metadata
2. Fix `_generate_r32_pairings_2026()` to generate 16 R32 matches
3. Implement 3rd-place team selection (8 best from 12 groups)
4. Make `simulate()` detect rounds dynamically (no hardcoded IDs)
5. Add `third_place_match` to `TournamentResult`

---

## 7. ML Pipeline Audit

### 7.1 Feature Engineering

All 17 features are well-defined. Graceful fallbacks exist for missing data. When players/coaches are absent, features fall back to neutral values (0.0 or 1.0). **The feature engineering code is correct; it just needs real data.**

### 7.2 Model Files

Five models exist as `.pkl` files:
- `models/catboost.pkl`
- `models/lightgbm.pkl`
- `models/logistic.pkl`
- `models/random_forest.pkl`
- `models/xgboost.pkl`

These were trained on historical match data (since 2000). Adding WC2026 player/coach data won't require retraining — the features are already computed dynamically. Retraining is optional to add more recent 2025/2026 match results.

### 7.3 Ensemble

The ensemble weights are DB-driven and normalized. No changes required unless retraining produces new weights.

---

## 8. API Audit

### 8.1 Existing Endpoints

| Endpoint | Status |
|---|---|
| `GET /world-cup/qualified-teams` | Working |
| `GET /world-cup/groups` | Working (empty until groups seeded) |
| `GET /world-cup/bracket` | Working |
| `POST /world-cup/simulate` | Working for 2026 (provisional groups) |
| `GET /world-cup/schedule` | Working |
| `GET /world-cup/teams/{name}` | Working |
| `GET /world-cup/players/{name}` | Working (empty until players seeded) |
| `GET /world-cup/predictions` | **Missing** |
| `GET /teams` | Working — returns all teams from DB |
| `POST /ml/predict` | Working — hybrid prediction |

### 8.2 Missing Endpoints

- `GET /world-cup/predictions` — pre-computed champion/stage probabilities for all 48 teams
- `GET /world-cup/stats` — aggregate stats (team count, player count, coach count, sim count)

---

## 9. Frontend Audit

### 9.1 Existing Pages

| Page | Status |
|---|---|
| `/` (landing) | Good — missing WC2026 Intelligence Center section |
| `/wc2026` | Good — fully functional |
| `/simulate` | Working — uses 2022 edition |
| `/predict` | Working — ML predictions |
| `/scenarios` | Working |
| `/teams`, `/team/[id]` | Working |
| `/compare` | Working |

### 9.2 Missing Frontend Work

- Landing page: Add "World Cup 2026 Intelligence Center" section with live stats, favorites, dark horse picks
- All team selectors must include all 48 WC2026 teams (currently populated dynamically from API — OK once backend is seeded)

---

## 10. Required Actions Summary

### CRITICAL (do now)
1. Seed player data for all 48 teams (~1,100 records)
2. Seed coach data for all 48 teams (48 records)
3. Fix tournament engine 48-team bracket bug

### HIGH
4. Seed official group assignments
5. Add extended team stats fields
6. Create `etl/world_cup_2026/` ETL module
7. Wire ETL into `init_db()` and pipeline

### MEDIUM
8. Add `/world-cup/predictions` endpoint
9. Update landing page with Intelligence Center
10. Add automated WC2026 validation tests

### LOW
11. Update README, MODEL_CARD, MEMORY
12. Optionally retrain models with 2025/2026 match data

---

## 11. Data Lineage

```
SEED SOURCE (etl/world_cup_2026/seed_data.py)
  ↓ ingest.py
  ├── qualified_teams table  ← groups, pots
  ├── teams table            ← elo, fifa_rank, extended stats
  ├── players table          ← squads (23-26 per team)
  └── coaches table          ← 1 per team

LIVE UPDATE (etl/pipeline.py)
  ├── eloratings.net         → teams.elo (daily)
  ├── FIFA rankings API      → teams.fifa_rank (monthly)
  └── international_results  → match_results (incremental)

ML PIPELINE
  match_results → feature_matrix → model training → ensemble weights

SIMULATION
  qualified_teams + teams + (players/coaches for features)
  → MonteCarloEngine → champion/stage probabilities
```
