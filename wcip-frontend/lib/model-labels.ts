// Display names for prediction methods and ML models. Kept outside the chart
// component so importing labels does not pull recharts into a page bundle.
export const MODEL_LABELS: Record<string, string> = {
  elo: "Elo",
  fifa: "FIFA",
  player_strength: "Player Strength",
  statistical: "Statistical",
  ml: "ML Average",
  logistic: "Logistic",
  random_forest: "Rnd Forest",
  xgboost: "XGBoost",
  lightgbm: "LightGBM",
  catboost: "CatBoost",
  ensemble: "Ensemble",
};
