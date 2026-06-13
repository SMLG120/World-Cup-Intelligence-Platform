"use client";

import { useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, LabelList, Legend,
} from "recharts";
import { useWC2026Teams, useWC2026Groups, useWC2026Simulate } from "@/lib/queries";
import type {
  PredictionMode,
  TeamProbability,
  QualifiedTeam,
  WC2026GroupRow,
  WC2026KnockoutMatch,
  WC2026KnockoutRound,
  WC2026Simulation,
} from "@/lib/types";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { WinnerPredictionsSection } from "@/components/winner-predictions-section";
import { SaveSimulationButton } from "@/components/save-simulation-button";
import { DataFreshnessStrip } from "@/components/data-freshness";
import { pct, ordinal } from "@/lib/utils";

// ── Colour palette per confederation ────────────────────────────────────────
const CONF_COLOURS: Record<string, string> = {
  UEFA: "hsl(220 90% 62%)",
  CONMEBOL: "hsl(45 95% 58%)",
  CAF: "hsl(140 70% 50%)",
  AFC: "hsl(8 90% 64%)",
  CONCACAF: "hsl(280 70% 68%)",
  OFC: "hsl(200 90% 62%)",
};

const BAR_COLOURS = [
  "hsl(75 95% 55%)",
  "hsl(75 90% 50%)",
  "hsl(75 80% 44%)",
  "hsl(75 70% 38%)",
  "hsl(75 65% 34%)",
  "hsl(75 60% 30%)",
  "hsl(75 55% 26%)",
  "hsl(75 50% 22%)",
  "hsl(75 45% 18%)",
  "hsl(75 40% 15%)",
];

// ── Custom tooltip ────────────────────────────────────────────────────────────
function ChampTooltip({ active, payload }: { active?: boolean; payload?: { payload: TeamProbability }[] }) {
  if (!active || !payload?.[0]) return null;
  const t = payload[0].payload;
  return (
    <div className="bg-elevated border border-line rounded-lg px-4 py-3 text-xs space-y-1 shadow-xl">
      <div className="font-bold text-fg text-sm">{t.team}</div>
      <div className="flex justify-between gap-6">
        <span className="text-muted">Champion</span>
        <span className="text-pitch font-mono">{pct(t.champion)}</span>
      </div>
      <div className="flex justify-between gap-6">
        <span className="text-muted">Final</span>
        <span className="text-[hsl(200_90%_62%)] font-mono">{pct(t.final)}</span>
      </div>
      <div className="flex justify-between gap-6">
        <span className="text-muted">Semi</span>
        <span className="text-muted font-mono">{pct(t.semi)}</span>
      </div>
      {t.champion_ci_low !== undefined && (
        <div className="text-muted border-t border-line pt-1">
          95% CI: {pct(t.champion_ci_low)} – {pct(t.champion_ci_high)}
        </div>
      )}
    </div>
  );
}

// ── Champion probability bar chart ────────────────────────────────────────────
function ChampionChart({ teams, limit = 10 }: { teams: TeamProbability[]; limit?: number }) {
  const data = teams.slice(0, limit).map((t) => ({
    ...t,
    champion_pct: parseFloat((t.champion * 100).toFixed(2)),
    final_pct: parseFloat((t.final * 100).toFixed(2)),
  }));

  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 56, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" horizontal={false} />
        <XAxis
          type="number" dataKey="champion_pct" tickFormatter={(v) => `${v}%`}
          stroke="hsl(var(--muted))" fontSize={11}
        />
        <YAxis
          type="category" dataKey="team" width={90}
          stroke="hsl(var(--muted))" fontSize={11} tick={{ fill: "hsl(var(--fg))" }}
        />
        <Tooltip content={<ChampTooltip />} cursor={{ fill: "hsl(var(--elevated))" }} />
        <Bar dataKey="champion_pct" radius={[0, 4, 4, 0]} maxBarSize={26}>
          {data.map((_, i) => <Cell key={i} fill={BAR_COLOURS[i] ?? "hsl(var(--muted))"} />)}
          <LabelList
            dataKey="champion_pct"
            position="right"
            formatter={(v: number) => `${v.toFixed(1)}%`}
            style={{ fill: "hsl(var(--muted))", fontSize: 11, fontFamily: "var(--font-mono)" }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Round probabilities stacked bar ──────────────────────────────────────────
function RoundsChart({ teams, limit = 12 }: { teams: TeamProbability[]; limit?: number }) {
  const data = teams.slice(0, limit).map((t) => ({
    team: t.team,
    champion: parseFloat((t.champion * 100).toFixed(2)),
    final_only: parseFloat(((t.final - t.champion) * 100).toFixed(2)),
    semi_only: parseFloat(((t.semi - t.final) * 100).toFixed(2)),
    quarter: parseFloat(((t.quarter - t.semi) * 100).toFixed(2)),
  }));

  return (
    <ResponsiveContainer width="100%" height={340}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" horizontal={false} />
        <XAxis type="number" tickFormatter={(v) => `${v}%`} stroke="hsl(var(--muted))" fontSize={11} />
        <YAxis
          type="category" dataKey="team" width={90}
          stroke="hsl(var(--muted))" fontSize={11} tick={{ fill: "hsl(var(--fg))" }}
        />
        <Tooltip
          formatter={(v: number, name: string) => [
            `${v.toFixed(1)}%`,
            name === "champion" ? "Champion" : name === "final_only" ? "Final" : name === "semi_only" ? "Semi" : "Quarter",
          ]}
          contentStyle={{
            background: "hsl(var(--elevated))", border: "1px solid hsl(var(--line))",
            borderRadius: 8, fontSize: 12,
          }}
          labelStyle={{ color: "hsl(var(--fg))", fontWeight: "bold" }}
          cursor={{ fill: "hsl(var(--elevated))" }}
        />
        <Legend
          formatter={(v) => v === "champion" ? "Champion" : v === "final_only" ? "Final" : v === "semi_only" ? "Semi" : "Quarter"}
          wrapperStyle={{ fontSize: 11, color: "hsl(var(--muted))" }}
        />
        <Bar dataKey="champion" stackId="a" fill="hsl(75 95% 55%)" name="champion" />
        <Bar dataKey="final_only" stackId="a" fill="hsl(200 90% 62%)" name="final_only" />
        <Bar dataKey="semi_only" stackId="a" fill="hsl(280 70% 68%)" name="semi_only" />
        <Bar dataKey="quarter" stackId="a" fill="hsl(var(--line))" name="quarter" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Qualified teams grid ──────────────────────────────────────────────────────
function TeamPill({ team }: { team: QualifiedTeam }) {
  const colour = CONF_COLOURS[team.confederation] ?? "hsl(var(--muted))";
  return (
    <div
      className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-elevated transition-colors"
      style={{ borderLeft: `2px solid ${colour}` }}
    >
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-[10px] font-mono text-muted w-8 shrink-0">{team.team_code}</span>
        <span className="text-sm text-fg truncate">{team.team_name}</span>
        {team.host_nation && (
          <span className="text-[9px] bg-[hsl(45_95%_58%/0.2)] text-[hsl(45_95%_58%)] border border-[hsl(45_95%_58%/0.3)] px-1 py-0.5 rounded shrink-0">
            HOST
          </span>
        )}
      </div>
      <div className="flex items-center gap-3 shrink-0 ml-2">
        {team.elo_rating != null && (
          <span className="text-[10px] font-mono text-pitch" title="Elo rating">
            {Math.round(team.elo_rating)}
          </span>
        )}
        {team.fifa_rank != null && (
          <span className="text-[10px] text-muted" title={`FIFA rank #${team.fifa_rank}`}>
            #{team.fifa_rank}
          </span>
        )}
        <span className="text-[10px] text-muted">{team.confederation}</span>
      </div>
    </div>
  );
}

// ── Most likely final ─────────────────────────────────────────────────────────
function LikelyFinal({ teams }: { teams: TeamProbability[] }) {
  const top2 = teams.slice(0, 2);
  if (top2.length < 2) return null;
  const [a, b] = top2;
  return (
    <div className="flex flex-col items-center gap-3 py-6">
      <p className="kicker text-center">Most likely final</p>
      <div className="flex items-center gap-6 text-center">
        <div>
          <div className="display text-3xl text-fg">{a.team}</div>
          <div className="text-pitch tnum text-sm mt-0.5">{pct(a.champion)} champion</div>
        </div>
        <div className="text-muted text-xl display">vs</div>
        <div>
          <div className="display text-3xl text-fg">{b.team}</div>
          <div className="text-pitch tnum text-sm mt-0.5">{pct(b.champion)} champion</div>
        </div>
      </div>
    </div>
  );
}

// ── Group simulation card ─────────────────────────────────────────────────────
function GroupSimCard({
  label,
  teamNames,
  sim,
}: {
  label: string;
  teamNames: string[];
  sim: WC2026Simulation;
}) {
  const probMap = new Map(sim.teams.map((t) => [t.team, t]));
  const sorted = [...teamNames].sort((a, b) => {
    const pa = probMap.get(a)?.round_of_16 ?? 0;
    const pb = probMap.get(b)?.round_of_16 ?? 0;
    return pb - pa;
  });

  return (
    <Card>
      <CardHeader className="py-3 flex items-center justify-between">
        <span className="kicker">Group {label}</span>
        <span className="text-[10px] text-muted">R16 %</span>
      </CardHeader>
      <CardBody className="py-2 space-y-1.5">
        {sorted.map((name, i) => {
          const p = probMap.get(name);
          const pct_val = p ? Math.round(p.round_of_16 * 100) : null;
          const barW = p ? p.round_of_16 * 100 : 0;
          return (
            <div key={name} className="space-y-0.5">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className={`text-[10px] font-mono w-4 shrink-0 ${i < 2 ? "text-pitch" : "text-muted"}`}>
                    {i + 1}
                  </span>
                  <span className={`truncate ${i < 2 ? "text-fg" : "text-muted"}`}>{name}</span>
                </div>
                <span className={`tnum shrink-0 ml-2 text-[10px] ${i < 2 ? "text-pitch" : "text-muted"}`}>
                  {pct_val != null ? `${pct_val}%` : "—"}
                </span>
              </div>
              <div className="h-0.5 w-full bg-elevated rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${i < 2 ? "bg-pitch" : "bg-muted/40"}`}
                  style={{ width: `${barW}%` }}
                />
              </div>
            </div>
          );
        })}
      </CardBody>
    </Card>
  );
}

function QualificationBadge({ type }: { type: WC2026GroupRow["qualification_type"] }) {
  if (type === "automatic") {
    return <span className="text-[9px] text-pitch border border-pitch/30 rounded px-1">Q</span>;
  }
  if (type === "best_third") {
    return <span className="text-[9px] text-[hsl(45_95%_58%)] border border-[hsl(45_95%_58%/0.35)] rounded px-1">3rd</span>;
  }
  return <span className="text-[9px] text-muted border border-line rounded px-1">out</span>;
}

function GroupTableCard({ label, rows }: { label: string; rows: WC2026GroupRow[] }) {
  return (
    <Card>
      <CardHeader className="py-3 flex items-center justify-between">
        <span className="kicker">Group {label}</span>
        <span className="text-[10px] text-muted">simulated table</span>
      </CardHeader>
      <CardBody className="p-0 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-[10px] text-muted border-b border-line/50">
              <th className="py-2 pl-3 text-left font-normal">Team</th>
              <th className="py-2 text-right font-normal">P</th>
              <th className="py-2 text-right font-normal">GD</th>
              <th className="py-2 text-right font-normal">Pts</th>
              <th className="py-2 pr-3 text-right font-normal">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.team} className="border-b border-line/40 last:border-0">
                <td className="py-2 pl-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="tnum text-[10px] text-muted w-3">{row.rank}</span>
                    <span className={row.qualified ? "text-fg font-medium truncate" : "text-muted truncate"}>
                      {row.team}
                    </span>
                  </div>
                </td>
                <td className="py-2 text-right tnum text-muted">{row.played}</td>
                <td className="py-2 text-right tnum text-muted">{row.goal_difference > 0 ? "+" : ""}{row.goal_difference}</td>
                <td className="py-2 text-right tnum text-fg font-semibold">{row.points}</td>
                <td className="py-2 pr-3 text-right"><QualificationBadge type={row.qualification_type} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}

// ── Group tables grid ─────────────────────────────────────────────────────────
function GroupTablesGrid({
  groups,
  sim,
}: {
  groups: Record<string, string[]>;
  sim: WC2026Simulation;
}) {
  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {Object.entries(groups)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([label, teamNames]) => {
          const rows = sim.group_tables?.[label];
          return rows
            ? <GroupTableCard key={label} label={label} rows={rows} />
            : <GroupSimCard key={label} label={label} teamNames={teamNames} sim={sim} />;
        })}
    </div>
  );
}

function BestThirdTable({ rows }: { rows?: WC2026GroupRow[] }) {
  if (!rows?.length) return null;
  return (
    <Card>
      <CardHeader className="py-3">
        <span className="kicker">Best third-place teams</span>
      </CardHeader>
      <CardBody className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] text-muted border-b border-line">
              <th className="px-4 py-2 text-left font-normal">#</th>
              <th className="px-4 py-2 text-left font-normal">Team</th>
              <th className="px-4 py-2 text-right font-normal">Group</th>
              <th className="px-4 py-2 text-right font-normal">Pts</th>
              <th className="px-4 py-2 text-right font-normal">GD</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.group}-${row.team}`} className="border-b border-line/50 last:border-0">
                <td className="px-4 py-2 tnum text-muted">{row.rank}</td>
                <td className="px-4 py-2 text-fg font-medium">{row.team}</td>
                <td className="px-4 py-2 text-right tnum text-muted">{row.group}</td>
                <td className="px-4 py-2 text-right tnum text-fg">{row.points}</td>
                <td className="px-4 py-2 text-right tnum text-muted">{row.goal_difference > 0 ? "+" : ""}{row.goal_difference}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}

function BracketMatchCard({ match }: { match: WC2026KnockoutMatch }) {
  const winnerProb = match.winner_probability != null ? pct(match.winner_probability) : "n/a";
  const championProb = match.champion_probability != null ? pct(match.champion_probability) : null;
  const modeLabel = (match.effective_prediction_mode ?? match.prediction_mode ?? "ensemble").replace("_", " ");
  const row = (team: string, code: string | undefined, goals: number) => (
    <div className="flex items-center justify-between gap-2">
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-[10px] font-mono text-muted w-8 shrink-0">{code ?? team.slice(0, 3).toUpperCase()}</span>
        <span className={match.winner === team ? "font-semibold text-fg truncate" : "text-muted truncate"}>
          {team}
        </span>
      </div>
      <span className={`tnum shrink-0 ${match.winner === team ? "text-pitch font-semibold" : "text-fg"}`}>
        {goals}
      </span>
    </div>
  );

  return (
    <div className="rounded-md border border-line bg-elevated/50 p-3 text-xs space-y-2">
      {row(match.home, match.home_code, match.home_goals)}
      {row(match.away, match.away_code, match.away_goals)}
      <div className="grid grid-cols-2 gap-2 border-t border-line/50 pt-2 text-[10px] text-muted">
        <span>{match.match_id}</span>
        <span className="text-right capitalize">{match.decided_by.replace("_", " ")}</span>
        <span>Winner prob</span>
        <span className="text-right text-pitch tnum">{winnerProb}</span>
        <span>Model</span>
        <span className="text-right uppercase">{modeLabel}</span>
        {championProb && (
          <>
            <span>Champion odds</span>
            <span className="text-right tnum">{championProb}</span>
          </>
        )}
      </div>
      {match.advancement_reason && (
        <p className="text-[10px] leading-snug text-muted">{match.advancement_reason}</p>
      )}
    </div>
  );
}

function KnockoutBracket({ rounds }: { rounds?: WC2026KnockoutRound[] }) {
  const visibleRounds = (rounds ?? []).filter((round) => round.matches.length > 0);
  if (!visibleRounds.length) return null;
  return (
    <div className="overflow-x-auto pb-2">
      <div className="grid gap-4 min-w-[1260px]" style={{ gridTemplateColumns: `repeat(${visibleRounds.length}, minmax(190px, 1fr))` }}>
        {visibleRounds.map((round) => (
          <div key={round.round} className="space-y-2">
            <div className="kicker text-center">{round.round}</div>
            {round.matches
              .slice()
              .sort((a, b) => a.order - b.order)
              .map((match) => <BracketMatchCard key={match.match_id} match={match} />)}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Run count selector ────────────────────────────────────────────────────────
const RUN_OPTIONS: [number, string][] = [
  [1, "Single"],
  [1000, "1K"], [5000, "5K"], [10000, "10K"], [50000, "50K"],
];

const MODE_OPTIONS: { value: PredictionMode; label: string }[] = [
  { value: "ensemble", label: "Ensemble" },
  { value: "statistical", label: "Stat" },
  { value: "ml", label: "ML" },
];

function PredictionModeControl({
  value,
  onChange,
}: {
  value: PredictionMode;
  onChange: (mode: PredictionMode) => void;
}) {
  return (
    <div className="flex gap-1" aria-label="Prediction mode">
      {MODE_OPTIONS.map((mode) => (
        <button
          key={mode.value}
          onClick={() => onChange(mode.value)}
          className={`px-3 h-9 rounded-md border text-xs uppercase tracking-[0.12em] transition-colors ${
            value === mode.value
              ? "border-pitch text-pitch bg-pitch/10"
              : "border-line text-muted hover:text-fg"
          }`}
          title={`Use ${mode.label} predictions for displayed match probabilities`}
        >
          {mode.label}
        </button>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function WorldCupPage() {
  const [tab, setTab] = useState("overview");
  const [simRuns, setSimRuns] = useState(10000);
  const [predictionMode, setPredictionMode] = useState<PredictionMode>("ensemble");
  const [teamSort, setTeamSort] = useState<"elo" | "name" | "fifa">("elo");
  const [confFilter, setConfFilter] = useState("all");

  const { data: teams, isLoading: teamsLoading } = useWC2026Teams();
  const { data: groups, isLoading: groupsLoading } = useWC2026Groups();
  const sim = useWC2026Simulate();

  const confederation = Array.from(new Set((teams ?? []).map((t) => t.confederation))).sort();
  const filtered = confFilter === "all" ? (teams ?? []) : (teams ?? []).filter((t) => t.confederation === confFilter);
  const simResult = sim.data;

  function runSim() {
    sim.mutate({ runs: simRuns, predictionMode });
  }

  return (
    <div className="space-y-8">
      {/* ── Header ── */}
      <motion.header
        initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
        className="flex flex-wrap items-end justify-between gap-4"
      >
        <div>
          <p className="kicker mb-2">FIFA World Cup</p>
          <h1 className="display text-4xl text-fg">2026 Dashboard</h1>
          <p className="text-muted mt-2 max-w-2xl">
            June 11 – July 19 · USA, Canada & Mexico · 48 teams · 104 matches.
            {groups && (
              <span>
                {" "}<span className="text-fg tnum">{groups.qualification_status.confirmed}</span>
                /{groups.qualification_status.total_slots} teams confirmed.{" "}
                {groups.draw_complete
                  ? <span className="text-pitch">Draw complete.</span>
                  : <span className="text-[hsl(45_95%_58%)]">Draw pending.</span>
                }
              </span>
            )}
          </p>
        </div>

        {/* Sim controls */}
        <div className="flex items-center gap-2 flex-wrap">
          <PredictionModeControl value={predictionMode} onChange={setPredictionMode} />
          <div className="flex gap-1">
            {RUN_OPTIONS.map(([v, l]) => (
              <button
                key={v}
                onClick={() => setSimRuns(v)}
                className={`tnum px-3 h-9 rounded-md border text-sm transition-colors ${
                  simRuns === v
                    ? "border-pitch text-pitch bg-pitch/10"
                    : "border-line text-muted hover:text-fg"
                }`}
              >
                {l}
              </button>
            ))}
          </div>
          <Button onClick={runSim} disabled={sim.isPending} size="md">
            {sim.isPending ? "Simulating…" : "Run simulation"}
          </Button>
          <Link href="/wc2026/bracket">
            <Button variant="outline" size="md">Full bracket</Button>
          </Link>
        </div>
      </motion.header>

      <DataFreshnessStrip />

      <WinnerPredictionsSection />

      {/* ── Tabs ── */}
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="teams">Teams ({(teams ?? []).length})</TabsTrigger>
          <TabsTrigger value="groups">Groups</TabsTrigger>
          <TabsTrigger value="bracket">Bracket</TabsTrigger>
        </TabsList>

        {/* ── Overview tab ── */}
        <TabsContent value="overview" className="mt-6 space-y-6">
          {sim.isError && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-signal/30 bg-signal/10 px-4 py-3 text-sm">
              <p className="text-signal">{(sim.error as Error).message}</p>
              <Button variant="outline" size="sm" onClick={runSim}>Retry</Button>
            </div>
          )}

          {!simResult && !sim.isPending && (
            <Card>
              <CardBody className="py-16 text-center">
                <div className="text-4xl mb-3">🏆</div>
                <h2 className="display text-2xl mb-2">Run a simulation to see championship odds</h2>
                <p className="text-muted max-w-md mx-auto">
                  Monte Carlo tournament simulation runs all 104 matches thousands of times using
                  the hybrid Elo + ML prediction engine to compute championship probabilities.
                </p>
              </CardBody>
            </Card>
          )}

          {sim.isPending && (
            <div className="grid gap-5 lg:grid-cols-2">
              <Skeleton className="h-80" />
              <Skeleton className="h-80" />
            </div>
          )}

          <AnimatePresence>
            {simResult && !sim.isPending && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-6"
              >
                <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
                  <span>
                    <span className="tnum text-fg font-semibold">{simResult.runs.toLocaleString()}</span> run{simResult.runs === 1 ? "" : "s"}
                  </span>
                  <span>
                    Mode <span className="text-fg font-semibold uppercase">{simResult.prediction_mode ?? predictionMode}</span>
                  </span>
                  {simResult.seed !== undefined && simResult.seed !== null && (
                    <span>
                      Seed <span className="tnum text-fg font-semibold">{simResult.seed}</span>
                    </span>
                  )}
                  {simResult.champion && (
                    <span>
                      Champion <span className="text-pitch font-semibold">{simResult.champion}</span>
                    </span>
                  )}
                  <div className="flex gap-2 sm:ml-auto">
                    <SaveSimulationButton
                      defaultName={`WC 2026 simulation (${simResult.runs.toLocaleString()} runs)`}
                      simulationType="wc2026"
                      edition="2026"
                      runs={simResult.runs}
                      seed={simResult.seed}
                      deterministic={simResult.deterministic}
                      tournamentResult={simResult}
                      championProbabilities={simResult.teams}
                      bracketOutput={{
                        group_tables: simResult.group_tables,
                        group_stage_matches: simResult.group_stage_matches,
                        qualified_teams: simResult.qualified_teams,
                        best_third_place: simResult.best_third_place,
                        knockout_bracket: simResult.knockout_bracket,
                        matches: simResult.matches,
                        prediction_mode: simResult.prediction_mode,
                      }}
                    />
                    <Link href="/saved">
                      <Button variant="ghost" size="sm">Saved</Button>
                    </Link>
                  </div>
                </div>

                {/* Most likely final */}
                <Card>
                  <CardBody className="py-2">
                    <LikelyFinal teams={simResult.teams} />
                  </CardBody>
                </Card>

                <div className="grid gap-5 lg:grid-cols-2">
                  {/* Champion probability chart */}
                  <Card>
                    <CardHeader className="flex justify-between items-baseline">
                      <span className="kicker">Champion probability</span>
                      <span className="tnum text-xs text-muted">{simResult.runs.toLocaleString()} simulations</span>
                    </CardHeader>
                    <CardBody>
                      <ChampionChart teams={simResult.teams} limit={10} />
                    </CardBody>
                  </Card>

                  {/* Round advancement stacked */}
                  <Card>
                    <CardHeader>
                      <span className="kicker">Round advancement odds</span>
                    </CardHeader>
                    <CardBody>
                      <RoundsChart teams={simResult.teams} limit={10} />
                    </CardBody>
                  </Card>
                </div>

                {/* Full probability table */}
                <Card>
                  <CardHeader>
                    <span className="kicker">All teams — projected finish</span>
                  </CardHeader>
                  <CardBody className="overflow-x-auto p-0">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="kicker text-left border-b border-line">
                          <th className="px-5 py-3 font-normal w-8">#</th>
                          <th className="px-5 py-3 font-normal">Team</th>
                          <th className="px-5 py-3 font-normal text-right text-pitch">Champion</th>
                          <th className="px-5 py-3 font-normal text-right hidden sm:table-cell">Final</th>
                          <th className="px-5 py-3 font-normal text-right hidden md:table-cell">Semi</th>
                          <th className="px-5 py-3 font-normal text-right hidden lg:table-cell">QF</th>
                          <th className="px-5 py-3 font-normal text-right hidden lg:table-cell">E[pos]</th>
                        </tr>
                      </thead>
                      <tbody>
                        {simResult.teams.map((t, i) => (
                          <motion.tr
                            key={t.team}
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: i * 0.015 }}
                            className="border-b border-line/50 hover:bg-elevated/60 transition-colors"
                          >
                            <td className="px-5 py-2 tnum text-muted text-xs">{i + 1}</td>
                            <td className="px-5 py-2 font-medium">{t.team}</td>
                            <td className="px-5 py-2 text-right tnum text-pitch font-semibold">{pct(t.champion)}</td>
                            <td className="px-5 py-2 text-right tnum text-muted hidden sm:table-cell">{pct(t.final)}</td>
                            <td className="px-5 py-2 text-right tnum text-muted hidden md:table-cell">{pct(t.semi)}</td>
                            <td className="px-5 py-2 text-right tnum text-muted hidden lg:table-cell">{pct(t.quarter ?? 0)}</td>
                            <td className="px-5 py-2 text-right tnum text-muted hidden lg:table-cell">{ordinal(t.expected_finish)}</td>
                          </motion.tr>
                        ))}
                      </tbody>
                    </table>
                  </CardBody>
                </Card>

                {/* Group stage qualification probabilities */}
                {simResult.groups && (
                  <div>
                    <h2 className="kicker mb-4">Group stage</h2>
                    <GroupTablesGrid groups={simResult.groups} sim={simResult} />
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </TabsContent>

        {/* ── Teams tab ── */}
        <TabsContent value="teams" className="mt-6 space-y-4">
          <div className="flex flex-wrap items-center gap-2 justify-between">
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => setConfFilter("all")}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                  confFilter === "all" ? "border-pitch text-pitch bg-pitch/10" : "border-line text-muted hover:text-fg"
                }`}
              >
                All ({(teams ?? []).length})
              </button>
              {confederation.map((c) => (
                <button
                  key={c}
                  onClick={() => setConfFilter(c)}
                  style={confFilter === c ? { borderColor: CONF_COLOURS[c], color: CONF_COLOURS[c] } : {}}
                  className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                    confFilter === c ? "bg-elevated" : "border-line text-muted hover:text-fg"
                  }`}
                >
                  {c} ({(teams ?? []).filter((t) => t.confederation === c).length})
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1 text-xs text-muted">
              <span>Sort:</span>
              {(["elo", "fifa", "name"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setTeamSort(s)}
                  className={`px-2 py-0.5 rounded border text-[10px] transition-colors ${
                    teamSort === s ? "border-pitch text-pitch" : "border-line hover:text-fg"
                  }`}
                >
                  {s === "elo" ? "Elo ↓" : s === "fifa" ? "FIFA ↑" : "Name"}
                </button>
              ))}
            </div>
          </div>

          {teamsLoading ? (
            <div className="grid sm:grid-cols-2 gap-1">
              {Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} className="h-9" />)}
            </div>
          ) : (
            <Card>
              <CardBody className="p-0">
                <div className="flex items-center justify-between px-3 py-1.5 border-b border-line/50 text-[10px] text-muted">
                  <span className="w-8">Code</span>
                  <span className="flex-1 ml-2">Team</span>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-pitch font-medium">Elo</span>
                    <span>FIFA</span>
                    <span>Conf</span>
                  </div>
                </div>
                <div className="grid sm:grid-cols-2">
                  {[...(filtered ?? [])]
                    .sort((a, b) =>
                      teamSort === "elo"
                        ? (b.elo_rating ?? 0) - (a.elo_rating ?? 0)
                        : teamSort === "fifa"
                        ? (a.fifa_rank ?? 999) - (b.fifa_rank ?? 999)
                        : a.team_name.localeCompare(b.team_name)
                    )
                    .map((t) => <TeamPill key={t.team_name} team={t} />)}
                </div>
              </CardBody>
            </Card>
          )}
        </TabsContent>

        {/* ── Groups tab ── */}
        <TabsContent value="groups" className="mt-6 space-y-6">
          {groupsLoading ? (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} className="h-44" />)}
            </div>
          ) : simResult?.groups ? (
            <>
              {!groups?.draw_complete && (
                <div className="flex items-start gap-3 px-4 py-3 rounded-lg border border-[hsl(45_95%_58%/0.3)] bg-[hsl(45_95%_58%/0.06)] text-sm text-[hsl(45_95%_58%)]">
                  <span className="shrink-0 mt-0.5">⚠</span>
                  <span>
                    Official draw pending — showing <strong>provisional Elo-seeded groups</strong> used in the simulation.
                    Probabilities reflect these provisional assignments.
                  </span>
                </div>
              )}
              <GroupTablesGrid groups={simResult.groups} sim={simResult} />
              <BestThirdTable rows={simResult.best_third_place} />
              <p className="text-[10px] text-muted text-center">
                Based on {simResult.runs.toLocaleString()} simulations · Top 2 per group advance ·
                {groups?.draw_complete ? " Official draw" : " Provisional Elo seeding"}
              </p>
            </>
          ) : groups?.draw_complete ? (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {Object.entries(groups.groups).map(([label, groupTeams]) => (
                <Card key={label}>
                  <CardHeader className="py-3">
                    <span className="kicker">Group {label}</span>
                  </CardHeader>
                  <CardBody className="py-3 space-y-1">
                    {(groupTeams as string[]).map((name) => (
                      <div key={name} className="text-sm text-fg py-0.5 border-b border-line/40 last:border-0">
                        {name}
                      </div>
                    ))}
                  </CardBody>
                </Card>
              ))}
            </div>
          ) : (
            <div className="py-20 text-center">
              <div className="text-5xl mb-4">🎲</div>
              <h2 className="display text-2xl mb-2">Group draw pending</h2>
              <p className="text-muted max-w-md mx-auto">
                The official FIFA group draw hasn&apos;t taken place yet. Run a simulation to see
                provisional Elo-seeded group qualification probabilities.
              </p>
            </div>
          )}
        </TabsContent>

        {/* ── Bracket tab ── */}
        <TabsContent value="bracket" className="mt-6 space-y-6">
          {simResult?.knockout_bracket ? (
            <>
              <div className="grid gap-4 md:grid-cols-3">
                <Card>
                  <CardBody className="py-5">
                    <p className="kicker mb-1">Champion</p>
                    <div className="display text-3xl">{simResult.champion ?? "TBD"}</div>
                  </CardBody>
                </Card>
                <Card>
                  <CardBody className="py-5">
                    <p className="kicker mb-1">Runner-up</p>
                    <div className="display text-3xl">{simResult.runner_up ?? "TBD"}</div>
                  </CardBody>
                </Card>
                <Card>
                  <CardBody className="py-5">
                    <p className="kicker mb-1">Third place</p>
                    <div className="display text-3xl">{simResult.third_place ?? "TBD"}</div>
                  </CardBody>
                </Card>
              </div>
              <KnockoutBracket rounds={simResult.knockout_bracket} />
            </>
          ) : (
            <Card>
              <CardBody className="py-16 text-center">
                <h2 className="display text-2xl mb-2">No bracket yet</h2>
                <p className="text-muted">Run a simulation to generate a full knockout path.</p>
              </CardBody>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
