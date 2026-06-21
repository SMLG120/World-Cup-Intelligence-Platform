# Probability and Elo CSV Audit

Date: 2026-06-21

## Scope

This audit covers the winner prediction API, tournament simulation probability aggregation, Monte Carlo outputs, frontend probability formatting, the champion probability chart, dark-horse calculations, ensemble outputs, TypeScript normalization gaps, and the requested static World Football Elo PDF ingestion path.

## Exact Probability Root Cause

The impossible frontend values are caused by mixed probability units.

The backend winner prediction service in `wcip-backend/app/services/winner_predictions.py` currently converts winner prediction fields to percent-unit numbers with `_pct()`. For example, an internal ensemble probability of `0.14232` becomes the API value `14.232`.

The `/wc2026` frontend page imports `pct()` from `wcip-frontend/lib/utils.ts`, and that formatter assumes fraction-unit inputs from `0.0` to `1.0`. It multiplies by 100. Therefore the API value `14.232` is rendered as `1423.2%`.

The dedicated `WinnerPredictionsSection` component has its own local `pct()` formatter that does not multiply by 100, so the app currently has two incompatible frontend assumptions:

- `/wc2026` treats winner predictions as fractions.
- `components/winner-predictions-section.tsx` treats winner predictions as percent values.

The backend is also inconsistent with the rest of the tournament simulation API. `POST /world-cup/2026/simulate` returns team probabilities as fractions, and the simulation probability sanitizers in `world_cup.py` and `simulations.py` already normalize toward `0.0` to `1.0`.

## Audited Areas

### Backend Winner Prediction API

File: `wcip-backend/app/services/winner_predictions.py`

- Monte Carlo champion/final/semi/quarter values are generated as fractions.
- `_ml_strength_probabilities()` returns a normalized fraction distribution.
- `ensemble_probs` is normalized as a fraction distribution.
- The service then calls `_pct()` on `champion_probability`, `final_probability`, `semifinal_probability`, `quarterfinal_probability`, `round_of_16_probability`, `group_qualification_probability`, confidence intervals, `statistical_probability`, `ml_probability`, and `ensemble_probability`.
- `_normalize_percentage_field()` then rescales `champion_probability` and `ensemble_probability` to sum to `100.0`, confirming the public winner prediction API is percent-unit today.
- Existing backend tests expect the old percent contract by asserting champion totals between `99.9` and `100.1`.

Required change: make this API emit probability fractions, normalize champion/ensemble distributions to sum near `1.0`, and update tests to enforce no value above `1.0`.

### Tournament Simulation Aggregation

File: `wcip-backend/app/api/v1/world_cup.py`

- Tournament simulations return `TeamProbability` values as fractions.
- `champion_probability` on a single simulated bracket result is derived from the fraction table.
- Match-level probability sanitizers clamp and normalize values to fraction-unit outputs.

Required change: no broad rewrite. Keep this API fraction-based and only add metadata where useful.

### Monte Carlo Probability Calculation

Monte Carlo outputs are already fraction-based:

- `probs.champion`
- `probs.final`
- `probs.semi`
- `probs.quarter`
- `probs.round_of_16`
- confidence interval fields

Required change: do not convert Monte Carlo outputs to percentages in backend service responses.

### Model Ensemble Response

The ensemble calculation in `winner_predictions.py` blends statistical, ML, and uniform components as fractions. The calculation is sound as a distribution, but the response serializes it as percentages.

Required change: keep ensemble math as-is, return the raw normalized fraction, and validate the resulting distribution.

### Frontend Probability Formatting

File: `wcip-frontend/lib/utils.ts`

- Existing `pct(value)` multiplies by 100 and is correct for simulation fraction values.
- It is unsafe for legacy winner prediction API values like `14.232`.
- There is no shared defensive formatter that accepts both legacy percent-unit values and corrected fraction-unit values.

Required change: add `normalizeProbabilityValue(value)` and `formatProbability(value)` for user-facing probability labels. Use them for winner prediction UI. Keep `pct()` available for existing fraction-only paths that may include deltas.

### Champion Probability Chart

File: `wcip-frontend/components/winner-predictions-section.tsx`

- The chart currently expects percent-unit values.
- X-axis and tooltip formatting append `%` to raw values.
- Once the backend returns fractions, the chart must use `formatProbability()` for ticks and tooltips.

Required change: normalize incoming rows defensively, chart fraction values, and format labels with one multiply by 100.

### Dark Horse Calculation

Files:

- `wcip-frontend/components/winner-predictions-section.tsx`
- `wcip-frontend/app/wc2026/page.tsx`

The dedicated winner section currently filters dark horses with `champion_probability >= 1.25`, which only works when backend values are percentages. Under the corrected fraction contract this threshold must be `0.0125`.

The overview page slices ranks 6-10 and displays them with the fraction formatter, which caused the screenshot-level `1423.2%` bug when backend values were already percentages.

Required change: normalize prediction rows and use one shared display formatter.

### Raw Counts Displayed as Percentages

No evidence was found that raw simulation counts are being directly displayed as champion percentages in the inspected frontend or winner prediction service. The observed issue is unit double-multiplication, not raw count display.

### TypeScript Normalization

File: `wcip-frontend/lib/types.ts`

The `WorldCupWinnerPrediction` type defines numeric probability fields but does not document or enforce units. It also lacks the requested Elo metadata fields:

- `elo_rank_used`
- `elo_source`
- `elo_source_date`
- `elo_snapshot_version`

Required change: add optional Elo metadata fields and normalize at component boundaries.

## Probability Contract Decision

The source-of-truth internal and API format for probabilities will be `0.0` to `1.0`.

Backend:

- `normalize_probabilities()` will normalize nonnegative finite values into a distribution summing to `1.0`.
- `validate_probability_distribution()` will reject negative, nonfinite, above-1, and non-normalized probability distributions.
- Winner prediction response probability fields will be fractions.

Frontend:

- `normalizeProbabilityValue()` will defensively convert legacy percent-unit inputs above `1.0` into fractions.
- `formatProbability()` will display fraction-unit values as rounded percentages, clamped between `0%` and `100%`.
- Development builds will warn when legacy or invalid probability values are normalized.

## Elo PDF/CSV Audit

The user-provided file path is `/Users/smlgmac/Downloads/World Football Elo Ratings.pdf`; the task text names `World Football Elo Ratings(1).pdf`. The conversion script should accept an explicit input path and also try common default paths.

Required conversion output:

`wcip-backend/data/processed/world_football_elo_ratings_2026_06_21.csv`

Required top-six validation rows:

- Spain, rank 1, rating 2129
- Argentina, rank 2, rating 2128
- France, rank 3, rating 2084
- England, rank 4, rating 2055
- Colombia, rank 5, rating 1998
- Brazil, rank 6, rating 1986

The existing database schema already has:

- `elo_rating_snapshots`
- `team_elo_ratings`
- `elo_source_logs`

It does not have separate columns for every requested CSV audit field, so loader-specific metadata such as `raw_team_name`, `normalized_team_name`, `source_name`, `source_file`, `snapshot_version`, `ingested_at`, and `validation_status` should be preserved in `TeamEloRating.raw_payload` and `EloSourceLog.metadata_json` without destructive schema churn.

## Files Expected to Change

Backend:

- `wcip-backend/app/services/probabilities.py`
- `wcip-backend/app/services/winner_predictions.py`
- `wcip-backend/ml/features.py`
- `wcip-backend/scripts/convert_elo_pdf_to_csv.py`
- `wcip-backend/scripts/validate_elo_csv.py`
- `wcip-backend/etl/elo/load_elo_csv.py`
- Backend tests under `wcip-backend/tests/`

Frontend:

- `wcip-frontend/lib/utils.ts`
- `wcip-frontend/lib/types.ts`
- `wcip-frontend/components/winner-predictions-section.tsx`
- `wcip-frontend/app/wc2026/page.tsx`

Docs:

- `README.md`
- `docs/MEMORY.md`
- `docs/REPO_CHECKLIST.md`
- `docs/DATA_PIPELINE.md`
- `docs/MODEL_CARD.md`

## Remaining Risks Before Implementation

- OCR availability depends on installed local tools or Python libraries. The conversion script must fail clearly if the image-based PDF cannot be OCRed.
- Some frontend pages use `pct()` for simulation values and scenario deltas. Those should not be blindly migrated without checking whether negative deltas are expected.
- Prediction rows can still lack Elo snapshot data until the CSV is loaded and marked current; the response must tolerate missing metadata.
