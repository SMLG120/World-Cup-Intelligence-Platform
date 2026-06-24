# Data Requirements

Generated: 2026-06-24

## Real Table Names

The project does not use generic `data_sources`, `data_freshness`, or `etl_runs`
tables. Freshness is derived from source/import log tables and data timestamps.

| Requested concept | Actual table(s) |
|---|---|
| teams | `teams`, `qualified_teams` |
| players | `players` |
| coaches | `coaches` |
| matches | `match_results`, `match_features` |
| groups | `qualified_teams.group_label` |
| users | `users`, `audit_logs` |
| elo_ratings | `team_elo_ratings`, legacy `elo_history` |
| elo_rating_snapshots | `elo_rating_snapshots` |
| fifa_rankings | `fifa_ranking_entries`, `team_rankings` |
| fifa_ranking_snapshots | `fifa_ranking_snapshots` |
| player_ratings | `players.player_rating`, `player_rating_records` |
| model_metadata | `ml_models` |
| prediction_snapshots | `ml_models.data_snapshot_version`, freshness snapshot payloads |
| simulations | `simulations`, `simulation_runs`, `saved_scenarios` |
| rag_documents | `rag_documents` |
| rag_chunks | `rag_chunks` |
| rag_embeddings | `rag_embeddings` |
| rag_queries | `rag_queries` |
| rag_answers | `rag_answers` |
| data_sources | `elo_source_logs`, `ranking_source_logs`, `player_rating_imports` |
| data_freshness | derived by `/api/v1/data/freshness` |
| etl_runs | `elo_source_logs`, `ranking_source_logs`, `player_rating_imports` |
| source_logs | `elo_source_logs`, `ranking_source_logs`, `player_rating_imports` |

## Feature To Data Mapping

| Frontend feature | Required backend data |
|---|---|
| Data Freshness card | `elo_rating_snapshots`, `fifa_ranking_snapshots`, `players`, `player_rating_imports`, `match_results`, `ml_models`, `elo_source_logs`, `ranking_source_logs` |
| Teams page | `qualified_teams`, `teams`, `players`, `coaches` |
| Team detail page | `teams`, `players`, `coaches`, `elo_history`, `team_elo_ratings` |
| Models page | `ml_models`, feature pipeline inputs from teams/rankings/players |
| Prediction page | `teams`, `elo_rating_snapshots`, `team_elo_ratings`, `fifa_ranking_snapshots`, `fifa_ranking_entries`, `players`, `coaches`, `ml_models` |
| Bracket simulation | `qualified_teams`, `teams`, ratings/rankings, player-strength features, simulation engine |
| RAG Ask Analyst | `rag_documents`, `rag_chunks`, `rag_embeddings`, plus source tables used by RAG indexing |

## Minimum Healthy WC2026 Production Data

| Data area | Minimum expected state |
|---|---|
| WC2026 field | 48 `qualified_teams` rows and matching `teams` rows |
| Squads | 48 teams, 1248 players when using the official 26-player squad list |
| Coaches | 48 coaches |
| Elo | one current `elo_rating_snapshots` row and many `team_elo_ratings` rows |
| FIFA | one current `fifa_ranking_snapshots` row and ranking entries |
| Player ratings | either imported legal ratings or explicit missing/partial status |
| Models | at least one active `ml_models` row for the model dashboard |
| RAG | indexed docs/chunks/embeddings if Ask Analyst is enabled |

## Required Bundled Source Files For Render

These files are small enough to ship with the backend and are allow-listed in
`.gitignore` so `python -m scripts.bootstrap_data` can populate a fresh Render
database without relying on a developer laptop:

| Source | Required file |
|---|---|
| Historical matches | `wcip-backend/data/cache/results.csv` |
| FIFA rankings fallback/cache | `wcip-backend/data/cache/fifa_rankings.json` |
| WC2026 squads/coaches | `wcip-backend/data/external/fifa_wc2026_squad_lists_english.pdf` |
| Player-rating proxy import | `wcip-backend/data/external/fifa_wc2026_squad_players.csv` |
| Elo ratings | `wcip-backend/data/processed/world_football_elo_ratings_2026_06_21.csv` |
| Model metadata/artifacts | `wcip-backend/models/*.pkl` |

## Player Ratings Rule

Do not fake ratings. If no licensed/manual `ea_player_ratings.csv` exists, the
app may use the official FIFA squad-list proxy generated from roster facts, but
it must label it clearly as `fifa_wc2026_squad_pdf` /
`fifa_roster_proxy_v1`.
