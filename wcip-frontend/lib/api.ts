// Typed fetch client for the FastAPI backend.
// Handles token storage, Authorization injection, transparent refresh on 401,
// and consistent error shapes. Browser-only token storage (localStorage).

import type {
  MatchPrediction, Page, ScenarioComparison, Simulation, Team, TokenPair,
  TournamentResult, User, EloPoint, AdminAnalytics,
  HybridPrediction, MLModel, FeatureVector, QualifiedTeam,
  WC2026Groups, WC2026Simulation, TeamDetail, Player, TeamSquad,
  WorldCupWinnerPrediction, DataFreshness, LatestEloSnapshot,
  PredictionMode, RagAnswer, RagAskRequest, RagIndexStatus, RagDocumentSummary,
} from "./types";

export interface ApiConfigIssue {
  code: "api_base_missing" | "api_base_includes_prefix" | "api_base_localhost" | "api_base_frontend_origin" | "api_base_insecure";
  message: string;
  detail: string;
}

function rawApiBase() {
  return process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "";
}

export function buildApiUrl(path: string) {
  const rawBase = rawApiBase();

  if (!rawBase) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured");
  }

  const base = rawBase.replace(/\/+$/, "");
  const cleanPath = path.startsWith("/") ? path : `/${path}`;

  return `${base}${cleanPath}`;
}

const API_PREFIX = "/api/v1";

export function getApiBaseUrl() {
  return buildApiUrl(API_PREFIX);
}

export function getApiConfigIssue(): ApiConfigIssue | null {
  const publicBase = rawApiBase();
  const isProduction = process.env.NODE_ENV === "production";

  if (!publicBase) {
    return {
      code: "api_base_missing",
      message: "Backend URL is not configured.",
      detail: "Set NEXT_PUBLIC_API_BASE_URL to the FastAPI backend origin, for example http://localhost:8000 locally or the Render backend URL in production.",
    };
  }

  if (/\/api\/v1$/i.test(publicBase.replace(/\/+$/, ""))) {
    return {
      code: "api_base_includes_prefix",
      message: "Backend URL includes /api/v1.",
      detail: "Set NEXT_PUBLIC_API_BASE_URL to the backend origin only. The frontend appends /api/v1 in code.",
    };
  }

  if (isProduction && /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?/i.test(publicBase)) {
    return {
      code: "api_base_localhost",
      message: "Production backend URL points to localhost.",
      detail: "NEXT_PUBLIC_API_BASE_URL must point to the deployed FastAPI backend, not localhost.",
    };
  }

  if (
    isProduction
    && typeof window !== "undefined"
    && publicBase
    && publicBase.replace(/\/+$/, "") === window.location.origin
  ) {
    return {
      code: "api_base_frontend_origin",
      message: "Backend URL points to the frontend deployment.",
      detail: "NEXT_PUBLIC_API_BASE_URL must be the FastAPI backend URL, not the Vercel frontend URL.",
    };
  }

  if (
    isProduction
    && typeof window !== "undefined"
    && window.location.protocol === "https:"
    && publicBase.startsWith("http://")
  ) {
    return {
      code: "api_base_insecure",
      message: "Backend URL uses insecure HTTP.",
      detail: "Use an HTTPS backend URL to avoid browser mixed-content blocking.",
    };
  }

  return null;
}

const ACCESS_KEY = "wcip_access";
const REFRESH_KEY = "wcip_refresh";

export const tokenStore = {
  get access() {
    return typeof window === "undefined" ? null : localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return typeof window === "undefined" ? null : localStorage.getItem(REFRESH_KEY);
  },
  set(pair: TokenPair) {
    localStorage.setItem(ACCESS_KEY, pair.access_token);
    localStorage.setItem(REFRESH_KEY, pair.refresh_token);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public errorCode?: string,
    public requestId?: string | null,
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
  form?: boolean;       // send as x-www-form-urlencoded
  retry?: boolean;      // internal: prevent infinite refresh loops
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const configIssue = getApiConfigIssue();
  if (configIssue) {
    throw new ApiError(0, configIssue.message, configIssue.code, null, configIssue);
  }

  const { method = "GET", body, auth = false, form = false, retry = true } = opts;
  const headers: Record<string, string> = {};
  let payload: BodyInit | undefined;

  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    payload = new URLSearchParams(body as Record<string, string>).toString();
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  if (auth && tokenStore.access) {
    headers["Authorization"] = `Bearer ${tokenStore.access}`;
  }

  const res = await fetch(buildApiUrl(`${API_PREFIX}${path}`), { method, headers, body: payload });

  if (res.status === 401 && auth && retry && tokenStore.refresh) {
    const refreshed = await tryRefresh();
    if (refreshed) return request<T>(path, { ...opts, retry: false });
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    let errorCode: string | undefined;
    let requestId: string | null | undefined;
    let rawDetail: unknown;
    try {
      const data = await res.json();
      errorCode = typeof data.error_code === "string" ? data.error_code : undefined;
      requestId = typeof data.request_id === "string" ? data.request_id : null;
      rawDetail = data.detail;
      detail = typeof data.message === "string" ? data.message
        : typeof data.detail === "string" ? data.detail
        : Array.isArray(data.detail) ? data.detail.map((d: { msg: string }) => d.msg).join(", ")
        : detail;
    } catch { /* non-JSON error body */ }
    throw new ApiError(res.status, detail, errorCode, requestId, rawDetail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

async function tryRefresh(): Promise<boolean> {
  try {
    const pair = await request<TokenPair>("/auth/refresh", {
      method: "POST",
      body: { refresh_token: tokenStore.refresh },
      retry: false,
    });
    tokenStore.set(pair);
    return true;
  } catch {
    tokenStore.clear();
    return false;
  }
}

export const api = {
  // --- auth ---
  register: (email: string, password: string, full_name?: string) =>
    request<User>("/auth/register", { method: "POST", body: { email, password, full_name } }),
  login: async (email: string, password: string) => {
    const pair = await request<TokenPair>("/auth/login", {
      method: "POST", body: { email, password },
    });
    tokenStore.set(pair);
    return pair;
  },
  me: () => request<User>("/auth/me", { auth: true }),
  logout: () => tokenStore.clear(),

  // --- teams ---
  teams: (confederation?: string, worldCupOnly = true) => {
    const params = new URLSearchParams();
    if (confederation) params.set("confederation", confederation);
    params.set("world_cup_only", String(worldCupOnly));
    return request<Team[]>(`/teams?${params}`);
  },
  team: (id: number) => request<Team>(`/teams/${id}`),
  teamPlayers: (id: number, position?: string) =>
    request<Player[]>(`/teams/${id}/players${position ? `?position=${encodeURIComponent(position)}` : ""}`),
  teamSquad: (id: number) => request<TeamSquad>(`/teams/${id}/squad`),
  eloHistory: (id: number) => request<EloPoint[]>(`/teams/${id}/elo-history`),
  latestElo: (limit = 50) => request<LatestEloSnapshot>(`/ratings/elo/latest?limit=${limit}`),
  teamEloSnapshotHistory: (id: number, limit = 100) =>
    request<{ team_id: number; team_name: string; entries: LatestEloSnapshot["entries"] }>(
      `/ratings/elo/history/${id}?limit=${limit}`
    ),
  fifaLatest: (limit = 50) => request<unknown>(`/rankings/fifa/latest?limit=${limit}`),
  fifaHistory: (id: number, limit = 100) =>
    request<unknown>(`/rankings/fifa/history/${id}?limit=${limit}`),

  // --- players ---
  players: (params?: { team_name?: string; q?: string; limit?: number }) => {
    const p = new URLSearchParams();
    if (params?.team_name) p.set("team_name", params.team_name);
    if (params?.q) p.set("q", params.q);
    if (params?.limit) p.set("limit", String(params.limit));
    const qs = p.toString();
    return request<Player[]>(`/players${qs ? `?${qs}` : ""}`);
  },
  player: (id: number) => request<Player>(`/players/${id}`),

  // --- predictions ---
  simulateMatch: (body: unknown) =>
    request<MatchPrediction>("/match/simulate", { method: "POST", body }),
  simulateTournament: (body: unknown) =>
    request<TournamentResult>("/tournament/simulate", { method: "POST", body }),
  compareScenarios: (body: unknown) =>
    request<ScenarioComparison>("/scenario/compare", { method: "POST", body }),

  // --- simulations (authed) ---
  createSimulation: (body: unknown) =>
    request<{ id: number; status: string; task_id?: string; result?: unknown }>(
      "/simulations", { method: "POST", body, auth: true }),
  listSimulations: (page = 1, page_size = 20) =>
    request<Page<Simulation>>(`/simulations?page=${page}&page_size=${page_size}`, { auth: true }),
  getSimulation: (id: number) => request<Simulation>(`/simulations/${id}`, { auth: true }),
  updateSimulation: (id: number, body: unknown) =>
    request<Simulation>(`/simulations/${id}`, { method: "PATCH", body, auth: true }),
  duplicateSimulation: (id: number) =>
    request<Simulation>(`/simulations/${id}/duplicate`, { method: "POST", auth: true }),
  compareSimulations: (id: number, simulationIds: number[]) =>
    request<unknown>(`/simulations/${id}/compare`, {
      method: "POST",
      body: { simulation_ids: simulationIds },
      auth: true,
    }),
  deleteSimulation: (id: number) =>
    request<void>(`/simulations/${id}`, { method: "DELETE", auth: true }),

  // --- admin ---
  adminAnalytics: () => request<AdminAnalytics>("/admin/analytics", { auth: true }),
  dataFreshness: () => request<DataFreshness>("/data/freshness"),
  refreshElo: () => request<unknown>("/admin/data/refresh-elo", { method: "POST", auth: true }),
  refreshFifaRankings: () =>
    request<unknown>("/admin/data/refresh-fifa-rankings", { method: "POST", auth: true }),
  refreshPlayers: () => request<unknown>("/admin/data/refresh-players", { method: "POST", auth: true }),
  refreshAllData: () => request<unknown>("/admin/data/refresh-all", { method: "POST", auth: true }),
  adminRetrainIfNeeded: (body?: {
    material_ranking_changes?: number;
    material_elo_changes?: number;
    changed_player_records?: number;
    changed_match_results?: number;
    apply?: boolean;
  }) => request<unknown>("/admin/ml/retrain-if-needed", {
    method: "POST",
    auth: true,
    body: body ?? {},
  }),

  // --- ML predictions (Phase 2) ---
  mlPredict: (body: {
    home_team: string;
    away_team: string;
    match_date?: string;
    home_overrides?: Record<string, number>;
    away_overrides?: Record<string, number>;
    include_shap?: boolean;
  }) => request<HybridPrediction>("/ml/predict", { method: "POST", body }),

  mlModels: () => request<MLModel[]>("/ml/models"),
  mlRetrain: (model: string = "all") =>
    request<unknown>("/ml/retrain", { method: "POST", auth: true, body: { model } }),

  mlFeatures: (home: string, away: string, date?: string) => {
    const params = new URLSearchParams({ home_team: home, away_team: away });
    if (date) params.set("match_date", date);
    return request<FeatureVector>(`/ml/features?${params}`);
  },

  mlExplanations: (home: string, away: string, model = "xgboost", date?: string) => {
    const params = new URLSearchParams({ home_team: home, away_team: away, model });
    if (date) params.set("match_date", date);
    return request<{
      home_team: string;
      away_team: string;
      model: string;
      top_positive: Array<{ name: string; display_name: string; value: number; impact: number }>;
      top_negative: Array<{ name: string; display_name: string; value: number; impact: number }>;
      narrative: string;
    }>(`/ml/explanations?${params}`);
  },

  // --- World Cup 2026 (Phase 2) ---
  wc2026Teams: (params?: { confederation?: string; confirmed_only?: boolean }) => {
    const p = new URLSearchParams({ year: "2026" });
    if (params?.confederation) p.set("confederation", params.confederation);
    if (params?.confirmed_only !== undefined) p.set("confirmed_only", String(params.confirmed_only));
    return request<QualifiedTeam[]>(`/world-cup/qualified-teams?${p}`);
  },

  wc2026Groups: () => request<WC2026Groups>("/world-cup/groups?year=2026"),

  wc2026Simulate: (
    runs = 10000,
    overrides?: Record<string, Record<string, number>>,
    options?: { seed?: number | null; deterministic?: boolean; predictionMode?: PredictionMode },
  ) =>
    request<WC2026Simulation>("/world_cup/2026/simulate", {
      method: "POST",
      body: {
        year: 2026,
        runs,
        overrides,
        seed: options?.seed ?? null,
        deterministic: options?.deterministic ?? false,
        prediction_mode: options?.predictionMode ?? "ensemble",
      },
    }),

  wc2026WinnerPredictions: (runs = 5000, seed?: number | null, deterministic = false) => {
    const params = new URLSearchParams({ runs: String(runs), deterministic: String(deterministic) });
    if (seed !== undefined && seed !== null) params.set("seed", String(seed));
    return request<WorldCupWinnerPrediction[]>(
      `/world-cup/2026/winner-predictions?${params}`
    );
  },

  wc2026Predictions: (runs = 5000, seed?: number | null, deterministic = false) => {
    const params = new URLSearchParams({ runs: String(runs), deterministic: String(deterministic) });
    if (seed !== undefined && seed !== null) params.set("seed", String(seed));
    return request<{
      year: number;
      prediction_type: string;
      freshness: DataFreshness;
      winner_predictions: WorldCupWinnerPrediction[];
    }>(`/world-cup/2026/predictions?${params}`);
  },

  wc2026Schedule: () => request<unknown>("/world-cup/schedule?year=2026"),

  wc2026TeamDetail: (teamName: string) =>
    request<TeamDetail>(`/world-cup/teams/${encodeURIComponent(teamName)}`),

  wc2026Players: (teamName: string) =>
    request<{ team_name: string; squad: Player[] }>(
      `/world-cup/players/${encodeURIComponent(teamName)}`
    ),
};

export const ragApi = {
  ask: (req: RagAskRequest) =>
    request<RagAnswer>("/rag/ask", { method: "POST", body: req }),

  status: () => request<RagIndexStatus>("/rag/status"),

  documents: (doc_type?: string) => {
    const params = doc_type ? `?doc_type=${encodeURIComponent(doc_type)}` : "";
    return request<RagDocumentSummary[]>(`/rag/documents${params}`);
  },

  adminIndex: (force = false) =>
    request<{ status: string; indexed: Record<string, number>; force: boolean }>(
      `/admin/rag/index?force=${force}`,
      { method: "POST", auth: true }
    ),
};
