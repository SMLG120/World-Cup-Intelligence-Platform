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
  fifa_code?: string | null;
  confederation: string;
  elo: number;
  elo_rating?: number | null;
  fifa_rank: number;
  fifa_ranking?: number | null;
  group?: string | null;
  group_label?: string | null;
  coach?: string | null;
  squad_count?: number;
}

export interface EloRatingEntry {
  team_name: string;
  team_code: string | null;
  rank: number | null;
  rating: number;
  rating_date: string;
  data_version: string;
  source_url: string;
  created_at: string | null;
}

export interface LatestEloSnapshot {
  snapshot_id: string;
  data_version: string;
  rating_date: string;
  source_url: string;
  source_note?: string;
  team_count: number;
  created_at: string | null;
  entries: EloRatingEntry[];
}

export interface DataFreshnessSource {
  status: "available" | "partial" | "missing" | string;
  source_name?: string | null;
  source_date?: string | null;
  source_url?: string | null;
  rows?: number | null;
  version?: string | null;
  last_run_status?: string | null;
  teams?: number | null;
  players?: number | null;
  coaches?: number | null;
  rated_players?: number | null;
  missing_teams?: string[];
  source_version?: string | null;
  last_update?: string | null;
  active_models?: number | null;
  latest_model?: string | null;
  last_trained_at?: string | null;
}

export interface DataFreshness {
  status?: "available" | "partial" | "unavailable" | string;
  message?: string | null;
  warnings?: string[];
  sources?: Record<string, DataFreshnessSource>;
  generated_at: string;
  data_snapshot_timestamp: string | null;
  last_elo_update: string | null;
  last_elo_rating_date: string | null;
  elo_data_version: string | null;
  elo_source_url: string | null;
  last_fifa_ranking_update: string | null;
  last_fifa_ranking_date: string | null;
  fifa_data_version: string | null;
  fifa_source_url: string | null;
  last_match_result_update: string | null;
  last_player_data_update: string | null;
  player_data_source: string | null;
  model_version: string | null;
  model_trained_at: string | null;
  feature_version: string;
  data_snapshot_version: string;
  using_latest_cached_snapshot: boolean;
  source_status: Record<string, string>;
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
  data_snapshot?: Record<string, unknown>;
  explanation: PredictionExplanation;
}

export interface HeadToHeadPrediction {
  home_team: string;
  away_team: string;
  match_date: string;
  method_used: string;
  probabilities: MLOutcome;
  expected_score: {
    home_xg: number;
    away_xg: number;
    scoreline: string;
  };
  confidence: number;
  model_version: string;
  feature_snapshot: {
    features: Record<string, number>;
    data_snapshot: Record<string, unknown>;
  };
  method_breakdown: Record<string, MLOutcome>;
  method_weights: Record<string, number>;
  model_agreement: number;
  key_factors: Array<{
    name: string;
    label: string;
    value: number;
    unit: string;
    favours: string;
    impact: number;
  }>;
  explanation?: PredictionExplanation;
}

export interface MLModel {
  id: number;
  model_name: string;
  model_type?: string | null;
  version: string;
  accuracy: number | null;
  f1_score: number | null;
  brier_score: number | null;
  log_loss: number | null;
  calibration_score: number | null;
  ensemble_weight: number;
  weight?: number | null;
  ml_weight?: number | null;
  final_ensemble_weight?: number | null;
  metrics?: Record<string, number | string | null>;
  training_samples: number | null;
  feature_version: string;
  data_snapshot_version?: string | null;
  calibration_status?: string;
  requires_recalibration?: boolean;
  is_active: boolean;
  status?: string | null;
  description?: string | null;
  trained_at: string | null;
  last_trained_at?: string | null;
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
  elo_rating: number | null;
  fifa_rank: number | null;
}

export interface WC2026Groups {
  year: number;
  draw_complete: boolean;
  groups: Record<string, string[]>;
  total_qualified: number;
  qualification_status: { confirmed: number; total_slots: number };
}

export interface WC2026GroupRow {
  rank: number;
  team: string;
  group: string;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
  qualified: boolean;
  qualification_type: "automatic" | "best_third" | "eliminated";
}

export type PredictionMode = "statistical" | "ml" | "ensemble";

export interface WC2026MatchPrediction {
  home_win: number;
  draw: number;
  away_win: number;
  available?: boolean;
  models_used?: string[];
}

export interface WC2026Match {
  match_id: string;
  round: string;
  order: number;
  group?: string | null;
  home: string;
  away: string;
  home_code?: string;
  away_code?: string;
  home_goals: number;
  away_goals: number;
  winner: string | null;
  loser: string | null;
  advancing_team?: string | null;
  decided_by: "regulation" | "extra_time" | "penalties" | string;
  home_xg: number;
  away_xg: number;
  scoreline?: string;
  expected_scoreline?: string;
  statistical_prediction?: WC2026MatchPrediction;
  ml_prediction?: WC2026MatchPrediction;
  ensemble_prediction?: WC2026MatchPrediction;
  selected_prediction?: WC2026MatchPrediction;
  prediction_mode?: PredictionMode;
  effective_prediction_mode?: PredictionMode | "ensemble_fallback" | string;
  model_used?: string;
  winner_probability?: number | null;
  champion_probability?: number | null;
  advancement_reason?: string;
}

export type WC2026KnockoutMatch = WC2026Match;

export interface WC2026KnockoutRound {
  round: string;
  matches: WC2026KnockoutMatch[];
}

export interface WC2026Simulation {
  year: number;
  runs: number;
  seed?: number | null;
  deterministic?: boolean;
  prediction_mode?: PredictionMode;
  draw_complete: boolean;
  groups?: Record<string, string[]>;
  champion?: string | null;
  runner_up?: string | null;
  third_place?: string | null;
  fourth_place?: string | null;
  champion_probability?: number | null;
  group_tables?: Record<string, WC2026GroupRow[]>;
  group_stage_matches?: Record<string, WC2026Match[]>;
  qualified_teams?: WC2026GroupRow[];
  best_third_place?: WC2026GroupRow[];
  knockout_bracket?: WC2026KnockoutRound[];
  matches?: WC2026Match[];
  data_snapshot?: DataFreshness;
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
  elo_rating_used?: number;
  elo_rank_used?: number | null;
  elo_source?: string | null;
  elo_source_date?: string | null;
  elo_snapshot_version?: string | null;
  fifa_ranking_used?: number;
  data_snapshot?: string | null;
  data_snapshot_version?: string | null;
  player_data_freshness_timestamp?: string | null;
  model_version?: string | null;
  prediction_type?: string;
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
  data_snapshot?: DataFreshness;
}

export interface Player {
  id: number;
  team_id?: number | null;
  name: string;
  team_name?: string;
  position: string;
  club: string | null;
  age: number | null;
  nationality?: string | null;
  // FIFA squad PDF fields
  shirt_number?: number | null;
  first_names?: string | null;
  last_names?: string | null;
  name_on_shirt?: string | null;
  date_of_birth?: string | null;
  height_cm?: number | null;
  // Playing metrics
  goals: number;
  assists: number;
  xg: number;
  xag: number;
  minutes_played: number;
  international_caps: number;
  international_goals: number;
  player_rating?: number | null;
  ea_fc_rating?: number | null;
  player_rating_source?: string | null;
  player_rating_version?: string | null;
  injured: boolean;
  suspended: boolean;
  fitness_score: number;
  recent_form_score?: number;
  data_source?: string | null;
  updated_at?: string | null;
  profile_description?: string | null;
  market_value_eur: number | null;
}

export interface TeamSquad {
  team?: Team;
  team_name?: string;
  coach?: string | null;
  squad_count?: number;
  squad: Player[];
}

// RAG types
export interface RagChunkRef {
  chunk_id: number;
  document_id: number;
  doc_type: string;
  title: string;
  text: string;
  score: number;
}

export interface RagAnswer {
  answer: string;
  chunks: RagChunkRef[];
  citations: string[];
  sources: string[];
  confidence: number;
  warnings: string[];
  context_type?: string | null;
  team_id?: number | null;
  simulation_id?: string | null;
}

export interface RagAskRequest {
  query: string;
  context_type?: string | null;
  team_id?: number | null;
  simulation_id?: string | null;
  max_chunks?: number;
}

export interface RagIndexStatus {
  total_documents: number;
  total_chunks: number;
  doc_types: Record<string, number>;
  last_indexed_at: string | null;
  index_method: string;
}

export interface RagDocumentSummary {
  id: number;
  doc_type: string;
  title: string;
  source_ref: string;
  indexed_at: string;
  chunk_count: number;
}
