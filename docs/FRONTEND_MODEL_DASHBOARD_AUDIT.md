# Frontend Model Dashboard Audit

Date: 2026-06-13

## Root Cause

The `/models` page fetches `/api/v1/ml/models`, filters rows by `is_active`, and renders every active registry row directly. The backend model registry can contain more than one active row for the same `model_name` across versions or weighting passes. Because the frontend does not deduplicate by normalized model name and latest active version, each ML model can appear twice.

The duplicated weight pattern is caused by the page treating every returned `ensemble_weight` as the same kind of weight. Older/current ML-only weights and final hybrid ensemble contribution rows can both be present, so the dashboard shows one band around 16-17% and another around 3% for the same model family.

## Files Affected

- `wcip-frontend/app/models/page.tsx`
- `wcip-frontend/lib/types.ts`
- `wcip-frontend/lib/api.ts`
- `wcip-frontend/package.json`
- `wcip-frontend/next.config.mjs`

## Proposed Fix

1. Normalize model names and select one latest active row per ML model family.
2. Treat the displayed model-card weight as ML-only weight.
3. Calculate final hybrid ensemble contribution separately from the ML weight using the configured statistical-vs-ML blend.
4. Render the statistical engine in its own section instead of mixing it into the ML model list.
5. Add unique static descriptions keyed by normalized model name, merged into API data once at render time.
6. Update the production build script to use the stable webpack builder because Turbopack fails in the current sandbox while processing CSS.
7. Replace the obsolete `next lint` script with a real ESLint command.
