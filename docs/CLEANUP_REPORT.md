# Cleanup Report

**Date:** 2026-06-21

## Files / Directories Removed

| Item | Reason |
|------|--------|
| `wcip-backend/**/__pycache__/` (1,310 dirs) | Python bytecode cache — regenerated automatically |
| `wcip-backend/.pytest_cache/` | Pytest cache — regenerated on next test run |
| `wcip-frontend/.next/` | Next.js build output — regenerated on next build |

## .gitignore Updated

Added to root `.gitignore`:
- `DATA_SECURITY_AUDIT.md`
- `FRONTEND_NAVIGATION_AUDIT.md`
- `world_cup_2026_audit.md`
- `BRACKET_SIMULATION_AUDIT.md`
- `RAG_AND_CLEANUP_AUDIT.md`
- `CLEANUP_REPORT.md`

These audit documents are local working files and not intended for version control.

## Files Left Untouched

| File | Reason |
|------|--------|
| `wcip-backend/data/external/fifa_wc2026_squad_lists_english.pdf` | Primary RAG data source |
| `wcip-backend/data/external/fifa_wc2026_squad_players.csv` | Derived player CSV |
| `wcip-backend/models/*.pkl` | Trained ML models — expensive to regenerate |
| `wcip-backend/wcip.db` | Local dev database |
| All `.env` / `.env.example` files | Config files — `.env` is gitignored, `.env.example` is safe |
| `wcip-backend.zip` / `wcip-frontend.zip` | Matched by `*.zip` in .gitignore — not committed |

## Duplicates Identified (Not Removed — Requires Manual Review)

| Issue | Files |
|-------|-------|
| Two WC2026 seed scripts | `etl/world_cup_2026/seed_data.py` vs `etl/world_cup_2026_seed.py` |
| Two player CSV importers | `etl/players/csv_import.py` vs `etl/player_ratings/csv_import.py` |
| Duplicate Elo ETL | `etl/elo/` vs `etl/extract/elo_ratings.py` |
| Legacy frontend pages | `/world-cup/` vs `/wc2026/`, `/simulate/` vs `/wc2026/simulate/` |
| Legacy engine | `wcip/engine/` vs `app/services/prediction.py` |
