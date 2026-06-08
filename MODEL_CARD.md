# Model Card — World Cup Intelligence Platform

> Predictions are probabilistic simulations and should not be interpreted as certainty.
> This platform does not provide betting advice and does not encourage gambling.

---

## Purpose

The ML ensemble in this platform predicts three-class outcomes for international
football matches: **home win**, **draw**, or **away win**. Predictions are combined
with a statistical engine (Elo + Poisson) in a weighted ensemble to produce calibrated
probability estimates used for tournament simulation, scenario analysis, and educational
exploration of World Cup 2026.

---

## Intended Use

- Educational exploration of match prediction methodology
- Probabilistic tournament simulation for fan engagement
- Comparing statistical vs ML vs ensemble prediction approaches
- Teaching feature engineering, time-series cross-validation, and SHAP explainability

## Non-Intended Use

- Betting or wagering decisions of any kind
- Commercial sports intelligence without proper data licensing
- Real-time in-play prediction (the model uses pre-match features only)
- Player-level performance prediction (squad features are aggregated, not individual)

---

## Training Data

| Property | Value |
|---|---|
| Source | martj42 international_results dataset (CC BY-SA 4.0) |
| Total historical rows | 49,304 at v20260604 training; 49,306 local rows observed on 2026-06-08 |
| Training window | 2000-01-01 to 2026-06-04 |
| Training samples | 25,243 matches |
| Unique national teams | 327 |
| Outcome distribution | Home win 48.2% / Draw 22.3% / Away win 27.8% |
| Feature version | v1 (17 features) |

The training window starts at 2000-01-01 to reduce the influence of pre-modern
football conditions (different fitness, travel, tactics) while still capturing
sufficient sample size. Matches before this date are retained in the database for
Elo history computation but excluded from ML training.

**Outcome class imbalance note:** Home wins (48%) outnumber draws (22%) and away wins
(28%) because this dataset includes all international matches, not just neutral-venue
fixtures. The class imbalance is not corrected by oversampling — models are expected
to output calibrated probabilities rather than to maximise balanced accuracy.

---

## Feature Set (v1 — 17 features)

All features are (home − away) differentials. Positive = favours home team.

| Feature | Description | Data Source |
|---|---|---|
| `elo_diff` | Elo rating gap | eloratings.net via ETL |
| `fifa_rank_diff` | FIFA rank gap (inverted: positive = home team ranked higher) | Versioned FIFA ranking snapshots |
| `xg_diff` | Mean xG last 10 matches | `match_results` aggregation |
| `xga_diff` | Mean xGA last 10 (negative = better defence) | `match_results` aggregation |
| `goals_scored_diff` | Mean goals scored last 10 | `match_results` aggregation |
| `goals_conceded_diff` | Mean goals conceded last 10 | `match_results` aggregation |
| `form_diff` | Points from last 5 competitive matches | `match_results` aggregation |
| `avg_age_diff` | Mean squad age | `players` table (defaults 0 if empty) |
| `market_value_diff` | log10(market value) gap | `players` table (defaults 0 if empty) |
| `injury_burden_diff` | Injured/suspended starters ratio | `players` table (defaults 0 if empty) |
| `coach_impact_diff` | Coach impact score | `coaches` table (defaults 0 if empty) |
| `squad_chemistry_diff` | Proportion from same club | `players` table (defaults 0 if empty) |
| `travel_distance_km` | Home team km to venue | Geolocation estimate |
| `rest_days` | Days since home team's last match | `match_results` date diff |
| `tournament_exp_diff` | World Cup appearances | `teams` metadata |
| `starting_xi_strength_diff` | Mean Elo contribution of starting XI | `players` stats |
| `bench_strength_diff` | Mean Elo contribution of bench | `players` stats |

**Important:** The `players` and `coaches` tables are schema-complete but empty until
football-data.org ETL runs with a valid API key. In that state, features 7–11 and 15–16
default to 0. This reduces their signal contribution but does not invalidate predictions
— the model was trained on the same feature space where those values default to 0 when
player data is unavailable.

**Ranking leakage guardrail:** Historical feature generation reads the latest
stored FIFA ranking snapshot with `ranking_date <= match_date`. If no historical
snapshot exists for that match date, `fifa_rank_diff` falls back to a neutral
value rather than using the current ranking. Elo uses the same point-in-time
pattern through `elo_history`.

---

## Models

### Logistic Regression

```
sklearn.linear_model.LogisticRegression
  solver: lbfgs
  max_iter: 1000
  C: 1.0
  Wrapped in Pipeline(StandardScaler → LogisticRegression)
```

Provides a linear baseline. `StandardScaler` is required because LBFGS converges
poorly on unscaled features spanning very different ranges (Elo diffs ~0–2000 vs
form diffs ~0–15).

### Random Forest

```
sklearn.ensemble.RandomForestClassifier
  n_estimators: 300
  max_depth: 8
  min_samples_leaf: 10
  n_jobs: -1
  random_state: 42
```

`min_samples_leaf=10` prevents overfitting on small leaf nodes given the ~25K training
set size. `max_depth=8` limits model complexity.

### XGBoost

```
xgboost.XGBClassifier
  n_estimators: 300
  max_depth: 5
  learning_rate: 0.05
  objective: multi:softprob
  num_class: 3
  random_state: 42
```

### LightGBM

```
lightgbm.LGBMClassifier
  n_estimators: 300
  max_depth: 5
  learning_rate: 0.05
  objective: multiclass
  num_class: 3
  random_state: 42
```

### CatBoost

```
catboost.CatBoostClassifier
  iterations: 300
  depth: 5
  learning_rate: 0.05
  loss_function: MultiClass
  random_seed: 42
  verbose: 0
```

---

## Evaluation Metrics

### Cross-Validation Results (5-fold time-series CV, training date: 2026-06-04)

| Model | Accuracy | F1 (macro) | Brier Score | Log-Loss | Calibration (ECE) | Ensemble Weight |
|---|---|---|---|---|---|---|
| CatBoost | 57.92% | 0.5007 | 0.181 | 0.9196 | 0.9811 | 20.11% |
| Random Forest | 57.85% | 0.4970 | 0.181 | 0.9221 | 0.9786 | 20.06% |
| Logistic Regression | 57.68% | 0.4954 | 0.182 | 0.9229 | 0.9826 | 20.04% |
| XGBoost | 57.23% | 0.5021 | 0.183 | 0.9282 | 0.9761 | 19.92% |
| LightGBM | 57.29% | 0.5037 | 0.183 | 0.9306 | 0.9758 | 19.87% |

**Metrics explanation:**
- **Accuracy** — fraction of matches where the predicted modal outcome was correct
- **F1 (macro)** — macro-averaged F1 across all three classes; penalises ignoring draws
- **Brier Score** — mean squared probability error (lower is better; 0 = perfect, 1 = worst)
- **Log-Loss** — cross-entropy of predicted probabilities (lower is better; < 1.0 for three-class is good calibration)
- **Calibration (ECE)** — Expected Calibration Error approximation; values near 1.0 indicate reliable probabilities

All five models perform within a narrow band (~0.7% accuracy spread). The log-loss
spread drives the ensemble weighting, giving CatBoost a marginal edge.

### Ensemble Performance

The 30/70 statistical/ML blend consistently narrows the gap between models and the
statistical baseline without sacrificing calibration. On Argentina vs France (held-out
example): statistical 51.3% / 24.5% / 24.2%, ensemble 59.9% / 22.7% / 17.3%.

### Ranking Audit Note

The stored `v20260604` models were trained before the FIFA ranking snapshot
pipeline and point-in-time ranking lookup were added. During the June 2026 audit,
the local `teams` table had Brazil ranked #1, while the current official FIFA
men’s ranking publication identified France as #1 and Brazil as #6. The old
models should therefore be treated as a baseline until official ranking snapshots
are ingested, historical ranking snapshots are backfilled where possible, and
the ensemble is retrained.

---

## Model Selection Process

1. All five models are trained on the same 17-feature matrix with the same time-series CV
2. Per-fold log-loss is recorded; means are used for ensemble weighting
3. `ensemble_weight = (1 / log_loss) / Σ(1 / log_loss_j)` — normalised inverse log-loss
4. Weights are re-normalised to sum to 1.0 in `ml_models` table after each retrain
5. On prediction, weights are read from the DB so adding a new model automatically
   adjusts all existing weights

---

## Known Biases and Limitations

**Home advantage conflation.** Because ~74% of training matches are played on
a designated "home" team's territory, the differential feature format bakes in a
home advantage signal. The model does not separately estimate neutral-venue
home advantage vs genuine quality gap.

**Draw prediction difficulty.** International football draws are inherently hard to
predict from pre-match features. The training data has a 22.3% draw rate, but model
F1 for the draw class is lower than for win/loss. All five models show draw
under-confidence.

**Player/coach feature sparsity.** Eight of the 17 features (avg_age, market_value,
injury_burden, coach_impact, squad_chemistry, travel_distance, starting_xi_strength,
bench_strength) require populated player/coach tables. Until football-data.org ETL
runs, these features default to 0, reducing model signal for those dimensions.

**No recent-form look-ahead.** The model uses the 10-match rolling average at the
time of prediction. For a tournament starting in June 2026, the last competitive
matches may be from March 2026 qualifiers — a 3-month gap. This reduces form signal
accuracy for tournament predictions.

**Pre-2000 data exclusion.** Matches before 2000-01-01 are excluded from training.
This removes ~24,000 historical matches. The exclusion is intentional (pre-modern
football conditions differ significantly) but means the model has not seen many
historical upsets.

**Small sample sizes for some nations.** 327 unique home teams are in the dataset,
but many have played fewer than 50 matches since 2000. Elo and form estimates for
these teams carry higher uncertainty.

**No player-level transfer or injury tracking.** The player table stores the last
known state. Late team news (injury in final training session, late call-ups) is not
automatically reflected unless the player record is updated via the API before prediction.

**Historical ranking coverage.** The new ranking pipeline versions snapshots
going forward. Older FIFA ranking publications need a backfill before
`fifa_rank_diff` can carry historical signal for all training rows. Until then,
missing historical periods use neutral ranking values to avoid data leakage.

---

## Known Failure Cases

- **Major upsets** — All five models under-weight low-probability outcomes. A
  team rated 300+ Elo points below the opponent will rarely have predicted win
  probability above 10%, regardless of current form.
- **Debut teams / very new qualifiers** — Teams that qualified via playoffs with few
  matches since 2000 have sparse match_results data. Form and xG features will be
  at their defaults.
- **Tournament-specific conditions** — The model was trained on all international
  matches (including friendlies), not exclusively on tournament matches. Friendly
  form is given equal weight to competitive results unless `is_competitive` filtering
  is applied in the feature engineering query.

---

## Retraining Schedule

| Trigger | Command | Description |
|---|---|---|
| Admin API | `POST /api/v1/ml/retrain {"model": "all"}` | Incremental retrain on new data |
| Ranking monitor | `check_fifa_ranking_update(trigger_retraining=True)` | Retrain after material FIFA ranking movement |
| Manual | `python -m ml.train --model all` | Full retrain from CLI |
| Full refresh | `python -m ml.train --model all --full-refresh` | Re-reads all history |

Recommended cadence:
- After each major international window (every ~3 months)
- After loading a new batch of historical results via ETL
- After a material FIFA ranking snapshot update
- After historical FIFA ranking or Elo snapshots are backfilled

---

## Version History

| Version | Training Date | Samples | Notes |
|---|---|---|---|
| v20260604 | 2026-06-04 | 25,243 | Initial production training; 5-model ensemble activated |

All model versions are retained in `ml_models` with `is_active` flags. To roll back
to a previous version, set `is_active=false` on the current version and `is_active=true`
on the target version. The ensemble weight calculation will update on next prediction.

---

## Package Versions (as of training date)

| Package | Version |
|---|---|
| scikit-learn | 1.9.0 |
| xgboost | 3.2.0 |
| lightgbm | 4.6.0 |
| catboost | 1.2.10 |
| shap | 0.52.0 |
| numpy | ≥ 1.26 |
| pandas | ≥ 2.1 |
| Python | 3.14 |

---

## Data Source Licensing

| Source | License | Restriction |
|---|---|---|
| martj42 international_results | CC BY-SA 4.0 | Attribution required; share-alike |
| eloratings.net | Public data | Attribution requested; no scraping restriction documented |
| football-data.org | Free tier ToS | Rate-limited; commercial tiers for production use |
| FIFA Rankings | Public display data | Ingest from FIFA ranking page/schedule payload; preserve source URL, schedule id, and snapshot hash |
