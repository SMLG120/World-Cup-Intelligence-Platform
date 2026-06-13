"use client";

import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine, LabelList,
} from "recharts";
import { useTeams, useMLExplanations, useMLFeatures } from "@/lib/queries";
import type { ExplanationFactor } from "@/lib/types";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

// ── Model options ─────────────────────────────────────────────────────────────

const MODELS = [
  { value: "xgboost", label: "XGBoost" },
  { value: "catboost", label: "CatBoost" },
  { value: "lightgbm", label: "LightGBM" },
  { value: "random_forest", label: "Random Forest" },
  { value: "logistic", label: "Logistic Regression" },
];

// ── SHAP waterfall chart ──────────────────────────────────────────────────────

function SHAPWaterfall({
  positive,
  negative,
}: {
  positive: ExplanationFactor[];
  negative: ExplanationFactor[];
}) {
  const allFactors = [
    ...positive.map((f) => ({ ...f, side: "positive" as const })),
    ...negative.map((f) => ({ ...f, side: "negative" as const })),
  ].sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact));

  const data = allFactors.map((f) => ({
    name: f.display_name,
    value: parseFloat(f.impact.toFixed(4)),
    fill: f.impact >= 0 ? "hsl(var(--pitch))" : "hsl(var(--signal))",
    side: f.side,
  }));

  return (
    <ResponsiveContainer width="100%" height={Math.max(280, data.length * 36)}>
      <BarChart data={data} layout="vertical" margin={{ left: 12, right: 60, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" horizontal={false} />
        <XAxis
          type="number"
          tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(3)}`}
          stroke="hsl(var(--muted))" fontSize={10}
        />
        <YAxis
          type="category" dataKey="name" width={140}
          stroke="hsl(var(--muted))" fontSize={10} tick={{ fill: "hsl(var(--fg))" }}
        />
        <Tooltip
          formatter={(v: number) => [`${v > 0 ? "+" : ""}${v.toFixed(4)}`, "SHAP impact"]}
          contentStyle={{
            background: "hsl(var(--elevated))", border: "1px solid hsl(var(--line))",
            borderRadius: 8, fontSize: 11,
          }}
          labelStyle={{ color: "hsl(var(--fg))", fontWeight: "bold" }}
          cursor={{ fill: "hsl(var(--elevated))" }}
        />
        <ReferenceLine x={0} stroke="hsl(var(--muted))" strokeDasharray="4 4" />
        <Bar dataKey="value" radius={4} maxBarSize={22}>
          {data.map((d, i) => <Cell key={i} fill={d.fill} />)}
          <LabelList
            dataKey="value"
            position="right"
            formatter={(v: number) => `${v > 0 ? "+" : ""}${v.toFixed(3)}`}
            style={{ fill: "hsl(var(--muted))", fontSize: 10, fontFamily: "var(--font-mono)" }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Feature importance chart ──────────────────────────────────────────────────

function FeatureImportanceChart({ features }: { features: Record<string, number> }) {
  const sorted = Object.entries(features)
    .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
    .slice(0, 12);

  const data = sorted.map(([name, value]) => ({
    name: name.replace(/_/g, " "),
    value: parseFloat(value.toFixed(4)),
    fill: value >= 0 ? "hsl(var(--pitch))" : "hsl(var(--signal))",
  }));

  return (
    <ResponsiveContainer width="100%" height={Math.max(280, data.length * 30)}>
      <BarChart data={data} layout="vertical" margin={{ left: 12, right: 48, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" horizontal={false} />
        <XAxis
          type="number"
          tickFormatter={(v) => v.toFixed(3)}
          stroke="hsl(var(--muted))" fontSize={10}
        />
        <YAxis
          type="category" dataKey="name" width={140}
          stroke="hsl(var(--muted))" fontSize={10} tick={{ fill: "hsl(var(--fg))" }}
        />
        <Tooltip
          formatter={(v: number) => [v.toFixed(4), "Feature value (home − away diff)"]}
          contentStyle={{
            background: "hsl(var(--elevated))", border: "1px solid hsl(var(--line))",
            borderRadius: 8, fontSize: 11,
          }}
          labelStyle={{ color: "hsl(var(--fg))", fontWeight: "bold" }}
          cursor={{ fill: "hsl(var(--elevated))" }}
        />
        <ReferenceLine x={0} stroke="hsl(var(--muted))" strokeDasharray="4 4" />
        <Bar dataKey="value" radius={4} maxBarSize={20}>
          {data.map((d, i) => <Cell key={i} fill={d.fill} />)}
          <LabelList
            dataKey="value"
            position="right"
            formatter={(v: number) => v.toFixed(3)}
            style={{ fill: "hsl(var(--muted))", fontSize: 10, fontFamily: "var(--font-mono)" }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Contribution breakdown ────────────────────────────────────────────────────

function ContributionBreakdown({
  home,
  away,
  positive,
  negative,
}: {
  home: string;
  away: string;
  positive: ExplanationFactor[];
  negative: ExplanationFactor[];
}) {
  const totalPositive = positive.reduce((s, f) => s + f.impact, 0);
  const totalNegative = negative.reduce((s, f) => s + f.impact, 0);

  return (
    <div className="grid sm:grid-cols-2 gap-6">
      <div>
        <div className="flex items-baseline justify-between mb-3">
          <p className="kicker text-pitch">Favours {home}</p>
          <span className="tnum text-xs text-pitch">+{totalPositive.toFixed(3)} net</span>
        </div>
        <div className="space-y-2">
          {positive.map((f) => (
            <motion.div
              key={f.name}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center gap-3"
            >
              <div className="flex-1">
                <div className="flex justify-between text-xs mb-0.5">
                  <span className="text-muted">{f.display_name}</span>
                  <span className="text-pitch tnum">+{f.impact.toFixed(3)}</span>
                </div>
                <div className="h-1.5 bg-elevated rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${(f.impact / totalPositive) * 100}%` }}
                    transition={{ duration: 0.5, ease: "easeOut" }}
                    className="h-full bg-pitch rounded-full"
                  />
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      <div>
        <div className="flex items-baseline justify-between mb-3">
          <p className="kicker text-signal">Favours {away}</p>
          <span className="tnum text-xs text-signal">{totalNegative.toFixed(3)} net</span>
        </div>
        <div className="space-y-2">
          {negative.map((f) => (
            <motion.div
              key={f.name}
              initial={{ opacity: 0, x: 8 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center gap-3"
            >
              <div className="flex-1">
                <div className="flex justify-between text-xs mb-0.5">
                  <span className="text-muted">{f.display_name}</span>
                  <span className="text-signal tnum">{f.impact.toFixed(3)}</span>
                </div>
                <div className="h-1.5 bg-elevated rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${(Math.abs(f.impact) / Math.abs(totalNegative)) * 100}%` }}
                    transition={{ duration: 0.5, ease: "easeOut" }}
                    className="h-full bg-signal rounded-full"
                  />
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Team selector ─────────────────────────────────────────────────────────────

function TeamSelect({
  label, value, onChange, options,
}: {
  label: string; value: string; onChange: (v: string) => void; options: string[];
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

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ExplainPage() {
  const { data: teams } = useTeams();
  const teamNames = useMemo(() => (teams ?? []).map((t) => t.name).sort(), [teams]);

  const [home, setHome] = useState("France");
  const [away, setAway] = useState("Brazil");
  const [model, setModel] = useState("xgboost");
  const [submitted, setSubmitted] = useState(false);

  const explanationQuery = useMLExplanations(home, away, model, undefined, submitted);
  const featuresQuery = useMLFeatures(home, away, undefined, submitted);

  const explanation = explanationQuery.data;
  const features = featuresQuery.data?.features;

  const loading = explanationQuery.isLoading || featuresQuery.isLoading;

  function run() {
    if (!submitted) {
      setSubmitted(true);
    } else {
      // Re-trigger by resetting and setting again (both queries are auto-fetched by key)
      setSubmitted(false);
      setTimeout(() => setSubmitted(true), 0);
    }
  }

  return (
    <div className="space-y-8">
      <header>
        <p className="kicker mb-2">Model explainability</p>
        <h1 className="display text-4xl">Why did the model predict this?</h1>
        <p className="text-muted mt-2 max-w-2xl">
          SHAP values show the contribution of each feature to the prediction. Positive values
          favour the home team; negative values favour the away team. Feature values are
          home−away differentials.
        </p>
      </header>

      {/* Selector */}
      <Card>
        <CardBody className="space-y-4">
          <div className="flex gap-3 items-end flex-wrap">
            <TeamSelect
              label="Home team" value={home} onChange={setHome}
              options={teamNames.length ? teamNames : [home]}
            />
            <div className="text-muted pb-2.5 font-bold shrink-0">vs</div>
            <TeamSelect
              label="Away team" value={away} onChange={setAway}
              options={teamNames.length ? teamNames : [away]}
            />
            <div className="flex-1 min-w-36">
              <label className="kicker block mb-1.5">Model</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full px-3 py-2.5 rounded-md border border-line bg-elevated text-fg text-sm
                  focus:outline-none focus:border-pitch transition-colors"
              >
                {MODELS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>
            <Button onClick={run} disabled={loading || home === away} size="md">
              {loading ? "Explaining…" : "Explain"}
            </Button>
          </div>
        </CardBody>
      </Card>

      {(explanationQuery.isError || featuresQuery.isError) && (
        <p className="text-signal text-sm">
          {((explanationQuery.error ?? featuresQuery.error) as Error)?.message}
        </p>
      )}

      {loading && (
        <div className="space-y-4">
          <Skeleton className="h-72" />
          <Skeleton className="h-48" />
        </div>
      )}

      <AnimatePresence>
        {explanation && !loading && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
            {/* Narrative */}
            <Card>
              <CardBody>
                <p className="kicker mb-3">
                  {home} vs {away} — {MODELS.find((m) => m.value === model)?.label ?? model}
                </p>
                <p className="text-muted leading-relaxed">
                  {explanation.narrative}
                </p>
              </CardBody>
            </Card>

            {/* Contribution breakdown */}
            <Card>
              <CardHeader><span className="kicker">Contribution breakdown</span></CardHeader>
              <CardBody>
                <ContributionBreakdown
                  home={home} away={away}
                  positive={explanation.top_positive}
                  negative={explanation.top_negative}
                />
              </CardBody>
            </Card>

            {/* SHAP waterfall */}
            <Card>
              <CardHeader><span className="kicker">SHAP waterfall — impact on home-win probability</span></CardHeader>
              <CardBody>
                <SHAPWaterfall
                  positive={explanation.top_positive}
                  negative={explanation.top_negative}
                />
              </CardBody>
            </Card>

            {/* Feature values */}
            {features && (
              <Card>
                <CardHeader>
                  <span className="kicker">Feature vector — {home} − {away} differentials</span>
                </CardHeader>
                <CardBody>
                  <FeatureImportanceChart features={features} />
                </CardBody>
              </Card>
            )}

            {/* Raw table */}
            <Card>
              <CardHeader><span className="kicker">Factor table</span></CardHeader>
              <CardBody className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="kicker border-b border-line">
                      <th className="py-2 text-left font-normal">Factor</th>
                      <th className="py-2 text-right font-normal">SHAP impact</th>
                      <th className="py-2 text-right font-normal">Feature value</th>
                      <th className="py-2 text-right font-normal hidden sm:table-cell">Direction</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...explanation.top_positive, ...explanation.top_negative]
                      .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact))
                      .map((f) => (
                        <tr key={f.name} className="border-b border-line/40 hover:bg-elevated/50 transition-colors">
                          <td className="py-2 text-fg">{f.display_name}</td>
                          <td className={`py-2 text-right tnum font-semibold ${f.impact >= 0 ? "text-pitch" : "text-signal"}`}>
                            {f.impact >= 0 ? "+" : ""}{f.impact.toFixed(4)}
                          </td>
                          <td className="py-2 text-right tnum text-muted">{f.value.toFixed(3)}</td>
                          <td className="py-2 text-right hidden sm:table-cell">
                            <span className={`text-xs ${f.impact >= 0 ? "text-pitch" : "text-signal"}`}>
                              {f.impact >= 0 ? `↑ ${home}` : `↑ ${away}`}
                            </span>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </CardBody>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {!submitted && (
        <div className="py-20 text-center text-muted">
          <div className="text-4xl mb-3">🔍</div>
          <p>Select two teams and a model, then click Explain to see SHAP feature attribution.</p>
        </div>
      )}
    </div>
  );
}
