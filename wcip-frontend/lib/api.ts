// Typed fetch client for the FastAPI backend.
// Handles token storage, Authorization injection, transparent refresh on 401,
// and consistent error shapes. Browser-only token storage (localStorage).

import type {
  MatchPrediction, Page, ScenarioComparison, Simulation, Team, TokenPair,
  TournamentResult, User, EloPoint, AdminAnalytics,
  HybridPrediction, MLModel, FeatureVector, QualifiedTeam,
  WC2026Groups, WC2026Simulation, TeamDetail, Player,
  WorldCupWinnerPrediction,
} from "./types";

function resolveApiBase() {
  const raw =
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE ||
    "/backend/api/v1";
  const trimmed = raw.replace(/\/+$/, "");
  if (trimmed.endsWith("/api/v1") || trimmed.endsWith("/backend/api/v1")) {
    return trimmed;
  }
  if (trimmed.startsWith("/")) {
    return `${trimmed}/api/v1`;
  }
  return `${trimmed}/api/v1`;
}

const BASE = resolveApiBase();

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
  form?: boolean;       // send as x-www-form-urlencoded (login)
  retry?: boolean;      // internal: prevent infinite refresh loops
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
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

  const res = await fetch(`${BASE}${path}`, { method, headers, body: payload });

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
      method: "POST", form: true, body: { username: email, password },
    });
    tokenStore.set(pair);
    return pair;
  },
  me: () => request<User>("/auth/me", { auth: true }),
  logout: () => tokenStore.clear(),

  // --- teams ---
  teams: (confederation?: string) =>
    request<Team[]>(`/teams${confederation ? `?confederation=${confederation}` : ""}`),
  team: (id: number) => request<Team>(`/teams/${id}`),
  eloHistory: (id: number) => request<EloPoint[]>(`/teams/${id}/elo-history`),

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
    options?: { seed?: number | null; deterministic?: boolean },
  ) =>
    request<WC2026Simulation>("/world-cup/simulate", {
      method: "POST",
      body: {
        year: 2026,
        runs,
        overrides,
        seed: options?.seed ?? null,
        deterministic: options?.deterministic ?? false,
      },
    }),

  wc2026WinnerPredictions: (runs = 5000, seed?: number | null, deterministic = false) => {
    const params = new URLSearchParams({ runs: String(runs), deterministic: String(deterministic) });
    if (seed !== undefined && seed !== null) params.set("seed", String(seed));
    return request<WorldCupWinnerPrediction[]>(
      `/world-cup/2026/winner-predictions?${params}`
    );
  },

  wc2026Schedule: () => request<unknown>("/world-cup/schedule?year=2026"),

  wc2026TeamDetail: (teamName: string) =>
    request<TeamDetail>(`/world-cup/teams/${encodeURIComponent(teamName)}`),

  wc2026Players: (teamName: string) =>
    request<{ team_name: string; squad: Player[] }>(
      `/world-cup/players/${encodeURIComponent(teamName)}`
    ),
};
