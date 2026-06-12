# API Reference

All backend routes are served under `/api/v1`. Interactive OpenAPI docs are
available at `http://localhost:8000/docs` while the FastAPI server is running.

## FIFA Rankings

The ranking API exposes versioned FIFA men's ranking snapshots. The latest
snapshot updates `teams.fifa_rank` for display, but historical snapshots remain
available for feature generation, backtesting, retraining, and reproducibility.

### Get Latest Snapshot

```http
GET /api/v1/rankings/fifa/latest?limit=50
```

Returns the current stored FIFA ranking snapshot and up to `limit` entries.

Response shape:

```json
{
  "ranking_id": "FRS_Male_Football_20260119",
  "ranking_date": "2026-04-01",
  "published_at": "2026-04-01T11:55:29.435000+00:00",
  "next_update_at": "2026-06-11T00:00:00+00:00",
  "source_url": "https://inside.fifa.com/fifa-world-ranking/men",
  "team_count": 211,
  "is_current": true,
  "entries": [
    {
      "team_name": "France",
      "team_code": "FRA",
      "confederation": "UEFA",
      "rank": 1,
      "previous_rank": 2,
      "rank_change": 1,
      "points": 1870.92,
      "previous_points": 1859.78,
      "points_change": 11.14
    }
  ]
}
```

### List Snapshots

```http
GET /api/v1/rankings/fifa/snapshots
```

Returns snapshot metadata without entry payloads.

### Get One Snapshot

```http
GET /api/v1/rankings/fifa/snapshots/{ranking_id}?limit=250
```

Returns one historical snapshot by FIFA ranking schedule id.

### Refresh Snapshot

```http
POST /api/v1/rankings/fifa/refresh?force_refresh=true&trigger_retraining=false
Authorization: Bearer <admin-token>
```

Starts a background refresh. When `trigger_retraining=true`, the monitor can run
the ML retraining workflow if the new ranking snapshot crosses material-change
thresholds.

## World Cup Winner Predictions

```http
GET /api/v1/world-cup/2026/winner-predictions?runs=5000&seed=12345
```

Returns ranked 2026 champion probabilities enriched with team metadata,
simulation outputs, ML-style strength probabilities, ensemble probabilities, and
short explanations.

Response shape:

```json
[
  {
    "rank": 1,
    "team_id": 12,
    "team_name": "France",
    "fifa_code": "FRA",
    "group": "Group I",
    "confederation": "UEFA",
    "fifa_rank": 1,
    "champion_probability": 14.2,
    "final_probability": 27.8,
    "semifinal_probability": 42.4,
    "quarterfinal_probability": 58.1,
    "round_of_16_probability": 73.5,
    "group_qualification_probability": 91.0,
    "expected_finish": 5.8,
    "confidence_interval_low": 12.9,
    "confidence_interval_high": 15.6,
    "statistical_probability": 13.1,
    "ml_probability": 15.0,
    "ensemble_probability": 14.2,
    "explanation": "France ranks here because of strong Elo, elite FIFA ranking, high player-strength rating."
  }
]
```

`champion_probability` and `ensemble_probability` are normalized percentages
that sum to approximately 100 across all returned teams.

Compatibility alias:

```http
GET /api/v1/world_cup/2026/winner-predictions?runs=5000&seed=12345
```

## ML And ETL

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/ml/models` | Active model registry, metrics, and ensemble weights |
| `GET` | `/ml/features` | Feature vector for a match |
| `GET` | `/ml/feature-names` | Feature names for the current feature version |
| `GET` | `/ml/explanations` | SHAP or fallback feature explanation |
| `POST` | `/ml/predict` | Hybrid statistical + ML prediction |
| `POST` | `/ml/train` | Admin model training trigger |
| `POST` | `/ml/retrain` | Admin retraining trigger |
| `POST` | `/ml/etl/run` | Admin ETL pipeline trigger |

Ranking-sensitive ML features use point-in-time lookups. Historical requests read
the latest stored ranking snapshot on or before the match date; current requests
use the latest stored snapshot or current team cache.

The active feature vector is `v2`. It keeps the original 17 fields first and
adds player rating, squad depth, position-unit strength, form, availability,
caps, goals, and weighted player strength fields.

## Core User Workflows

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/teams` | List teams |
| `GET` | `/teams/{id}` | Team detail |
| `GET` | `/players` | Player registry |
| `POST` | `/match/simulate` | Single-match statistical prediction |
| `POST` | `/tournament/simulate` | Monte Carlo tournament simulation |
| `POST` | `/scenario/compare` | Compare scenarios |
| `POST` | `/auth/register` | Create account |
| `POST` | `/auth/login` | Login |
| `GET` | `/auth/me` | Current user |

## World Cup 2026

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/world-cup/qualified-teams` | WC2026 qualified-team list |
| `GET` | `/world-cup/groups` | WC2026 groups |
| `GET` | `/world-cup/bracket` | Knockout bracket metadata |
| `POST` | `/world-cup/simulate` | WC2026 tournament simulation |
| `GET` | `/world-cup/schedule` | Schedule metadata |
| `GET` | `/world-cup/teams/{team_name}` | Team, squad, and coach detail |
| `GET` | `/world-cup/players/{team_name}` | Squad list |
