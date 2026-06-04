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
  round_of_16: number;
  expected_finish: number;
  champion_ci_low: number;
  champion_ci_high: number;
}

export interface TournamentResult {
  edition: string;
  runs: number;
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
