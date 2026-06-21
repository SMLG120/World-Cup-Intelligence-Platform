# Homepage/Auth/Hydration/Data Audit

Date: 2026-06-21

## Scope Reviewed

- Homepage route: `wcip-frontend/app/page.tsx`
- Navbar/auth state: `wcip-frontend/components/nav.tsx`, `wcip-frontend/lib/auth-context.tsx`
- Prediction/bracket links: `wcip-frontend/app/page.tsx`, `wcip-frontend/app/wc2026/page.tsx`, `wcip-frontend/app/wc2026/bracket/page.tsx`
- Data freshness UI: `wcip-frontend/components/data-freshness.tsx`
- Frontend API/auth client: `wcip-frontend/lib/api.ts`, `wcip-frontend/lib/queries.ts`
- Backend auth: `wcip-backend/app/api/v1/auth.py`, `wcip-backend/app/schemas/auth.py`, `wcip-backend/app/core/security.py`
- Backend rating/ranking APIs: `wcip-backend/app/api/v1/ratings.py`, `wcip-backend/app/api/v1/rankings.py`
- Freshness backend: `wcip-backend/app/api/v1/data.py`, `wcip-backend/app/services/data_refresh_service.py`
- Team/player/squad APIs: `wcip-backend/app/api/v1/teams.py`, `wcip-backend/app/api/v1/players.py`, `wcip-backend/app/api/v1/world_cup.py`
- Squad ingestion: `wcip-backend/etl/players/load_squad_pdf.py`, `wcip-backend/etl/players/fifa_squad_pdf.py`, `wcip-backend/scripts/validate_squad_ingestion.py`
- Feature pipeline: `wcip-backend/ml/features.py`

## What Is Working

- Backend exposes the required read endpoints:
  - `GET /api/v1/ratings/elo/latest`
  - `GET /api/v1/rankings/fifa/latest`
  - `GET /api/v1/data/freshness`
- Data freshness backend separates Elo, FIFA, player, match, and model fields.
- Local database has one Elo snapshot, one FIFA snapshot, one FIFA squad import, 1,254 players, and 48 coaches.
- `python -m scripts.validate_squad_ingestion` passes required checks locally, with warnings only:
  - one team below 20 players
  - two teams above 26 players
  - height and DOB fill rates are 99.5%
  - coach coverage is 48 teams
- Squad/player APIs expose FIFA squad PDF fields: name, position, club, shirt number, DOB, height, caps, goals, coach.
- ML feature code uses squad-derived signals through `_get_player_strength_stats`, including positional unit strength, depth, availability, average caps, total international goals, and weighted player strength.
- Local password verification for `test@example.com / testtest` succeeds against the existing database.

## What Is Broken Or Weak

- Homepage does not match the requested messaging. It mentions Elo/xG/Monte Carlo but omits FIFA rankings, squad PDF data, named ML models, statistical simulation details, and the full bracket-stage scope.
- Homepage redirects authenticated users to `/dashboard`, which prevents signed-in users from reading the explanatory homepage.
- Homepage links do not use the requested labels and do not directly point to bracket, prediction, and team exploration.
- Data freshness UI is named `data-freshness.tsx`, not `DataFreshnessCard.tsx`, and compact mode hides several required fields.
- Data freshness frontend formats timestamps with `toLocaleString(undefined, ...)`. Because the component is client-only this is not an SSR mismatch by itself, but it is locale/time-zone dependent and not deterministic.
- `GET /api/v1/ratings/elo/latest` falls back to `teams.elo` when no versioned Elo snapshot exists and labels that fallback as `teams.elo`. This is display-safe, but the source metadata is not clear enough that it is a cached team-table fallback rather than a true current Elo source.
- `GET /api/v1/rankings/fifa/latest` returns 404 when no FIFA snapshot exists. The task allows safe fallback behavior, so tests should cover either loaded data or a safe error shape.
- Backend login accepts OAuth2 form data only (`username` + `password`). The task's manual curl sends JSON (`email` + `password`), which currently returns 422.
- No `scripts.seed_test_user` module exists. The current local DB already has the user, but new dev/test databases need an idempotent safe seed command.
- Login frontend stores tokens and updates the navbar after successful form login, but error copy passes raw backend messages through.

## Hydration Findings

- The reported attribute `data-dashlane-rid` is consistent with Dashlane extension injection, not app code.
- App-code hydration risks found:
  - Locale date formatting in `components/data-freshness.tsx`.
  - `typeof window !== "undefined"` branch in `app/saved/page.tsx` inside render. It can render different text on server and client if the page is prerendered.
  - Chart components are client pages/components and are less likely to SSR differently, but Recharts should continue to stay in client components.
- No app source was found using `Date.now()` or `Math.random()` during render.

## Why `test@example.com / testtest` Fails

- In the inspected local DB, the user exists, is active, has a password hash, and `verify_password("testtest", hash)` returns true.
- Backend form login through TestClient returns 200 for `data={"username":"test@example.com","password":"testtest"}`.
- Backend JSON login through TestClient returns 422 for `json={"email":"test@example.com","password":"testtest"}` because the route only depends on `OAuth2PasswordRequestForm`.
- If the browser login fails while form login works, the likely causes are:
  - frontend points at a different backend/database than the inspected DB,
  - backend is not running at the expected `/backend/api/v1` rewrite target,
  - user is absent in that runtime database,
  - or CORS/rewrite configuration differs from local dev.

## Files That Must Change

- `wcip-frontend/app/page.tsx`
- `wcip-frontend/components/DataFreshnessCard.tsx` (new)
- `wcip-frontend/components/data-freshness.tsx`
- `wcip-frontend/lib/types.ts`
- `wcip-frontend/lib/api.ts`
- `wcip-frontend/app/login/page.tsx`
- `wcip-backend/app/api/v1/auth.py`
- `wcip-backend/scripts/seed_test_user.py` (new)
- `wcip-backend/tests/test_auth.py`
- `wcip-backend/tests/test_realtime_data.py` or a focused freshness/rating test file
- Documentation: `README.md`, `docs/MEMORY.md`, `docs/REPO_CHECKLIST.md`, `docs/DATA_PIPELINE.md`

## Proposed Fix Summary

- Replace homepage copy with the requested hero and six prediction-tool cards, linked to bracket, prediction, and teams.
- Preserve links to the full bracket page instead of duplicating the bracket UI on the homepage.
- Add a deterministic `DataFreshnessCard.tsx` and keep `DataFreshnessStrip` as a compatibility wrapper.
- Format dates using a fixed UTC formatter after mount, or a deterministic ISO fallback before mount.
- Make backend login accept both OAuth2 form (`username`) and JSON (`email`) safely.
- Add an idempotent development/test-only `python -m scripts.seed_test_user` command.
- Improve login error copy and make frontend login call the JSON shape that matches the task curl.
- Tighten Elo fallback metadata and add backend tests for login, seed, Elo latest, FIFA latest, and freshness ISO fields.
