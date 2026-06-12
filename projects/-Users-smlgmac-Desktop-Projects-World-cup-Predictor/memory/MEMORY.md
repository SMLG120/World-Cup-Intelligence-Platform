# Project Memory Index

- [Project Architecture](project_architecture.md) — Full stack overview, what's built and where
- [Data Sources & ETL](etl_data_sources.md) — All data sources, ETL state, DB counts, known issues
- [ML Model Registry](ml_model_registry.md) — Trained models, metrics, ensemble weights, feature version

Current WC2026 status is captured in `etl_data_sources.md`: official 48-team
groups are loaded, and startup player/coach records are placeholders until a
verified squad snapshot import replaces them.

Current FIFA ranking status is captured in `etl_data_sources.md` and
`ml_model_registry.md`: rankings are now versioned through
`fifa_ranking_snapshots` and `fifa_ranking_entries`; `teams.fifa_rank` is only a
current display cache. The June 2026 audit found Brazil incorrectly stored as
local DB rank #1 while the latest official FIFA men's ranking publication showed
France #1 and Brazil #6.

Current winner-prediction status: `GET /api/v1/world-cup/2026/winner-predictions`
returns ranked 2026 champion predictions with statistical, ML-style, and
ensemble probabilities. Frontend pages use
`components/winner-predictions-section.tsx`.
