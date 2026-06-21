# Hydration, RAG, and Squad Audit

Date: 2026-06-21

## Scope

This audit covers the reported `/wc2026` hydration mismatch, `AskAnalystBox`, `app/wc2026/page.tsx`, data freshness UI, chart/RAG components, team and squad API hooks, Bosnia and Herzegovina team/player records, squad PDF parsing/loading, validation scripts, RAG edge cases, and README updates.

## Hydration Audit

### Reported Error

The warning points at `components/AskAnalystBox.tsx` around:

```tsx
<div className="flex gap-2">
```

The reported server/client diff includes `data-dashlane-rid="..."`.

### Likely Root Cause

`data-dashlane-rid` is injected by the Dashlane browser extension into form-related DOM nodes before React hydrates. `AskAnalystBox` renders an input and button at the reported location, so it is a natural target for Dashlane. The component itself is already a client component and does not use `Date.now()`, `Math.random()`, `window`, `localStorage`, dynamic IDs, or locale formatting during render.

Conclusion: the reported mismatch is most likely browser-extension caused, not app-code caused.

### App-Side Hydration Risks Checked

- `components/AskAnalystBox.tsx`: deterministic initial render; only `useState`; no browser-only APIs during render.
- `app/wc2026/page.tsx`: client component using query hooks; date display uses `toISOString().slice(0, 10)` rather than locale rendering.
- `DataFreshnessStrip` / `DataFreshnessCard`: client component; formats timestamps with UTC components, avoiding locale/timezone drift.
- Chart components under WC pages and team pages: client components; no server-only chart rendering found.
- RAG components: client components; use local state only. `RagAnswerCard` derives confidence percent deterministically from API data.
- Frontend search found `toLocaleString()` in several client components. Those can still differ across browsers/locales, but they are not used in `AskAnalystBox` and are not SSR-critical in the reported node.
- `components/ui/input.tsx` and `components/ui/button.tsx` already use `suppressHydrationWarning`, likely from a prior extension-injection mitigation. This should not be broadened unless the only remaining mismatch is confirmed extension attributes.

### Verification Limit

I cannot disable the user's Dashlane extension from this shell. The correct manual verification is to open `/wc2026` in a browser profile or incognito/private window with Dashlane/extensions disabled. If the warning disappears, it confirms extension injection.

## Bosnia and Herzegovina Squad Audit

### Database Findings

Canonical aliases currently resolve as:

- `Bosnia and Herzegovina` -> `Bosnia and Herzegovina`
- `Bosnia-Herzegovina` -> `Bosnia and Herzegovina`
- `Bosnia & Herzegovina` -> `Bosnia and Herzegovina`
- `BIH` -> `Bosnia and Herzegovina`
- `Bosnia And Herzegovina` -> `Bosnia And Herzegovina`

The last alias is the bug.

The local DB contains:

- `teams`: `Bosnia and Herzegovina` with code `BIH`
- `qualified_teams`: `Bosnia and Herzegovina`, group `B`
- `players`: 26 real FIFA squad players under `Bosnia And Herzegovina`
- `players`: one placeholder row under `Bosnia and Herzegovina`
- `coaches`: one placeholder coach under `Bosnia and Herzegovina`

Representative real player rows under the wrong alias include Nikola Vasilj, Sead Kolasinac, Amar Dedic, and other parsed PDF players. The UI/API fetches canonical `Bosnia and Herzegovina`, so it only sees the placeholder row.

### Root Cause

The PDF parser preserves the team header casing from extracted text. The loader calls `canonical(p.team_name)`, but `etl/transform/normalize.py` does not map case variant `Bosnia And Herzegovina`, because the direct and case-insensitive lookup compare against only configured aliases and no configured key matches that title-case `And` variant.

### Files Needing Changes

- `wcip-backend/etl/transform/normalize.py`: add Bosnia title-case and additional aliases.
- `wcip-backend/etl/players/load_squad_pdf.py`: ensure player/coach upsert uses canonical names and removes/replaces placeholder rows when real rows exist for a team.
- `wcip-backend/scripts/validate_squad_ingestion.py`: enforce 48 teams, all teams with players, Bosnia players and coach, valid teams, duplicates, positions, numeric fields.
- `wcip-backend/app/api/v1/teams.py`: make team player lookups canonical/alias tolerant and return clear squad-not-found shape when appropriate.
- `wcip-backend/app/api/v1/world_cup.py`: same canonical lookup behavior for `/world-cup/players/{team_name}` and detail counts.
- Frontend squad displays: ensure incomplete/empty/error states are friendly and not blank.

## RAG Audit

RAG is structurally separate from prediction engines. `rag.generator` explicitly says RAG does not determine winners and appends a disclaimer.

Potential edge cases:

- Empty index returns no chunks and currently generates a clear low-confidence answer.
- Retrieval with a restrictive `context_type` or `team_id` falls back to all chunks, but warnings do not always say that context may be incomplete.
- RAG query logging is best-effort and rolls back on failure.
- Admin index rebuild is protected by `AdminUser`.
- Source generation must not index secrets. This should be covered by checking `rag.sources`.

Files needing changes:

- `rag/generator.py`: strengthen no-data/incomplete warnings, especially for missing team/squad data and prediction/bracket questions.
- `rag/retriever.py`: add Bosnia/team alias token expansion so `Bosnia and Herzegovina` and `BIH` retrieve the same documents.
- RAG tests: empty index, no matching chunks, Bosnia squad query, prediction explanation query, bracket query, unauthorized admin index rebuild.

## Prediction and Simulation Validation Audit

The previous probability fix standardized winner prediction probabilities to fractions. Additional validation should cover:

- champion probabilities finite, nonnegative, <= 1, and sum close to 1
- match probabilities finite and sum close to 1
- bracket replay does not advance eliminated teams
- third-place match uses only semi-final losers
- missing squad data does not crash predictions

Existing tests cover part of this, but more edge-case tests should be added around simulation payloads.

## README Audit

README needs updates for:

- final frontend routes
- hydration troubleshooting and Dashlane/browser extension note
- squad PDF ingestion and validation commands
- Bosnia and Herzegovina alias handling
- RAG as explanation-only
- prediction/simulation validation rules
- local startup/test commands
- known limitations
