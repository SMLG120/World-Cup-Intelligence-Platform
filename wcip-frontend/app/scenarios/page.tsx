"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Cell, ReferenceLine, Legend,
} from "recharts";
import { useCompareScenarios, useTeams } from "@/lib/queries";
import { NEUTRAL_MODIFIERS, TeamModifiers } from "@/lib/types";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { pct } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ScenarioDraft {
  label: string;
  team: string;
  mods: TeamModifiers;
}

const RUN_OPTIONS = [1000, 2000, 5000];

const FIELDS: { key: keyof TeamModifiers; label: string; min: number; max: number; step: number; hint: string }[] = [
  { key: "injury", label: "Availability", min: 0.4, max: 1, step: 0.05, hint: "Squad availability multiplier" },
  { key: "morale", label: "Morale", min: 0.7, max: 1.3, step: 0.05, hint: "Team morale & cohesion" },
  { key: "attack", label: "Form", min: 0.6, max: 1.6, step: 0.05, hint: "Recent attack form" },
];

const ACCENT_COLOURS = [
  "hsl(75 95% 55%)",
  "hsl(200 90% 62%)",
  "hsl(280 70% 68%)",
];
const KICKER_COLOURS = ["text-pitch", "text-[hsl(200_90%_62%)]", "text-[hsl(280_70%_68%)]"];
const BORDER_COLOURS = ["border-pitch/40", "border-[hsl(200_90%_62%/0.4)]", "border-[hsl(280_70%_68%/0.4)]"];

// ── Scenario card ─────────────────────────────────────────────────────────────

function ScenarioCard({
  sc, i, teams, onUpdate, onRemove,
}: {
  sc: ScenarioDraft;
  i: number;
  teams: string[];
  onUpdate: (patch: Partial<ScenarioDraft>) => void;
  onRemove?: () => void;
}) {
  return (
    <Card className={`border ${BORDER_COLOURS[i]}`}>
      <CardHeader className="flex items-center justify-between py-3">
        <input
          value={sc.label}
          onChange={(e) => onUpdate({ label: e.target.value })}
          className={`bg-transparent kicker focus:outline-none ${KICKER_COLOURS[i]} w-32 truncate`}
        />
        {onRemove && (
          <button onClick={onRemove} className="text-xs text-muted hover:text-signal transition-colors">
            Remove
          </button>
        )}
      </CardHeader>
      <CardBody className="space-y-4">
        <div>
          <span className="kicker block mb-1.5">Adjust team</span>
          <select
            value={sc.team}
            onChange={(e) => onUpdate({ team: e.target.value })}
            className="w-full px-3 py-2 rounded-md border border-line bg-elevated text-fg text-sm focus:outline-none focus:border-pitch"
          >
            <option value="">— Baseline (no change) —</option>
            {teams.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>

        <AnimatePresence>
          {sc.team && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="space-y-4 overflow-hidden"
            >
              {FIELDS.map((f) => (
                <div key={f.key} className="space-y-1">
                  <div className="flex justify-between">
                    <span className="text-xs text-muted">{f.label}</span>
                    <span className="tnum text-xs text-fg">{sc.mods[f.key].toFixed(2)}×</span>
                  </div>
                  <input
                    type="range" min={f.min} max={f.max} step={f.step}
                    value={sc.mods[f.key]}
                    onChange={(e) => onUpdate({ mods: { ...sc.mods, [f.key]: parseFloat(e.target.value) } })}
                    className="w-full accent-[hsl(var(--pitch))] h-1.5 cursor-pointer"
                  />
                  <p className="text-[10px] text-muted">{f.hint}</p>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </CardBody>
    </Card>
  );
}

// ── Delta chart ───────────────────────────────────────────────────────────────

function DeltaChart({
  rows,
  scenarios,
}: {
  rows: { team: string; values: number[] }[];
  scenarios: { label: string }[];
}) {
  if (scenarios.length < 2) return null;

  const data = rows.slice(0, 10).map((row) => ({
    team: row.team.length > 10 ? row.team.slice(0, 10) + "…" : row.team,
    delta: parseFloat(((row.values[row.values.length - 1] - row.values[0]) * 100).toFixed(2)),
  }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 40, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" horizontal={false} />
        <XAxis
          type="number"
          tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`}
          stroke="hsl(var(--muted))" fontSize={10}
        />
        <YAxis
          type="category" dataKey="team" width={80}
          stroke="hsl(var(--muted))" fontSize={10} tick={{ fill: "hsl(var(--fg))" }}
        />
        <Tooltip
          formatter={(v: number) => [`${v > 0 ? "+" : ""}${v.toFixed(2)}%`, `Δ champion (${scenarios[scenarios.length - 1].label} vs ${scenarios[0].label})`]}
          contentStyle={{
            background: "hsl(var(--elevated))", border: "1px solid hsl(var(--line))",
            borderRadius: 8, fontSize: 11,
          }}
          labelStyle={{ color: "hsl(var(--fg))", fontWeight: "bold" }}
        />
        <ReferenceLine x={0} stroke="hsl(var(--muted))" strokeDasharray="4 4" />
        <Bar dataKey="delta" radius={4} maxBarSize={22}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.delta >= 0 ? "hsl(var(--pitch))" : "hsl(var(--signal))"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Multi-scenario champion chart ─────────────────────────────────────────────

function MultiScenarioChart({
  rows,
  scenarios,
}: {
  rows: { team: string; values: number[] }[];
  scenarios: { label: string }[];
}) {
  const data = rows.slice(0, 10).map((row) => {
    const entry: Record<string, string | number> = {
      team: row.team.length > 10 ? row.team.slice(0, 10) + "…" : row.team,
    };
    scenarios.forEach((sc, i) => {
      entry[sc.label] = parseFloat((row.values[i] * 100).toFixed(2));
    });
    return entry;
  });

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" vertical={false} />
        <XAxis dataKey="team" stroke="hsl(var(--muted))" fontSize={10} tick={{ fill: "hsl(var(--muted))" }} />
        <YAxis tickFormatter={(v) => `${v}%`} stroke="hsl(var(--muted))" fontSize={10} />
        <Tooltip
          formatter={(v: number) => [`${v.toFixed(1)}%`]}
          contentStyle={{
            background: "hsl(var(--elevated))", border: "1px solid hsl(var(--line))",
            borderRadius: 8, fontSize: 11,
          }}
          labelStyle={{ color: "hsl(var(--fg))", fontWeight: "bold" }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: "hsl(var(--muted))" }} />
        {scenarios.map((sc, i) => (
          <Bar key={sc.label} dataKey={sc.label} fill={ACCENT_COLOURS[i]} radius={[4, 4, 0, 0]} maxBarSize={20} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ScenariosPage() {
  const { data: teamsData } = useTeams();
  const compare = useCompareScenarios();
  const [runs, setRuns] = useState(2000);
  const [scenarios, setScenarios] = useState<ScenarioDraft[]>([
    { label: "Baseline", team: "", mods: { ...NEUTRAL_MODIFIERS } },
    { label: "What-if A", team: "France", mods: { ...NEUTRAL_MODIFIERS, injury: 0.75 } },
  ]);

  const teamNames = (teamsData ?? []).map((t) => t.name).sort();

  const update = (i: number, patch: Partial<ScenarioDraft>) =>
    setScenarios((s) => s.map((sc, idx) => (idx === i ? { ...sc, ...patch } : sc)));

  const addScenario = () => setScenarios((s) =>
    s.length >= 3 ? s : [...s, {
      label: `What-if ${String.fromCharCode(65 + s.length - 1)}`,
      team: "Brazil",
      mods: { ...NEUTRAL_MODIFIERS },
    }]);

  const removeScenario = (i: number) =>
    setScenarios((s) => s.length <= 2 ? s : s.filter((_, idx) => idx !== i));

  const run = () =>
    compare.mutate({
      edition: "2022",
      runs,
      scenarios: scenarios.map((sc) => ({
        label: sc.label,
        overrides: sc.team ? { [sc.team]: sc.mods } : {},
      })),
    });

  const result = compare.data;

  const rows = (() => {
    if (!result) return [];
    const order = result.scenarios[0].result.teams.slice(0, 12).map((t) => t.team);
    return order.map((team) => ({
      team,
      values: result.scenarios.map(
        (sc) => sc.result.teams.find((t) => t.team === team)?.champion ?? 0,
      ),
    }));
  })();

  return (
    <div className="space-y-8">
      <header>
        <p className="kicker mb-2">Scenario lab</p>
        <h1 className="display text-4xl">Compare what-ifs</h1>
        <p className="text-muted mt-2 max-w-2xl">
          Configure up to three scenarios — adjust a nation's availability, morale, or form
          — then run them side by side to see champion probability changes with impact charts.
        </p>
      </header>

      {/* Scenario cards */}
      <div className="grid gap-4 md:grid-cols-3">
        {scenarios.map((sc, i) => (
          <ScenarioCard
            key={i}
            sc={sc} i={i}
            teams={teamNames}
            onUpdate={(patch) => update(i, patch)}
            onRemove={i >= 2 ? () => removeScenario(i) : undefined}
          />
        ))}
        {scenarios.length < 3 && (
          <button
            onClick={addScenario}
            className="rounded-lg border border-dashed border-line text-muted hover:text-pitch hover:border-pitch
              transition-colors min-h-[120px] flex items-center justify-center text-sm"
          >
            + Add scenario
          </button>
        )}
      </div>

      {/* Run controls */}
      <Card>
        <CardBody className="flex flex-wrap items-end gap-4">
          <div>
            <span className="kicker block mb-1.5">Simulations each</span>
            <div className="flex gap-2">
              {RUN_OPTIONS.map((r) => (
                <button
                  key={r}
                  onClick={() => setRuns(r)}
                  className={`tnum px-3 h-10 rounded-md border text-sm transition-colors ${
                    runs === r ? "border-pitch text-pitch bg-pitch/10" : "border-line text-muted hover:text-fg"
                  }`}
                >
                  {r.toLocaleString()}
                </button>
              ))}
            </div>
          </div>
          <Button size="lg" onClick={run} disabled={compare.isPending}>
            {compare.isPending ? "Comparing…" : "Compare scenarios"}
          </Button>
        </CardBody>
      </Card>

      {compare.isPending && <Skeleton className="h-72" />}
      {compare.isError && <p className="text-signal text-sm">{(compare.error as Error).message}</p>}

      <AnimatePresence>
        {result && !compare.isPending && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
            <div className="grid gap-5 lg:grid-cols-2">
              {/* Multi-scenario comparison chart */}
              <Card>
                <CardHeader><span className="kicker">Champion probability by scenario</span></CardHeader>
                <CardBody>
                  <MultiScenarioChart rows={rows} scenarios={result.scenarios} />
                </CardBody>
              </Card>

              {/* Delta chart */}
              <Card>
                <CardHeader>
                  <span className="kicker">
                    Delta: {result.scenarios[result.scenarios.length - 1].label} vs {result.scenarios[0].label}
                  </span>
                </CardHeader>
                <CardBody>
                  <DeltaChart rows={rows} scenarios={result.scenarios} />
                </CardBody>
              </Card>
            </div>

            {/* Full table */}
            <Card>
              <CardHeader><span className="kicker">Champion probability — all scenarios</span></CardHeader>
              <CardBody className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="kicker text-left border-b border-line">
                      <th className="pb-2 font-normal">Team</th>
                      {result.scenarios.map((sc, i) => (
                        <th key={i} className={`pb-2 font-normal text-right ${KICKER_COLOURS[i]}`}>
                          {sc.label}
                        </th>
                      ))}
                      <th className="pb-2 font-normal text-right text-muted">Δ vs base</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => {
                      const delta = row.values[row.values.length - 1] - row.values[0];
                      return (
                        <tr key={row.team} className="border-b border-line/50 hover:bg-elevated/50 transition-colors">
                          <td className="py-1.5">{row.team}</td>
                          {row.values.map((v, i) => (
                            <td key={i} className="py-1.5 text-right tnum text-muted">{pct(v)}</td>
                          ))}
                          <td className={`py-1.5 text-right tnum font-semibold ${
                            delta > 0.001 ? "text-pitch" : delta < -0.001 ? "text-signal" : "text-muted"
                          }`}>
                            {delta > 0 ? "+" : ""}{pct(delta)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </CardBody>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
