"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { useCompareScenarios, useTeams } from "@/lib/queries";
import { NEUTRAL_MODIFIERS, TeamModifiers } from "@/lib/types";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Skeleton } from "@/components/ui/skeleton";
import { pct } from "@/lib/utils";

interface ScenarioDraft {
  label: string;
  team: string;       // "" = baseline / no override
  mods: TeamModifiers;
}

const RUN_OPTIONS = [1000, 2000, 5000];

const FIELDS: { key: keyof TeamModifiers; label: string; min: number; max: number; step: number }[] = [
  { key: "injury", label: "Availability", min: 0.4, max: 1, step: 0.05 },
  { key: "morale", label: "Morale", min: 0.7, max: 1.3, step: 0.05 },
  { key: "attack", label: "Form", min: 0.6, max: 1.6, step: 0.05 },
];

const COLORS = ["text-pitch", "text-signal", "text-sky"];

export default function ScenariosPage() {
  const { data: teams } = useTeams();
  const compare = useCompareScenarios();
  const [runs, setRuns] = useState(2000);
  const [scenarios, setScenarios] = useState<ScenarioDraft[]>([
    { label: "Baseline", team: "", mods: { ...NEUTRAL_MODIFIERS } },
    { label: "What-if A", team: "France", mods: { ...NEUTRAL_MODIFIERS, injury: 0.75 } },
  ]);

  const update = (i: number, patch: Partial<ScenarioDraft>) =>
    setScenarios((s) => s.map((sc, idx) => (idx === i ? { ...sc, ...patch } : sc)));

  const addScenario = () =>
    setScenarios((s) =>
      s.length >= 3 ? s : [...s, { label: `What-if ${String.fromCharCode(65 + s.length - 1)}`, team: "Brazil", mods: { ...NEUTRAL_MODIFIERS } }]);

  const removeScenario = (i: number) =>
    setScenarios((s) => (s.length <= 2 ? s : s.filter((_, idx) => idx !== i)));

  const run = () =>
    compare.mutate({
      edition: "2022",
      runs,
      scenarios: scenarios.map((sc) => ({
        label: sc.label,
        overrides: sc.team ? { [sc.team]: sc.mods } : {},
      })),
    });

  // Build a comparison table keyed by team, using the first scenario's ranking.
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
          Configure up to three scenarios — adjust a key nation&apos;s
          availability, morale, or form — then run them side by side to see how
          champion probabilities shift.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        {scenarios.map((sc, i) => (
          <Card key={i}>
            <CardHeader className="flex items-center justify-between">
              <input
                value={sc.label}
                onChange={(e) => update(i, { label: e.target.value })}
                className={`bg-transparent kicker focus:outline-none ${COLORS[i]} w-28`}
              />
              {i >= 2 && (
                <button onClick={() => removeScenario(i)} className="text-xs text-muted hover:text-signal">
                  Remove
                </button>
              )}
            </CardHeader>
            <CardBody className="space-y-3">
              <div>
                <span className="kicker block mb-1.5">Adjust team</span>
                <Select value={sc.team} onChange={(e) => update(i, { team: e.target.value })}>
                  <option value="">— Baseline (no change) —</option>
                  {teams?.map((t) => <option key={t.id} value={t.name}>{t.name}</option>)}
                </Select>
              </div>
              {sc.team && FIELDS.map((f) => (
                <Slider
                  key={f.key}
                  label={f.label}
                  display={`${sc.mods[f.key].toFixed(2)}×`}
                  min={f.min} max={f.max} step={f.step} value={sc.mods[f.key]}
                  onChange={(e) => update(i, { mods: { ...sc.mods, [f.key]: parseFloat(e.target.value) } })}
                />
              ))}
            </CardBody>
          </Card>
        ))}
        {scenarios.length < 3 && (
          <button
            onClick={addScenario}
            className="rounded-lg border border-dashed border-line text-muted hover:text-pitch hover:border-pitch transition-colors min-h-[120px] flex items-center justify-center"
          >
            + Add scenario
          </button>
        )}
      </div>

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
      {compare.isError && <p className="text-signal">{(compare.error as Error).message}</p>}

      {result && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <Card>
            <CardHeader><span className="kicker">Champion probability by scenario</span></CardHeader>
            <CardBody className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="kicker text-left border-b border-line">
                    <th className="pb-2 font-normal">Team</th>
                    {result.scenarios.map((sc, i) => (
                      <th key={i} className={`pb-2 font-normal text-right ${COLORS[i]}`}>{sc.label}</th>
                    ))}
                    <th className="pb-2 font-normal text-right">Δ vs base</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const delta = row.values[row.values.length - 1] - row.values[0];
                    return (
                      <tr key={row.team} className="border-b border-line/50">
                        <td className="py-1.5">{row.team}</td>
                        {row.values.map((v, i) => (
                          <td key={i} className="py-1.5 text-right tnum text-muted">{pct(v)}</td>
                        ))}
                        <td className={`py-1.5 text-right tnum ${delta > 0.001 ? "text-pitch" : delta < -0.001 ? "text-signal" : "text-muted"}`}>
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
    </div>
  );
}
