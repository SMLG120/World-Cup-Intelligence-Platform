// Types mirroring the backend Pydantic schemas (app/schemas/*).

export interface User {
  id: number;
  email: string;
  full_name: string | null;
  role: "user" | "admin";
  is_active: boolean;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Team {
  id: number;
  name: string;
  code: string;
  confederation: string;
  elo: number;
  fifa_rank: number;
}

export interface EloPoint {
  rating: number;
  opponent: string | null;
  recorded_at: string;
}

export interface TeamModifiers {
  attack: number;
  defence: number;
  injury: number;
  morale: number;
  fatigue: number;
  chemistry: number;
  coaching: number;
}

export const NEUTRAL_MODIFIERS: TeamModifiers = {
  attack: 1, defence: 1, injury: 1, morale: 1, fatigue: 1, chemistry: 1, coaching: 1,
};

export interface MatchProbabilities {
  home_win: number;
  draw: number;
  away_win: number;
}

export interface PredictionFactor {
  name: string;
  detail: string;
  impact: number;
}

export interface MatchPrediction {
  home: string;
  away: string;
  probabilities: MatchProbabilities;
  home_xg: number;
  away_xg: number;
  explanation: string;
  factors: PredictionFactor[];
}

export interface TeamProbability {
  team: string;
  champion: number;
  final: number;
  semi: number;
  quarter: number;
  round_of_32?: number;
  round_of_16: number;
  expected_finish: number;
  champion_ci_low: number;
  champion_ci_high: number;
}

export interface TournamentResult {
  edition: string;
  runs: number;
  seed?: number | null;
  deterministic?: boolean;
  teams: TeamProbability[];
}

export interface ScenarioResult {
  label: string;
  result: TournamentResult;
}

export interface ScenarioComparison {
  edition: string;
  runs: number;
  scenarios: ScenarioResult[];
}

export interface Simulation {
  id: number;
  public_token: string;
  name: string;
  kind: string;
  status: "pending" | "running" | "completed" | "failed";
  params: Record<string, unknown>;
  result: TournamentResult | null;
  is_public: boolean;
  created_at: string;
  completed_at: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminAnalytics {
  users: number;
  simulations: number;
  simulations_by_status: Record<string, number>;
}

// ─── Phase 2: ML + World Cup 2026 types ─────────────────────────────────────

export interface MLOutcome {
  home_win: number;
  draw: number;
  away_win: number;
}

export interface ExplanationFactor {
  name: string;
  display_name: string;
  value: number;
  impact: number;
}

export interface PredictionExplanation {
  top_positive: ExplanationFactor[];
  top_negative: ExplanationFactor[];
  shap_values: number[];
  narrative: string;
}

export interface HybridPrediction {
  home_team: string;
  away_team: string;
  match_date: string;
  statistical: MLOutcome;
  ml_predictions: Record<string, MLOutcome>;
  ensemble: MLOutcome;
  home_xg: number;
  away_xg: number;
  expected_scoreline: string;
  confidence_score: number;
  model_agreement: number;
  model_weights_used?: Record<string, number>;
  feature_values_used?: Record<string, number>;
  explanation: PredictionExplanation;
}

export interface MLModel {
  id: number;
  model_name: string;
  version: string;
  accuracy: number | null;
  f1_score: number | null;
  brier_score: number | null;
  log_loss: number | null;
  calibration_score: number | null;
  ensemble_weight: number;
  training_samples: number | null;
  feature_version: string;
  is_active: boolean;
  trained_at: string | null;
}

export interface FeatureVector {
  home_team: string;
  away_team: string;
  match_date: string;
  feature_version: string;
  features: Record<string, number>;
}

export interface QualifiedTeam {
  team_name: string;
  team_code: string;
  confederation: string;
  group_label: string | null;
  pot: number | null;
  host_nation: boolean;
  confirmed: boolean;
  qualification_path: string | null;
}

export interface WC2026Groups {
  year: number;
  draw_complete: boolean;
  groups: Record<string, string[]>;
  total_qualified: number;
  qualification_status: { confirmed: number; total_slots: number };
}

export interface WC2026Simulation {
  year: number;
  runs: number;
  seed?: number | null;
  deterministic?: boolean;
  draw_complete: boolean;
  teams: TeamProbability[];
}

export interface WorldCupWinnerPrediction {
  rank: number;
  team_id: number | null;
  team_name: string;
  seed?: number | null;
  deterministic?: boolean;
  fifa_code: string;
  group: string | null;
  confederation: string;
  fifa_rank: number;
  champion_probability: number;
  final_probability: number;
  semifinal_probability: number;
  quarterfinal_probability: number;
  round_of_16_probability: number;
  group_qualification_probability: number;
  expected_finish: number;
  confidence_interval_low: number;
  confidence_interval_high: number;
  statistical_probability: number;
  ml_probability: number;
  ensemble_probability: number;
  explanation: string;
}

export interface TeamDetail {
  team_name: string;
  elo: number;
  fifa_rank: number;
  confederation: string | null;
  attack: number;
  defence: number;
  chemistry: number;
  form_ppg: number;
  squad_stats: {
    avg_age: number;
    market_value_log: number;
    injury_burden: number;
    avg_fitness: number;
  };
  coach: {
    name: string | null;
    formation: string | null;
    win_pct: number | null;
    impact_score: number;
    data_source?: string | null;
  };
  squad_size: number;
  injured_count: number;
  suspended_count: number;
}

export interface Player {
  id: number;
  name: string;
  team_name?: string;
  position: string;
  club: string | null;
  age: number | null;
  nationality?: string | null;
  goals: number;
  assists: number;
  xg: number;
  xag: number;
  minutes_played: number;
  international_caps: number;
  international_goals: number;
  injured: boolean;
  suspended: boolean;
  fitness_score: number;
  recent_form_score?: number;
  data_source?: string | null;
  market_value_eur: number | null;
}
