"use client";

import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Legend,
  LineChart, Line, ReferenceLine, ErrorBar,
} from "recharts";
import { useTeams, useMLPredict } from "@/lib/queries";
import type { HybridPrediction } from "@/lib/types";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { pct } from "@/lib/utils";

// ── Team selector ─────────────────────────────────────────────────────────────

function TeamInput({
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
  return (
    <div className="flex-1">
      <label className="kicker block mb-1.5">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2.5 rounded-md border border-line bg-elevated text-fg text-sm
          focus:outline-none focus:border-pitch transition-colors"
      >
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}

// ── Model agreement meter ─────────────────────────────────────────────────────

function AgreementMeter({ agreement, confidence }: { agreement: number; confidence: number }) {
  const agreementPct = agreement * 100;
  const level = agreementPct >= 80 ? "High" : agreementPct >= 60 ? "Medium" : "Low";
  const colour = agreementPct >= 80 ? "hsl(var(--pitch))" : agreementPct >= 60 ? "hsl(45 95% 58%)" : "hsl(var(--signal))";

  return (
    <div className="grid grid-cols-2 gap-6">
      <div className="text-center">
        <div className="kicker mb-3">Model agreement</div>
        <div className="relative size-28 mx-auto">
          <svg viewBox="0 0 100 60" className="w-full" style={{ overflow: "visible" }}>
            <path d="M 10,55 A 40,40 0 0,1 90,55" fill="none" stroke="hsl(var(--elevated))" strokeWidth="10" strokeLinecap="round" />
            <path
              d="M 10,55 A 40,40 0 0,1 90,55"
              fill="none"
              stroke={colour}
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={`${agreementPct * 1.257} 200`}
              className="transition-all duration-700"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-end pb-1">
            <span className="tnum text-2xl font-bold text-fg" style={{ color: colour }}>
              {agreementPct.toFixed(0)}%
            </span>
            <span className="text-xs text-muted">{level}</span>
          </div>
        </div>
      </div>

      <div className="text-center">
        <div className="kicker mb-3">Confidence score</div>
        <div className="relative size-28 mx-auto">
          <svg viewBox="0 0 100 60" className="w-full" style={{ overflow: "visible" }}>
            <path d="M 10,55 A 40,40 0 0,1 90,55" fill="none" stroke="hsl(var(--elevated))" strokeWidth="10" strokeLinecap="round" />
            <path
              d="M 10,55 A 40,40 0 0,1 90,55"
              fill="none"
              stroke="hsl(200 90% 62%)"
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={`${confidence * 100 * 1.257} 200`}
              className="transition-all duration-700"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-end pb-1">
            <span className="tnum text-2xl font-bold text-[hsl(200_90%_62%)]">
              {(confidence * 100).toFixed(0)}%
            </span>
            <span className="text-xs text-muted">score</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Probability distribution chart ────────────────────────────────────────────

const MODEL_LABELS: Record<string, string> = {
  statistical: "Stat",
  logistic: "Logistic",
  random_forest: "RF",
  xgboost: "XGB",
  lightgbm: "LGBM",
  catboost: "CatB",
  ensemble: "Ensemble",
};

const MODEL_COLOURS: Record<string, string> = {
  statistical: "hsl(45 95% 58%)",
  logistic: "hsl(220 90% 62%)",
  random_forest: "hsl(140 70% 50%)",
  xgboost: "hsl(8 90% 64%)",
  lightgbm: "hsl(280 70% 68%)",
  catboost: "hsl(200 90% 62%)",
  ensemble: "hsl(75 95% 55%)",
};

function ProbabilityDistribution({
  home,
  away,
  prediction,
}: {
  home: string;
  away: string;
  prediction: HybridPrediction;
}) {
  const data = [
    { model: "Stat", key: "statistical", ...prediction.statistical },
    ...Object.entries(prediction.ml_predictions).map(([k, v]) => ({
      model: MODEL_LABELS[k] ?? k,
      key: k,
      ...v,
    })),
    { model: "Ensemble", key: "ensemble", ...prediction.ensemble },
  ].map((row) => ({
    model: row.model,
    key: row.key as string,
    [`${home} win`]: parseFloat((row.home_win * 100).toFixed(1)),
    Draw: parseFloat((row.draw * 100).toFixed(1)),
    [`${away} win`]: parseFloat((row.away_win * 100).toFixed(1)),
  }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" vertical={false} />
        <XAxis dataKey="model" stroke="hsl(var(--muted))" fontSize={11} tick={{ fill: "hsl(var(--muted))" }} />
        <YAxis tickFormatter={(v) => `${v}%`} stroke="hsl(var(--muted))" fontSize={11} domain={[0, 100]} />
        <Tooltip
          contentStyle={{
            background: "hsl(var(--elevated))", border: "1px solid hsl(var(--line))",
            borderRadius: 8, fontSize: 11,
          }}
          labelStyle={{ color: "hsl(var(--fg))", fontWeight: "bold" }}
          formatter={(v: number) => [`${v}%`]}
        />
        <Bar dataKey={`${home} win`} fill="hsl(var(--pitch))" radius={[4, 4, 0, 0]} maxBarSize={24} />
        <Bar dataKey="Draw" fill="hsl(var(--line))" radius={[4, 4, 0, 0]} maxBarSize={24} />
        <Bar dataKey={`${away} win`} fill="hsl(var(--signal))" radius={[4, 4, 0, 0]} maxBarSize={24} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Prediction difference chart ───────────────────────────────────────────────

function PredictionDiffChart({
  home,
  prediction,
}: {
  home: string;
  prediction: HybridPrediction;
}) {
  const ensembleHomeWin = prediction.ensemble.home_win * 100;

  const data = Object.entries(prediction.ml_predictions).map(([k, v]) => ({
    model: MODEL_LABELS[k] ?? k,
    diff: parseFloat(((v.home_win - prediction.ensemble.home_win) * 100).toFixed(2)),
    fill: v.home_win > prediction.ensemble.home_win ? "hsl(var(--pitch))" : "hsl(var(--signal))",
  }));

  data.unshift({
    model: "Stat",
    diff: parseFloat(((prediction.statistical.home_win - prediction.ensemble.home_win) * 100).toFixed(2)),
    fill: prediction.statistical.home_win > prediction.ensemble.home_win ? "hsl(var(--pitch))" : "hsl(var(--signal))",
  });

  return (
    <div className="space-y-2">
      <p className="kicker">{home} win — deviation from ensemble</p>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ left: 0, right: 8, top: 4, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" vertical={false} />
          <XAxis dataKey="model" stroke="hsl(var(--muted))" fontSize={11} tick={{ fill: "hsl(var(--muted))" }} />
          <YAxis tickFormatter={(v) => `${v > 0 ? "+" : ""}${v}%`} stroke="hsl(var(--muted))" fontSize={11} />
          <Tooltip
            formatter={(v: number) => [`${v > 0 ? "+" : ""}${v.toFixed(1)}% vs ensemble`, "Deviation"]}
            contentStyle={{
              background: "hsl(var(--elevated))", border: "1px solid hsl(var(--line))",
              borderRadius: 8, fontSize: 11,
            }}
          />
          <ReferenceLine y={0} stroke="hsl(var(--muted))" strokeDasharray="4 4" />
          <Bar dataKey="diff" radius={4} maxBarSize={24}>
            {data.map((d, i) => <Cell key={i} fill={d.fill} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Full comparison table ─────────────────────────────────────────────────────

function ComparisonTable({ home, away, prediction }: { home: string; away: string; prediction: HybridPrediction }) {
  const rows = [
    { label: "Statistical", key: "statistical", probs: prediction.statistical, accent: "hsl(45 95% 58%)" },
    ...Object.entries(prediction.ml_predictions).map(([k, v]) => ({
      label: MODEL_LABELS[k] ?? k,
      key: k,
      probs: v,
      accent: MODEL_COLOURS[k] ?? "hsl(var(--muted))",
    })),
    { label: "Ensemble", key: "ensemble", probs: prediction.ensemble, accent: "hsl(var(--pitch))" },
  ];

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="kicker text-left border-b border-line">
          <th className="py-2 font-normal">Model</th>
          <th className="py-2 font-normal text-right text-pitch">{home}</th>
          <th className="py-2 font-normal text-right text-muted">Draw</th>
          <th className="py-2 font-normal text-right text-signal">{away}</th>
          <th className="py-2 font-normal text-right text-muted hidden sm:table-cell">Leader</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(({ label, key, probs, accent }) => {
          const best = probs.home_win > probs.away_win && probs.home_win > probs.draw
            ? home : probs.away_win > probs.home_win && probs.away_win > probs.draw
            ? away : "Draw";
          const isBold = key === "ensemble";
          return (
            <tr key={key} className={`border-b border-line/50 ${isBold ? "font-semibold" : ""}`}>
              <td className="py-2" style={{ color: accent }}>{label}</td>
              <td className="py-2 text-right tnum text-pitch">{pct(probs.home_win)}</td>
              <td className="py-2 text-right tnum text-muted">{pct(probs.draw)}</td>
              <td className="py-2 text-right tnum text-signal">{pct(probs.away_win)}</td>
              <td className="py-2 text-right text-muted text-xs hidden sm:table-cell">{best}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ── SHAP explanation ──────────────────────────────────────────────────────────

function ExplanationPanel({ prediction }: { prediction: HybridPrediction }) {
  const { explanation } = prediction;
  if (!explanation?.narrative) return null;
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted leading-relaxed bg-elevated rounded-lg p-3 border border-line">
        {explanation.narrative}
      </p>
      <div className="grid sm:grid-cols-2 gap-4">
        {explanation.top_positive.length > 0 && (
          <div>
            <p className="kicker text-pitch mb-2">Favours {prediction.home_team}</p>
            {explanation.top_positive.map((f) => (
              <div key={f.name} className="flex justify-between text-xs py-1.5 border-b border-line/40">
                <span className="text-muted">{f.display_name}</span>
                <span className="text-pitch tnum">+{f.impact.toFixed(3)}</span>
              </div>
            ))}
          </div>
        )}
        {explanation.top_negative.length > 0 && (
          <div>
            <p className="kicker text-signal mb-2">Favours {prediction.away_team}</p>
            {explanation.top_negative.map((f) => (
              <div key={f.name} className="flex justify-between text-xs py-1.5 border-b border-line/40">
                <span className="text-muted">{f.display_name}</span>
                <span className="text-signal tnum">{f.impact.toFixed(3)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ComparePage() {
  const { data: teams } = useTeams();
  const teamNames = useMemo(() => (teams ?? []).map((t) => t.name).sort(), [teams]);

  const [home, setHome] = useState("France");
  const [away, setAway] = useState("Brazil");
  const [prediction, setPrediction] = useState<HybridPrediction | null>(null);

  const mlMutation = useMLPredict();

  const predict = () => {
    mlMutation.mutate(
      { home_team: home, away_team: away, include_shap: true },
      { onSuccess: (r) => setPrediction(r) },
    );
  };

  return (
    <div className="space-y-8">
      <header>
        <p className="kicker mb-2">Model comparison</p>
        <h1 className="display text-4xl">Prediction comparison</h1>
        <p className="text-muted mt-2 max-w-2xl">
          Statistical, 5 ML models, and ensemble — compared side by side with
          deviation charts, confidence scores, and SHAP explanations.
        </p>
      </header>

      {/* Selector */}
      <Card>
        <CardBody>
          <div className="flex gap-3 items-end flex-wrap">
            <TeamInput
              label="Home team" value={home} onChange={setHome}
              options={teamNames.length ? teamNames : [home]}
            />
            <div className="text-muted pb-2.5 font-bold shrink-0">vs</div>
            <TeamInput
              label="Away team" value={away} onChange={setAway}
              options={teamNames.length ? teamNames : [away]}
            />
            <Button onClick={predict} disabled={mlMutation.isPending || home === away} size="md">
              {mlMutation.isPending ? "Comparing…" : "Compare"}
            </Button>
          </div>
        </CardBody>
      </Card>

      {mlMutation.isError && (
        <p className="text-signal text-sm">{(mlMutation.error as Error).message}</p>
      )}

      {mlMutation.isPending && (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
      )}

      <AnimatePresence>
        {prediction && !mlMutation.isPending && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
            {/* Match title */}
            <div className="text-center">
              <div className="display text-3xl">
                {prediction.home_team}
                <span className="text-muted mx-3 text-2xl">vs</span>
                {prediction.away_team}
              </div>
              <p className="text-muted text-sm mt-1">
                Expected {prediction.expected_scoreline} · xG {prediction.home_xg.toFixed(2)} – {prediction.away_xg.toFixed(2)}
              </p>
            </div>

            {/* Agreement + confidence */}
            <Card>
              <CardHeader><span className="kicker">Model consensus</span></CardHeader>
              <CardBody>
                <AgreementMeter
                  agreement={prediction.model_agreement}
                  confidence={prediction.confidence_score}
                />
              </CardBody>
            </Card>

            <div className="grid gap-5 lg:grid-cols-2">
              {/* Probability distribution */}
              <Card>
                <CardHeader><span className="kicker">Home-win probability by model</span></CardHeader>
                <CardBody>
                  <ProbabilityDistribution home={prediction.home_team} away={prediction.away_team} prediction={prediction} />
                </CardBody>
              </Card>

              {/* Deviation from ensemble */}
              <Card>
                <CardHeader><span className="kicker">Deviation from ensemble</span></CardHeader>
                <CardBody>
                  <PredictionDiffChart home={prediction.home_team} prediction={prediction} />
                </CardBody>
              </Card>
            </div>

            {/* Full table */}
            <Card>
              <CardHeader><span className="kicker">Full probability table</span></CardHeader>
              <CardBody className="overflow-x-auto">
                <ComparisonTable home={prediction.home_team} away={prediction.away_team} prediction={prediction} />
              </CardBody>
            </Card>

            {/* SHAP explanation */}
            <Card>
              <CardHeader><span className="kicker">AI explanation (ensemble SHAP)</span></CardHeader>
              <CardBody>
                <ExplanationPanel prediction={prediction} />
              </CardBody>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
