# Codebase Audit - World Cup 2026 Platform

Audit date: 2026-06-08

Scope: FastAPI routes, SQLAlchemy models, ETL loaders, WC2026 data module,
prediction/tournament engines, frontend API client, frontend route usage, and
local SQLite data state.

Primary references:

- FIFA standings page: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/standings
- FIFA teams page: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/teams/
- FIFA qualified teams article: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/world-cup-2026-who-has-qualified
- FIFA match schedule article: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/match-schedule-fixtures-results-teams-stadiums

## Executive Summary

The initial audit found three production blockers:

1. The backend could not import `wcip.data.teams_2022` because
   `wcip-backend/wcip/data/teams_2022.py` had been deleted in the worktree.
2. The WC2026 data layer was stale: local data had 52 teams, no group labels,
   and extra non-qualified teams, while FIFA's current reference shows the
   official 48-team field and Group A-L assignments.
3. The API did not expose several prompt-requested compatibility paths,
   including direct `/players` routes and snake-case `/world_cup/*` aliases.

Remediation in this pass restores backend startup, replaces the WC2026 fallback
with the official 48-team grouped field, adds placeholder-safe player/coach
startup rows, and adds compatibility routes for expected client paths.

## Initial Local Database State

Checked via `wcip-backend/wcip.db` before remediation:

| Table | Count |
|---|---:|
| `teams` | 57 |
| `qualified_teams` | 52 |
| `players` | 0 |
| `coaches` | 0 |

Group labels:

| Group label | Count |
|---|---:|
| `NULL` / empty | 52 |

Implications:

- WC2026 group views cannot show official groups.
- WC2026 team detail pages cannot show real squad or coach data.
- Player pages are not meaningful until player ingestion is populated.
- Feature engineering that depends on players/coaches falls back to neutral or
  missing values.

Post-fix startup state:

- `qualified_teams`: 48 official teams, each with `group_label`.
- `players`: one `world_cup_2026_placeholder` row per WC2026 team until a
  verified roster snapshot is imported.
- `coaches`: one `world_cup_2026_placeholder` row per WC2026 team until a
  verified coach snapshot is imported.
- `teams`: every WC2026 team exists in the main team registry.

## Broken Endpoints And Startup Risks

### Critical: backend import failure

Cause:

- `app/services/prediction.py` imports:
  `from wcip.data.teams_2022 import BRACKET_2022, GROUPS_2022, build_teams`
- `wcip-backend/wcip/data/teams_2022.py` is deleted in the current worktree.

Impact:

- Importing `app.main` fails with `ModuleNotFoundError`.
- Frontend receives request failures because the API server cannot serve routes.

Required fix:

- Restore `teams_2022.py` or migrate all prediction-service imports away from it.

### Missing route compatibility

Routes requested in the prompt but not implemented under those exact paths:

| Requested route | Current equivalent | Risk |
|---|---|---|
| `GET /players` | none | Missing player registry API |
| `GET /players/{id}` | none | Player detail page has no direct API |
| `GET /world_cup/groups` | `GET /world-cup/groups` | Snake-case clients 404 |
| `GET /world_cup/standings` | none | Missing standings route |
| `GET /world_cup/bracket` | `GET /world-cup/bracket` | Snake-case clients 404 |
| `POST /matches/predict` | `POST /match/simulate` | Compatibility clients 404 |
| `POST /simulations/tournament` | `POST /tournament/simulate` | Compatibility clients 404 |
| `POST /scenarios` | `POST /scenario/compare` | Compatibility clients 404 |

Required fix:

- Add player endpoints.
- Add compatibility aliases or update all clients to use canonical paths.

Implemented:

- `GET /players`
- `GET /players/{id}`
- `GET /world_cup/groups`
- `GET /world_cup/standings`
- `GET /world_cup/bracket`
- `POST /matches/predict`
- `POST /simulations/tournament`
- `POST /scenarios`

## WC2026 Data Audit

### Local fallback data

`wcip-backend/wcip/data/wc2026.py` initially reported:

- `CONFIRMED_QUALIFIERS`: 52 teams
- Unique names: 52
- Group labels: none

Problems:

- FIFA's current field is 48 teams.
- Local data contains teams that are not in the current FIFA qualified list.
- Local data omits official group assignments.
- Local code still treats the draw as incomplete.

Implemented:

- `CONFIRMED_QUALIFIERS` now contains the official 48-team grouped field.
- DB reads fall back to the static official seed if the local DB is stale.
- Startup seeding prunes stale WC2026 rows that are not in the official field.
- Known FIFA display names are normalized to local canonical names.

### Official FIFA group data to reflect locally

Based on FIFA's indexed official pages and schedule:

| Group | Teams |
|---|---|
| A | Mexico, South Africa, South Korea, Czechia |
| B | Canada, Bosnia and Herzegovina, Qatar, Switzerland |
| C | Brazil, Morocco, Haiti, Scotland |
| D | United States, Paraguay, Australia, Turkey |
| E | Germany, Curaçao, Ivory Coast, Ecuador |
| F | Netherlands, Japan, Sweden, Tunisia |
| G | Belgium, Egypt, Iran, New Zealand |
| H | Spain, Cape Verde, Saudi Arabia, Uruguay |
| I | France, Senegal, Iraq, Norway |
| J | Argentina, Algeria, Austria, Jordan |
| K | Portugal, DR Congo, Uzbekistan, Colombia |
| L | England, Croatia, Ghana, Panama |

Name normalization note: FIFA uses display names such as Korea Republic,
Türkiye, Côte d'Ivoire, Cabo Verde, IR Iran, and Congo DR. The codebase currently
uses canonical names South Korea, Turkey, Ivory Coast, Cape Verde, Iran, and
DR Congo. This is acceptable internally only if aliases are consistently handled.

## Knockout Structure Audit

Current code already improved the local placeholder bracket shape, but the
official FIFA Round-of-32 match map should be represented explicitly where known.

Requirements:

- 12 group winners, 12 runners-up, and 8 best third-place teams enter the Round
  of 32.
- UI labels should show Round of 32, Round of 16, Quarter-finals, Semi-finals,
  Third-place match, and Final.
- If exact third-place combinations are not represented, label them as
  placeholder rather than official fixtures.

Risk:

- A purely placeholder bracket can be statistically useful but should not be
  marketed as the official fixture bracket.

## Prediction Plausibility Audit

Existing strengths:

- Match probability responses sum to approximately 1 in existing tests.
- Monte Carlo champion probabilities are aggregated per team.
- Scenario modifiers are wired into match/tournament paths.

Risks:

- Player/coach-dependent features are only as strong as the loaded roster data;
  placeholder rows are intentionally neutral.
- WC2026 simulation uses official groups, but knockout fixture slots remain
  placeholder until exact FIFA pairings are imported.
- Extreme Elo and missing feature values need explicit tests for NaN/Inf guards.

Implemented:

- Restored the 2022 seed module used by prediction imports.
- Added prediction fallback for WC2026 teams that were not in the 2022 seed.
- Added a restricted-environment fallback for Monte Carlo multiprocessing.
- Added WC2026 validation checks for probability bounds and finite values.

## Frontend Audit

Frontend API client:

- `wcip-frontend/lib/api.ts` uses `/backend/api/v1` by default.
- The client calls canonical active routes such as `/world-cup/groups`,
  `/world-cup/simulate`, and `/world-cup/players/{team}`.
- It throws `ApiError` for non-2xx responses. A generic `Request failed (500)`
  means the backend returned a server error without a useful JSON detail.

Frontend display risks:

- `/world-cup` and `/wc2026` can only show groups if the backend returns
  `group_label` data.
- `/team/[id]` links player pages with a query param derived from the first
  player name in `SquadBrief`, not the team name. This can break player detail
  lookup.
- `/player/[id]` depends on loading a squad by `team` query param rather than a
  direct `GET /players/{id}` endpoint.
- Prediction selectors use `/teams`, which currently contains 2022 baseline
  teams plus stale WC2026 seeding artifacts in the local database.

Required fixes:

- Add direct backend player endpoints.
- Update frontend player links to pass the team name or fetch by player ID.
- Ensure WC2026 pages use API data only and show clear empty/error states.
- Ensure group labels come from official group data, not placeholders.

Implemented:

- Team pages pass the team name in player links.
- Player pages fetch `GET /players/{id}` first and only use squad fallback when
  needed.
- Placeholder roster rows are labelled in the team/player UI.

## API Contract Audit

Current frontend/backend contracts mostly align for existing canonical routes:

- `Team`
- `QualifiedTeam`
- `WC2026Groups`
- `WC2026Simulation`
- `TeamDetail`
- `Player`

Contract gaps:

- No `PlayerOut` schema for direct player endpoints.
- `TeamOut` lacks WC2026 group fields; team pages must call WC2026 detail routes.
- Compatibility route names are missing.
- Error responses are not structured beyond FastAPI's default `detail`.

## Required Fix Plan

1. Complete: restore `wcip-backend/wcip/data/teams_2022.py` so backend startup works.
2. Complete: replace local WC2026 fallback data with the 48-team FIFA group field.
3. Complete: seed `qualified_teams.group_label` from the WC2026 source.
4. Complete: add direct player API endpoints and schemas.
5. Complete: add compatibility route aliases for prompt-requested route paths.
6. Complete: add `scripts/validate_world_cup_2026.py`.
7. Complete: add tests for:
   - backend import/startup
   - WC2026 groups return 12 groups of 4
   - WC2026 simulation returns 200 and normalized champion probabilities
   - player list/detail endpoints
   - invalid route inputs return 400/404/422, not 500
8. Complete: update frontend player-team mapping bug and direct player fetch.

## Current Audit Status

Audit and targeted remediation are complete for the reported 500-risk data-load
path. Remaining production hardening is focused on importing verified player and
coach snapshots, replacing placeholder knockout slots with exact FIFA pairings
when available, and adding browser-level visual regression coverage.
