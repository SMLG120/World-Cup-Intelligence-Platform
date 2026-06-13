"use client";

import { useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { useWC2026Simulate } from "@/lib/queries";
import type { TeamProbability } from "@/lib/types";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SaveSimulationButton } from "@/components/save-simulation-button";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { DataFreshnessStrip } from "@/components/data-freshness";
import { pct, ordinal } from "@/lib/utils";

// ── Run options ───────────────────────────────────────────────────────────────

const RUN_OPTIONS: [number, string][] = [
  [1000, "1K"], [5000, "5K"], [10000, "10K"], [50000, "50K"],
];

// ── Animated probability bar ──────────────────────────────────────────────────

function TeamRow({ team, rank, max }: { team: TeamProbability; rank: number; max: number }) {
  const champPct = team.champion * 100;
  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: rank * 0.025, type: "spring", stiffness: 200 }}
      className="flex items-center gap-3 py-2 border-b border-line/40 last:border-0 hover:bg-elevated/60 px-1 rounded transition-colors"
    >
      <span className="tnum text-xs text-muted w-5 shrink-0">{rank + 1}</span>
      <span className="text-sm text-fg flex-1 min-w-0 truncate">{team.team}</span>
      <div className="flex-1 max-w-[120px] h-1.5 bg-elevated rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${(champPct / max) * 100}%` }}
          transition={{ delay: rank * 0.025 + 0.2, duration: 0.6, ease: "easeOut" }}
          className="h-full bg-pitch rounded-full"
        />
      </div>
      <div className="text-right shrink-0 w-20 hidden sm:flex justify-end gap-3">
        <span className="text-pitch tnum text-xs font-semibold">{pct(team.champion)}</span>
      </div>
      <div className="hidden md:flex gap-3 shrink-0 w-28 justify-end">
        <span className="text-muted tnum text-xs">{pct(team.final)}</span>
        <span className="text-muted tnum text-xs">{pct(team.semi)}</span>
      </div>
    </motion.div>
  );
}

// ── Champion histogram ────────────────────────────────────────────────────────

function ChampionHistogram({ teams }: { teams: TeamProbability[] }) {
  const top = teams.slice(0, 12);
  const data = top.map((t) => ({
    name: t.team.length > 11 ? t.team.substring(0, 10) + "…" : t.team,
    champion: parseFloat((t.champion * 100).toFixed(2)),
    final: parseFloat((t.final * 100).toFixed(2)),
    semi: parseFloat((t.semi * 100).toFixed(2)),
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 32 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" vertical={false} />
        <XAxis
          dataKey="name" stroke="hsl(var(--muted))" fontSize={10}
          tick={{ fill: "hsl(var(--muted))" }} angle={-40} textAnchor="end" interval={0}
        />
        <YAxis tickFormatter={(v) => `${v}%`} stroke="hsl(var(--muted))" fontSize={10} />
        <Tooltip
          formatter={(v: number, name: string) => [
            `${v.toFixed(1)}%`,
            name === "champion" ? "Champion" : name === "final" ? "Final" : "Semi",
          ]}
          contentStyle={{
            background: "hsl(var(--elevated))", border: "1px solid hsl(var(--line))",
            borderRadius: 8, fontSize: 11,
          }}
          labelStyle={{ color: "hsl(var(--fg))", fontWeight: "bold" }}
        />
        <Bar dataKey="champion" fill="hsl(75 95% 55%)" name="champion" radius={[4, 4, 0, 0]} maxBarSize={28} />
        <Bar dataKey="final" fill="hsl(200 90% 62%)" name="final" radius={[4, 4, 0, 0]} maxBarSize={28} />
        <Bar dataKey="semi" fill="hsl(280 70% 68%)" name="semi" radius={[4, 4, 0, 0]} maxBarSize={28} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Bracket funnel ────────────────────────────────────────────────────────────

function BracketFunnel({ teams }: { teams: TeamProbability[] }) {
  const top = teams.slice(0, 8);
  const stages = [
    { label: "Champion", key: "champion" as const, colour: "hsl(75 95% 55%)" },
    { label: "Final", key: "final" as const, colour: "hsl(200 90% 62%)" },
    { label: "Semi", key: "semi" as const, colour: "hsl(280 70% 68%)" },
    { label: "Quarter", key: "quarter" as const, colour: "hsl(45 95% 58%)" },
  ];

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm min-w-[500px]">
        <thead>
          <tr className="kicker border-b border-line">
            <th className="py-2 text-left font-normal pl-2">Team</th>
            {stages.map((s) => (
              <th key={s.key} className="py-2 text-right font-normal pr-2" style={{ color: s.colour }}>
                {s.label}
              </th>
            ))}
            <th className="py-2 text-right font-normal pr-2 text-muted hidden lg:table-cell">E[pos]</th>
          </tr>
        </thead>
        <tbody>
          {top.map((t, i) => (
            <motion.tr
              key={t.team}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              className="border-b border-line/40 hover:bg-elevated/50 transition-colors"
            >
              <td className="py-2 pl-2 font-medium">{t.team}</td>
              {stages.map((s) => {
                const val = t[s.key] ?? 0;
                return (
                  <td key={s.key} className="py-2 text-right pr-2">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-16 h-1.5 bg-elevated rounded-full overflow-hidden hidden sm:block">
                        <div
                          className="h-full rounded-full"
                          style={{ width: `${Math.min(100, val * 100 * (s.key === "champion" ? 10 : s.key === "final" ? 5 : s.key === "semi" ? 2.5 : 1.5))}%`, background: s.colour }}
                        />
                      </div>
                      <span className="tnum text-xs" style={{ color: s.colour }}>
                        {pct(val)}
                      </span>
                    </div>
                  </td>
                );
              })}
              <td className="py-2 text-right pr-2 tnum text-muted text-xs hidden lg:table-cell">
                {ordinal(t.expected_finish)}
              </td>
            </motion.tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SimulatePage() {
  const [runs, setRuns] = useState(10000);
  const [view, setView] = useState<"ranking" | "histogram" | "bracket">("ranking");
  const sim = useWC2026Simulate();
  const result = sim.data;
  const maxChamp = result ? Math.max(...result.teams.map((t) => t.champion)) * 100 : 1;

  function reset() {
    sim.reset();
  }

  return (
    <div className="space-y-8">
      <header>
        <p className="kicker mb-2">Monte Carlo</p>
        <h1 className="display text-4xl">Tournament simulator</h1>
        <p className="text-muted mt-2 max-w-2xl">
          Run the full WC 2026 bracket thousands of times using provisional Elo-seeded groups
          and the hybrid prediction engine. Larger run counts reduce sampling noise.
        </p>
      </header>

      <DataFreshnessStrip />

      {/* Controls */}
      <Card>
        <CardBody className="flex flex-wrap items-end gap-4">
          <div>
            <span className="kicker block mb-1.5">Simulations</span>
            <div className="flex gap-1">
              {RUN_OPTIONS.map(([v, l]) => (
                <button
                  key={v}
                  onClick={() => setRuns(v)}
                  className={`tnum px-3 h-10 rounded-md border text-sm transition-colors ${
                    runs === v
                      ? "border-pitch text-pitch bg-pitch/10"
                      : "border-line text-muted hover:text-fg"
                  }`}
                >
                  {l}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <Button onClick={() => sim.mutate({ runs })} disabled={sim.isPending} size="lg">
              {sim.isPending ? "Simulating…" : "Run simulation"}
            </Button>
            {result && (
              <Button onClick={reset} variant="outline" size="lg" disabled={sim.isPending}>
                Reset
              </Button>
            )}
          </div>
          <p className="text-xs text-muted basis-full sm:basis-auto sm:ml-auto self-center max-w-xs">
            Uses provisional Elo-seeded groups. {runs.toLocaleString()} simulations × 48 teams × 104 matches.
          </p>
        </CardBody>
      </Card>

      {sim.isPending && (
        <div className="space-y-4">
          <Progress value={100} className="animate-pulse" />
          <div className="grid gap-4 lg:grid-cols-2">
            <Skeleton className="h-72" />
            <Skeleton className="h-72" />
          </div>
        </div>
      )}

      {sim.isError && (
        <p className="text-signal text-sm">{(sim.error as Error).message}</p>
      )}

      <AnimatePresence>
        {result && !sim.isPending && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
            {/* Metadata */}
            <div className="flex flex-wrap items-center gap-4 text-sm text-muted">
              <span>
                <span className="text-fg tnum font-semibold">{result.runs.toLocaleString()}</span> simulations
              </span>
              <span>
                <span className="text-fg tnum font-semibold">{result.teams.length}</span> teams
              </span>
              {result.seed !== undefined && result.seed !== null && (
                <span>
                  Seed <span className="text-fg tnum font-semibold">{result.seed}</span>
                </span>
              )}
              {!result.draw_complete && (
                <span className="text-[hsl(45_95%_58%)]">Using provisional Elo-seeded groups</span>
              )}
              <div className="flex gap-2 sm:ml-auto">
                <SaveSimulationButton
                  defaultName={`WC 2026 simulation (${result.runs.toLocaleString()} runs)`}
                  simulationType="wc2026"
                  edition="2026"
                  runs={result.runs}
                  seed={result.seed}
                  deterministic={result.deterministic}
                  tournamentResult={result}
                  championProbabilities={result.teams}
                />
                <Link href="/saved">
                  <Button variant="ghost" size="sm">View Saved Simulations</Button>
                </Link>
              </div>
            </div>

            {/* View selector */}
            <div className="flex gap-1 bg-elevated/60 border border-line p-1 rounded-lg w-fit">
              {(["ranking", "histogram", "bracket"] as const).map((v) => (
                <button
                  key={v}
                  onClick={() => setView(v)}
                  className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all capitalize ${
                    view === v ? "bg-pitch text-ink" : "text-muted hover:text-fg"
                  }`}
                >
                  {v === "ranking" ? "Rankings" : v === "histogram" ? "Histogram" : "Bracket"}
                </button>
              ))}
            </div>

            {view === "ranking" && (
              <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
                {/* Rankings list */}
                <Card>
                  <CardHeader className="flex justify-between items-baseline">
                    <span className="kicker">Championship probability</span>
                    <div className="hidden md:flex gap-4 text-[10px] text-muted">
                      <span className="text-pitch">Champ</span>
                      <span>Final</span>
                      <span>Semi</span>
                    </div>
                  </CardHeader>
                  <CardBody className="py-2">
                    {result.teams.map((t, i) => (
                      <TeamRow key={t.team} team={t} rank={i} max={maxChamp} />
                    ))}
                  </CardBody>
                </Card>

                {/* Summary stats */}
                <div className="space-y-5">
                  {/* Favourite */}
                  <Card>
                    <CardBody className="text-center py-6">
                      <p className="kicker mb-2">Tournament favourite</p>
                      <div className="display text-4xl mb-1">{result.teams[0].team}</div>
                      <div className="tnum text-2xl text-pitch">
                        {pct(result.teams[0].champion)}
                      </div>
                      <div className="text-muted text-xs mt-1">
                        championship probability
                      </div>
                      {result.teams[0].champion_ci_low !== undefined && (
                        <div className="text-muted text-xs mt-1">
                          95% CI: {pct(result.teams[0].champion_ci_low)} – {pct(result.teams[0].champion_ci_high)}
                        </div>
                      )}
                    </CardBody>
                  </Card>

                  {/* Top 5 quick list */}
                  <Card>
                    <CardHeader><span className="kicker">Top 5 favourites</span></CardHeader>
                    <CardBody className="py-3 space-y-2">
                      {result.teams.slice(0, 5).map((t, i) => (
                        <div key={t.team} className="flex items-center gap-3">
                          <span className="text-xs text-muted tnum w-4">{i + 1}</span>
                          <span className="text-sm flex-1">{t.team}</span>
                          <span className="text-pitch tnum text-sm font-semibold">{pct(t.champion)}</span>
                          <div className="w-16 h-1.5 bg-elevated rounded-full overflow-hidden">
                            <div
                              className="h-full bg-pitch rounded-full"
                              style={{ width: `${(t.champion / result.teams[0].champion) * 100}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </CardBody>
                  </Card>

                  {/* Most likely final */}
                  <Card>
                    <CardBody className="text-center py-4">
                      <p className="kicker mb-3">Most likely final</p>
                      <div className="flex items-center gap-4 justify-center">
                        <div>
                          <div className="text-lg font-bold text-fg">{result.teams[0].team}</div>
                          <div className="text-xs text-muted">{pct(result.teams[0].final)} to final</div>
                        </div>
                        <div className="text-muted text-lg display">vs</div>
                        <div>
                          <div className="text-lg font-bold text-fg">{result.teams[1].team}</div>
                          <div className="text-xs text-muted">{pct(result.teams[1].final)} to final</div>
                        </div>
                      </div>
                    </CardBody>
                  </Card>
                </div>
              </div>
            )}

            {view === "histogram" && (
              <Card>
                <CardHeader><span className="kicker">Championship / final / semi probabilities — top 12</span></CardHeader>
                <CardBody>
                  <ChampionHistogram teams={result.teams} />
                </CardBody>
              </Card>
            )}

            {view === "bracket" && (
              <Card>
                <CardHeader>
                  <span className="kicker">Bracket advancement probabilities — top 8</span>
                </CardHeader>
                <CardBody>
                  <BracketFunnel teams={result.teams} />
                </CardBody>
              </Card>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
