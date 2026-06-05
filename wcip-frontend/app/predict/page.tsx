"use client";

import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis,
} from "recharts";
import { useTeams, useSimulateMatch, useMLPredict } from "@/lib/queries";
import type { MatchPrediction, HybridPrediction } from "@/lib/types";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { pct } from "@/lib/utils";

// ── Shared types ──────────────────────────────────────────────────────────────

interface Overrides {
  form: number;
  injury_burden: number;
  coach_impact: number;
  elo: number;
}

const DEFAULT_OVERRIDES: Overrides = {
  form: 1.5,
  injury_burden: 0,
  coach_impact: 1.0,
  elo: 0,
};

// ── Team autocomplete ─────────────────────────────────────────────────────────

function TeamSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    if (!query) return options.slice(0, 10);
    const q = query.toLowerCase();
    return options.filter((o) => o.toLowerCase().includes(q)).slice(0, 10);
  }, [query, options]);

  function select(name: string) {
    onChange(name);
    setQuery("");
    setOpen(false);
  }

  return (
    <div className="relative">
      <label className="kicker block mb-1.5">{label}</label>
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        className="w-full text-left px-3 py-2.5 rounded-md border border-line bg-elevated text-fg text-sm
          hover:border-pitch transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pitch/60"
      >
        {value || <span className="text-muted">Select team…</span>}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="absolute z-50 mt-1 w-full bg-elevated border border-line rounded-lg shadow-xl overflow-hidden"
          >
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search…"
              className="w-full px-3 py-2 bg-surface text-sm text-fg border-b border-line outline-none"
            />
            <div className="max-h-52 overflow-y-auto">
              {filtered.map((name) => (
                <button
                  key={name}
                  onClick={() => select(name)}
                  className={`w-full text-left px-3 py-2 text-sm transition-colors hover:bg-surface ${
                    value === name ? "text-pitch" : "text-fg"
                  }`}
                >
                  {name}
                </button>
              ))}
              {filtered.length === 0 && (
                <p className="px-3 py-3 text-muted text-sm">No match</p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Override slider row ────────────────────────────────────────────────────────

function OverrideRow({
  label, value, min, max, step, hint, onChange,
}: {
  label: string; value: number; min: number; max: number; step: number; hint: string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between">
        <span className="text-xs text-muted">{label}</span>
        <span className="tnum text-xs text-fg">{value.toFixed(2)}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full accent-[hsl(var(--pitch))] h-1.5 cursor-pointer"
      />
      <p className="text-[10px] text-muted">{hint}</p>
    </div>
  );
}

// ── Outcome probability bar (stacked) ────────────────────────────────────────

function OutcomeBar({
  home, away, home_win, draw, away_win, accentClass = "bg-pitch",
}: {
  home: string; away: string; home_win: number; draw: number; away_win: number;
  accentClass?: string;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs text-muted">
        <span className="text-fg font-medium">{home}</span>
        <span>Draw</span>
        <span className="text-fg font-medium">{away}</span>
      </div>
      <div className="flex h-5 rounded-full overflow-hidden gap-px">
        <div className={`${accentClass} transition-all`} style={{ width: `${home_win * 100}%` }} />
        <div className="bg-elevated transition-all" style={{ width: `${draw * 100}%` }} />
        <div className="bg-signal transition-all" style={{ width: `${away_win * 100}%` }} />
      </div>
      <div className="flex justify-between text-xs tnum">
        <span className="text-pitch font-semibold">{pct(home_win)}</span>
        <span className="text-muted">{pct(draw)}</span>
        <span className="text-signal font-semibold">{pct(away_win)}</span>
      </div>
    </div>
  );
}

// ── Model comparison bar chart ────────────────────────────────────────────────

const MODEL_LABELS: Record<string, string> = {
  statistical: "Statistical",
  logistic: "Logistic",
  random_forest: "Rnd Forest",
  xgboost: "XGBoost",
  lightgbm: "LightGBM",
  catboost: "CatBoost",
  ensemble: "Ensemble",
};

function ModelComparisonChart({
  home,
  away,
  statistical,
  ml,
  ensemble,
}: {
  home: string;
  away: string;
  statistical: { home_win: number; draw: number; away_win: number };
  ml: Record<string, { home_win: number; draw: number; away_win: number }>;
  ensemble: { home_win: number; draw: number; away_win: number };
}) {
  const data = [
    { model: "Statistical", home_win: statistical.home_win * 100, draw: statistical.draw * 100, away_win: statistical.away_win * 100 },
    ...Object.entries(ml).map(([k, v]) => ({
      model: MODEL_LABELS[k] ?? k,
      home_win: v.home_win * 100,
      draw: v.draw * 100,
      away_win: v.away_win * 100,
    })),
    { model: "Ensemble", home_win: ensemble.home_win * 100, draw: ensemble.draw * 100, away_win: ensemble.away_win * 100 },
  ];

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" vertical={false} />
        <XAxis dataKey="model" stroke="hsl(var(--muted))" fontSize={10} tick={{ fill: "hsl(var(--muted))" }} />
        <YAxis tickFormatter={(v) => `${v}%`} stroke="hsl(var(--muted))" fontSize={10} domain={[0, 100]} />
        <Tooltip
          formatter={(v: number, name: string) => [
            `${v.toFixed(1)}%`,
            name === "home_win" ? home : name === "away_win" ? away : "Draw",
          ]}
          contentStyle={{
            background: "hsl(var(--elevated))", border: "1px solid hsl(var(--line))",
            borderRadius: 8, fontSize: 11,
          }}
          labelStyle={{ color: "hsl(var(--fg))", fontWeight: "bold" }}
        />
        <Bar dataKey="home_win" stackId="a" fill="hsl(var(--pitch))" name="home_win" />
        <Bar dataKey="draw" stackId="a" fill="hsl(var(--line))" name="draw" />
        <Bar dataKey="away_win" stackId="a" fill="hsl(var(--signal))" name="away_win" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Factors radar ─────────────────────────────────────────────────────────────

function FactorsPanel({ prediction }: { prediction: HybridPrediction }) {
  const { explanation } = prediction;
  if (!explanation) return null;

  return (
    <div className="space-y-3">
      {explanation.narrative && (
        <p className="text-sm text-muted leading-relaxed bg-elevated rounded-lg p-3 border border-line">
          {explanation.narrative}
        </p>
      )}
      <div className="grid sm:grid-cols-2 gap-4">
        {explanation.top_positive.length > 0 && (
          <div>
            <p className="kicker text-pitch mb-2">Favours {prediction.home_team}</p>
            <div className="space-y-1">
              {explanation.top_positive.map((f) => (
                <div key={f.name} className="flex justify-between text-xs py-1 border-b border-line/40">
                  <span className="text-muted">{f.display_name}</span>
                  <span className="text-pitch tnum">+{f.impact.toFixed(3)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        {explanation.top_negative.length > 0 && (
          <div>
            <p className="kicker text-signal mb-2">Favours {prediction.away_team}</p>
            <div className="space-y-1">
              {explanation.top_negative.map((f) => (
                <div key={f.name} className="flex justify-between text-xs py-1 border-b border-line/40">
                  <span className="text-muted">{f.display_name}</span>
                  <span className="text-signal tnum">{f.impact.toFixed(3)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── xG result display ─────────────────────────────────────────────────────────

function XGDisplay({ home, away, home_xg, away_xg, scoreline }: {
  home: string; away: string; home_xg: number; away_xg: number; scoreline: string;
}) {
  return (
    <div className="flex items-center justify-around border-y border-line py-4">
      <div className="text-center">
        <div className="kicker">{home} xG</div>
        <div className="tnum text-3xl text-pitch mt-0.5">{home_xg.toFixed(2)}</div>
      </div>
      <div className="text-center">
        <div className="kicker">Most likely</div>
        <div className="display text-xl text-fg mt-0.5">{scoreline}</div>
      </div>
      <div className="text-center">
        <div className="kicker">{away} xG</div>
        <div className="tnum text-3xl text-signal mt-0.5">{away_xg.toFixed(2)}</div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PredictPage() {
  const { data: teams } = useTeams();
  const teamNames = useMemo(() => (teams ?? []).map((t) => t.name).sort(), [teams]);

  const [home, setHome] = useState("France");
  const [away, setAway] = useState("Brazil");
  const [showControls, setShowControls] = useState(false);
  const [homeOverrides, setHomeOverrides] = useState<Overrides>({ ...DEFAULT_OVERRIDES });
  const [awayOverrides, setAwayOverrides] = useState<Overrides>({ ...DEFAULT_OVERRIDES });
  const [statResult, setStatResult] = useState<MatchPrediction | null>(null);
  const [hybridResult, setHybridResult] = useState<HybridPrediction | null>(null);
  const [activeMode, setActiveMode] = useState<"stat" | "ml" | "ensemble" | "all" | null>(null);

  const statMutation = useSimulateMatch();
  const mlMutation = useMLPredict();

  const busy = statMutation.isPending || mlMutation.isPending;

  function buildHomeOverrides() {
    const o: Record<string, number> = {};
    if (homeOverrides.form !== DEFAULT_OVERRIDES.form) o.form = homeOverrides.form;
    if (homeOverrides.injury_burden > 0) o.injury_burden = homeOverrides.injury_burden;
    if (homeOverrides.coach_impact !== 1.0) o.coach_impact = homeOverrides.coach_impact;
    return Object.keys(o).length ? o : undefined;
  }

  function buildAwayOverrides() {
    const o: Record<string, number> = {};
    if (awayOverrides.form !== DEFAULT_OVERRIDES.form) o.form = awayOverrides.form;
    if (awayOverrides.injury_burden > 0) o.injury_burden = awayOverrides.injury_burden;
    if (awayOverrides.coach_impact !== 1.0) o.coach_impact = awayOverrides.coach_impact;
    return Object.keys(o).length ? o : undefined;
  }

  async function runStatistical() {
    setActiveMode("stat");
    setHybridResult(null);
    statMutation.mutate({
      home, away,
      home_modifiers: { attack: 1, defence: 1, injury: 1 - homeOverrides.injury_burden, morale: 1, fatigue: 1, chemistry: 1, coaching: homeOverrides.coach_impact },
      away_modifiers: { attack: 1, defence: 1, injury: 1 - awayOverrides.injury_burden, morale: 1, fatigue: 1, chemistry: 1, coaching: awayOverrides.coach_impact },
    }, {
      onSuccess: (r) => setStatResult(r),
    });
  }

  async function runML() {
    setActiveMode("ml");
    mlMutation.mutate({
      home_team: home, away_team: away,
      home_overrides: buildHomeOverrides(),
      away_overrides: buildAwayOverrides(),
      include_shap: false,
    }, { onSuccess: (r) => setHybridResult(r) });
  }

  async function runEnsemble() {
    setActiveMode("ensemble");
    mlMutation.mutate({
      home_team: home, away_team: away,
      home_overrides: buildHomeOverrides(),
      away_overrides: buildAwayOverrides(),
      include_shap: true,
    }, { onSuccess: (r) => setHybridResult(r) });
  }

  async function runAll() {
    setActiveMode("all");
    setStatResult(null);
    setHybridResult(null);
    statMutation.mutate({ home, away }, {
      onSuccess: (r) => setStatResult(r),
    });
    mlMutation.mutate({
      home_team: home, away_team: away,
      home_overrides: buildHomeOverrides(),
      away_overrides: buildAwayOverrides(),
      include_shap: true,
    }, { onSuccess: (r) => setHybridResult(r) });
  }

  const isInvalid = home === away || !home || !away;

  return (
    <div className="space-y-8">
      {/* Header */}
      <header>
        <p className="kicker mb-2">Prediction lab</p>
        <h1 className="display text-4xl">Match predictor</h1>
        <p className="text-muted mt-2 max-w-2xl">
          Statistical (Elo + Poisson), 5 ML models, and ensemble — side by side.
          Adjust injuries, form, and coaching to model any scenario.
        </p>
      </header>

      {/* Controls card */}
      <Card>
        <CardHeader className="flex items-center justify-between">
          <span className="kicker">Fixture</span>
          <button
            onClick={() => setShowControls((s) => !s)}
            className="text-xs uppercase tracking-wide text-muted hover:text-pitch transition-colors"
          >
            {showControls ? "Hide" : "Advanced"} controls
          </button>
        </CardHeader>
        <CardBody className="space-y-5">
          <div className="grid grid-cols-[1fr_auto_1fr] items-end gap-4">
            <TeamSelect label="Home team" value={home} onChange={setHome} options={teamNames} />
            <span className="display text-muted text-sm mb-2.5">VS</span>
            <TeamSelect label="Away team" value={away} onChange={setAway} options={teamNames} />
          </div>

          <AnimatePresence>
            {showControls && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="grid sm:grid-cols-2 gap-6 pt-4 border-t border-line">
                  {[
                    { label: home, overrides: homeOverrides, set: setHomeOverrides },
                    { label: away, overrides: awayOverrides, set: setAwayOverrides },
                  ].map(({ label, overrides, set }) => (
                    <div key={label} className="space-y-4">
                      <p className="kicker text-pitch">{label} overrides</p>
                      <OverrideRow
                        label="Recent form (pts/game)" hint="0=poor, 1.5=average, 3=perfect"
                        value={overrides.form} min={0} max={3} step={0.1}
                        onChange={(v) => set((o) => ({ ...o, form: v }))}
                      />
                      <OverrideRow
                        label="Injury burden" hint="Fraction of squad unavailable (0=fit, 0.4=heavy)"
                        value={overrides.injury_burden} min={0} max={1} step={0.05}
                        onChange={(v) => set((o) => ({ ...o, injury_burden: v }))}
                      />
                      <OverrideRow
                        label="Coach impact" hint="Coaching quality multiplier (1.0 = neutral)"
                        value={overrides.coach_impact} min={0.5} max={1.5} step={0.05}
                        onChange={(v) => set((o) => ({ ...o, coach_impact: v }))}
                      />
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Action buttons */}
          <div className="flex flex-wrap gap-2 pt-2">
            <Button onClick={runStatistical} disabled={busy || isInvalid} variant="outline" size="sm">
              {statMutation.isPending && activeMode === "stat" ? "Running…" : "Statistical"}
            </Button>
            <Button onClick={runML} disabled={busy || isInvalid} variant="outline" size="sm">
              {mlMutation.isPending && activeMode === "ml" ? "Running…" : "ML Models"}
            </Button>
            <Button onClick={runEnsemble} disabled={busy || isInvalid} variant="outline" size="sm">
              {mlMutation.isPending && activeMode === "ensemble" ? "Running…" : "Ensemble"}
            </Button>
            <Button onClick={runAll} disabled={busy || isInvalid} size="sm">
              {busy && activeMode === "all" ? "Running…" : "Compare all"}
            </Button>
          </div>

          {isInvalid && home === away && (
            <p className="text-xs text-signal">Pick two different teams.</p>
          )}
        </CardBody>
      </Card>

      {/* Error states */}
      {statMutation.isError && (
        <p className="text-signal text-sm">{(statMutation.error as Error).message}</p>
      )}
      {mlMutation.isError && (
        <p className="text-signal text-sm">{(mlMutation.error as Error).message}</p>
      )}

      {/* Loading skeletons */}
      {busy && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      )}

      <AnimatePresence>
        {(statResult || hybridResult) && !busy && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
            {/* Match header */}
            <div className="text-center py-2">
              <div className="display text-3xl">
                {home}
                <span className="text-muted mx-3 text-2xl">vs</span>
                {away}
              </div>
              {hybridResult && (
                <XGDisplay
                  home={home} away={away}
                  home_xg={hybridResult.home_xg}
                  away_xg={hybridResult.away_xg}
                  scoreline={hybridResult.expected_scoreline}
                />
              )}
              {hybridResult && (
                <div className="flex justify-center gap-6 mt-3 text-xs text-muted">
                  <span>
                    Confidence: <span className="text-fg tnum">{(hybridResult.confidence_score * 100).toFixed(0)}%</span>
                  </span>
                  <span>
                    Model agreement: <span className="text-fg tnum">{(hybridResult.model_agreement * 100).toFixed(0)}%</span>
                  </span>
                </div>
              )}
            </div>

            {/* Three-layer comparison */}
            <Card>
              <CardHeader><span className="kicker">Probability comparison</span></CardHeader>
              <CardBody className="space-y-5">
                {statResult && (
                  <div>
                    <p className="kicker text-[hsl(45_95%_58%)] mb-2">Statistical (Elo + Poisson)</p>
                    <OutcomeBar
                      home={home} away={away}
                      home_win={statResult.probabilities.home_win}
                      draw={statResult.probabilities.draw}
                      away_win={statResult.probabilities.away_win}
                      accentClass="bg-[hsl(45_95%_58%)]"
                    />
                  </div>
                )}

                {hybridResult && Object.entries(hybridResult.ml_predictions).map(([model, probs]) => (
                  <div key={model}>
                    <p className="kicker text-[hsl(200_90%_62%)] mb-2">{MODEL_LABELS[model] ?? model}</p>
                    <OutcomeBar
                      home={home} away={away}
                      home_win={probs.home_win} draw={probs.draw} away_win={probs.away_win}
                      accentClass="bg-[hsl(200_90%_62%)]"
                    />
                  </div>
                ))}

                {hybridResult && (
                  <div className="pt-3 border-t border-line">
                    <p className="kicker text-pitch mb-2">Ensemble (weighted average)</p>
                    <OutcomeBar
                      home={home} away={away}
                      home_win={hybridResult.ensemble.home_win}
                      draw={hybridResult.ensemble.draw}
                      away_win={hybridResult.ensemble.away_win}
                    />
                  </div>
                )}
              </CardBody>
            </Card>

            {/* Model comparison chart (when we have all data) */}
            {hybridResult && (
              <Card>
                <CardHeader><span className="kicker">Home-win probability by model</span></CardHeader>
                <CardBody>
                  <ModelComparisonChart
                    home={home} away={away}
                    statistical={hybridResult.statistical}
                    ml={hybridResult.ml_predictions}
                    ensemble={hybridResult.ensemble}
                  />
                </CardBody>
              </Card>
            )}

            {/* Statistical explanation */}
            {statResult?.explanation && !hybridResult && (
              <Card>
                <CardHeader><span className="kicker">Statistical explanation</span></CardHeader>
                <CardBody className="space-y-3">
                  <p className="text-sm text-muted leading-relaxed">{statResult.explanation}</p>
                  {statResult.factors.slice(0, 4).map((f) => (
                    <div key={f.name} className="flex justify-between text-xs border-b border-line/50 pb-1.5">
                      <span className="text-muted">{f.name}</span>
                      <span className="text-fg">{f.detail}</span>
                    </div>
                  ))}
                </CardBody>
              </Card>
            )}

            {/* SHAP explanation */}
            {hybridResult?.explanation && (
              <Card>
                <CardHeader><span className="kicker">AI explanation</span></CardHeader>
                <CardBody>
                  <FactorsPanel prediction={hybridResult} />
                </CardBody>
              </Card>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
