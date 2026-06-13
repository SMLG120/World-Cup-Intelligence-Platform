# PLAYER_ELO_INGESTION_AUDIT.md
> Audited: 2026-06-13

---

## 1. Database Models

### Player (`players` table)
**Existing fields:** id, name, team_name, position, club, age, nationality, minutes_played, goals, assists, xg, xag, key_passes, shots_on_target, progressive_passes, progressive_carries, tackles, interceptions, clearances, yellow_cards, red_cards, injured, suspended, injury_notes, profile_description, market_value_eur, international_caps, international_goals, player_rating, ea_fc_rating, player_rating_source, player_rating_version, player_rating_updated_at, recent_form_score, fitness_score, data_source, external_id, updated_at

**Missing FIFA Squad PDF fields (not yet in DB):**
| Field | Type | Notes |
|-------|------|-------|
| `date_of_birth` | String(12) | "DD/MM/YYYY" per FIFA PDF |
| `height_cm` | Integer | three-digit integer from PDF |
| `shirt_number` | Integer | squad shirt number |
| `first_names` | String(80) | given name(s) as listed |
| `last_names` | String(80) | surname(s) in uppercase per FIFA |
| `name_on_shirt` | String(60) | short name on back of shirt |

### Coach (`coaches` table)
**Existing fields:** id, name, team_name, nationality, preferred_formation, win_pct, draw_pct, loss_pct, matches_managed, tournament_experience, knockout_record, tactical_flexibility, recent_form_score, impact_score, data_source, updated_at

**Missing / not linked:**
| Field | Type | Notes |
|-------|------|-------|
| `team_id` | Integer FK → teams.id | currently only a string `team_name` |
| `first_names` | String(80) | given name(s) |
| `last_names` | String(80) | surname(s) |
| `role` | String(60) | "Head Coach", "Assistant Coach", etc. |

---

## 2. ETL Pipeline

### Squad PDF Parser — `etl/players/fifa_squad_pdf.py`
- **EXISTS.** Parses FIFA PDF text → writes proxy-rated CSV for import
- Regex-based line parser: recognises rows starting with `GK|DF|MF|FW`
- Derives proxy `player_rating` from caps, goals, age, height, position
- Outputs CSV columns: `dob`, `height_cm` — but csv_import.py does NOT write these to the DB
- **Does NOT parse coach rows** (`ROLE COACH` header line is skipped; coach data lines are not `_looks_like_player_row`)
- Validation threshold: if `< 1,000` players parsed → treat as parse failure

### Player CSV Importer — `etl/player_ratings/csv_import.py`
- Upserts `Player` rows via `_upsert_player()`
- Does **NOT** write `date_of_birth`, `height_cm`, `shirt_number`, `first_names`, `last_names`, `name_on_shirt`
- Uses `canonical()` for team name normalization

### Elo Pipeline — `etl/elo/`
| File | Status |
|------|--------|
| `extract_elo.py` | **COMPLETE** — multi-source: WC page → World.tsv → embedded fallback |
| `transform_elo.py` | **COMPLETE** — deduplication, `canonical()` normalization |
| `load_elo.py` | **COMPLETE** — versioned snapshots, never overwrites history |
| `validate_elo.py` | **EXISTS** |

Primary URL: `https://www.eloratings.net/2026_World_Cup`  
Fallback URL: `https://www.eloratings.net/World.tsv`  
Embedded fallback: `etl/extract/elo_ratings._ELO_FALLBACK` dict  
DB tables: `elo_rating_snapshots`, `team_elo_ratings`, `elo_source_logs`

---

## 3. ML Features — `ml/features.py`

| # | Feature | Source |
|---|---------|--------|
| 0 | elo_diff | EloRatingSnapshot / EloHistory |
| 1 | fifa_rank_diff | FifaRankingEntry |
| 2–6 | xg_diff, xga_diff, goals_scored_diff, goals_conceded_diff, form_diff | MatchResult history |
| 7–11 | avg_age_diff, market_value_diff, injury_burden_diff, coach_impact_diff, squad_chemistry_diff | Player / Coach / Team tables |
| 12–14 | travel_distance_km, rest_days, tournament_exp_diff | simplified |
| 15–16 | starting_xi_strength_diff, bench_strength_diff | derived |
| 17–32 | player rating aggregates (GK/DEF/MID/FWD, squad depth, caps, goals, weighted strength) | Player table |

FEATURE_VERSION = "v2", N_FEATURES = 33  
Point-in-time logic: uses `as_of_date` for snapshot lookups to avoid data leakage.

**Not yet in ML features:**
- Goalkeeper height advantage (`height_cm` for GK vs opponent GK)
- Age profile score derived from `date_of_birth` (not `age` which can drift)

---

## 4. Simulation Engine

| File | Role |
|------|------|
| `wcip/engine/montecarlo.py` | Parallel Monte Carlo over N simulations |
| `wcip/engine/tournament.py` | WC 2026 48-team bracket/group logic |
| `wcip/engine/match.py` | Match outcome sampler |
| `wcip/engine/scoreline.py` | Poisson-based scoreline model |
| `wcip/engine/elo.py` | Live Elo K-factor updates |

Elo is fetched at simulation time via `_get_team_elo()` in `features.py`.

---

## 5. API Endpoints

### Public (read-only)
| Method | Path | Status |
|--------|------|--------|
| GET | `/api/v1/players` | ✅ exists |
| GET | `/api/v1/players/{id}` | ✅ exists |
| GET | `/api/v1/teams` | ✅ exists |
| GET | `/api/v1/teams/{id}` | ✅ exists |
| GET | `/api/v1/teams/{id}/stats` | ✅ exists |
| GET | `/api/v1/teams/{id}/elo-history` | ✅ exists |
| GET | `/api/v1/teams/{id}/players` | ❌ MISSING |
| GET | `/api/v1/teams/{id}/squad-strength` | ❌ MISSING |
| GET | `/api/v1/data/freshness` | ✅ exists (in data.py) |

### Admin (auth-gated)
| Method | Path | Status |
|--------|------|--------|
| POST | `/api/v1/admin/data/refresh-elo` | ✅ exists |
| POST | `/api/v1/admin/data/refresh-fifa-rankings` | ✅ exists |
| POST | `/api/v1/admin/data/refresh-players` | ✅ exists |
| POST | `/api/v1/admin/data/refresh-all` | ✅ exists |
| POST | `/api/v1/admin/data/ingest-squad-pdf` | ❌ MISSING |

---

## 6. Alembic Migration State

| Revision | Description |
|----------|-------------|
| `0964b8fff254` | initial schema |
| `3f8b9d9c2a11` | add_fifa_ranking_snapshots |
| `73b2e6b46c21` | add_prediction_data_quality_tables |
| `a1c9e8d4f602` | add_realtime_elo_and_refresh_metadata (HEAD) |

**Next migration needed:** add FIFA squad PDF columns to `players` and `coaches`.

---

## 7. Gaps — Priority Order

| Priority | Gap | Action |
|----------|-----|--------|
| HIGH | Player model missing 6 FIFA PDF fields | Update `app/models/player.py` |
| HIGH | Coach model missing `team_id`, role, name parts | Update `app/models/player.py` |
| HIGH | No Alembic migration for new fields | Create `alembic/versions/b5c7…_add_player_squad_fields` |
| HIGH | No direct PDF→DB loader | Create `etl/players/load_squad_pdf.py` |
| HIGH | No squad ingestion validation script | Create `scripts/validate_squad_ingestion.py` |
| HIGH | Missing admin ingest-squad-pdf endpoint | Update `app/api/v1/admin_data.py` |
| MEDIUM | csv_import does not write height_cm / dob | Update `etl/player_ratings/csv_import.py` |
| MEDIUM | Missing `GET /teams/{id}/players` endpoint | Update `app/api/v1/teams.py` |
| MEDIUM | Missing `GET /teams/{id}/squad-strength` endpoint | Update `app/api/v1/teams.py` |
| LOW | ML features: GK height, age-profile from DOB | Update `ml/features.py` |

---

## 8. Constraints

- **Do not rewrite the app.** Extend safely.
- **Do not hardcode predictions** or artificially favour any nation.
- **Do not create mock players.** Only real squad data.
- **Do not destroy existing historical data.** Alembic migrations must be additive.
- Admin routes must require `AdminUser` dependency.
- If fewer than 1,000 players parsed from the PDF → treat as parse failure and raise.
