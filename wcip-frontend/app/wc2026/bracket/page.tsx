"use client";

import { useState } from "react";
import Link from "next/link";
import { RefreshCw, Shuffle, Trophy } from "lucide-react";
import { useWC2026Simulate } from "@/lib/queries";
import type { PredictionMode, WC2026GroupRow, WC2026Match } from "@/lib/types";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { DataFreshnessStrip } from "@/components/data-freshness";
import { SaveSimulationButton } from "@/components/save-simulation-button";
import { TournamentBracket } from "@/components/bracket-tree";
import { SquadPanel } from "@/components/squad-panel";
import { pct, cn } from "@/lib/utils";

// ── Group stage helper components ─────────────────────────────────────────────

function QualTag({ row }: { row: WC2026GroupRow }) {
  if (row.qualified && row.qualification_type === "automatic")
    return (
      <span className="inline-block text-[9px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-pitch/15 text-pitch">
        Q
      </span>
    );
  if (row.qualified && row.qualification_type === "best_third")
    return (
      <span className="inline-block text-[9px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-500">
        3rd
      </span>
    );
  return (
    <span className="inline-block text-[9px] text-muted px-1.5 py-0.5 rounded bg-elevated">
      out
    </span>
  );
}

function GroupFixture({ match }: { match: WC2026Match }) {
  return (
    <div className="flex items-center gap-1 text-[10px] py-[3px]">
      <span
        className={cn(
          "flex-1 truncate text-right",
          match.winner === match.home ? "text-fg font-semibold" : "text-muted",
        )}
      >
        {match.home}
      </span>
      <span className="tnum font-mono shrink-0 px-2 tabular-nums min-w-[3rem] text-center text-fg/80">
        {match.home_goals}–{match.away_goals}
      </span>
      <span
        className={cn(
          "flex-1 truncate",
          match.winner === match.away ? "text-fg font-semibold" : "text-muted",
        )}
      >
        {match.away}
      </span>
    </div>
  );
}

function GroupCard({
  label,
  rows,
  matches,
}: {
  label: string;
  rows: WC2026GroupRow[];
  matches: WC2026Match[];
}) {
  return (
    <Card>
      <CardHeader className="py-2.5 flex items-center justify-between">
        <span className="kicker text-[11px]">Group {label}</span>
        <span className="text-[9px] text-muted uppercase tracking-wide">simulated</span>
      </CardHeader>
      <CardBody className="p-0 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-line/50">
              <th className="py-1.5 pl-3 pr-1 text-left text-[9px] text-muted font-medium w-5">#</th>
              <th className="py-1.5 px-1 text-left text-[9px] text-muted font-medium">Team</th>
              <th className="py-1.5 px-1 text-center text-[9px] text-muted font-medium tnum w-7">P</th>
              <th className="py-1.5 px-1 text-center text-[9px] text-muted font-medium tnum w-7">W</th>
              <th className="py-1.5 px-1 text-center text-[9px] text-muted font-medium tnum w-7">D</th>
              <th className="py-1.5 px-1 text-center text-[9px] text-muted font-medium tnum w-7">L</th>
              <th className="py-1.5 px-1 text-center text-[9px] text-muted font-medium tnum w-9">GD</th>
              <th className="py-1.5 px-1 text-center text-[9px] text-muted font-medium tnum w-8">Pts</th>
              <th className="py-1.5 pl-1 pr-3 w-9" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.team}
                className={cn(
                  "border-b border-line/30 last:border-0",
                  row.qualified && row.qualification_type === "automatic"
                    ? "bg-pitch/5"
                    : row.qualified && row.qualification_type === "best_third"
                      ? "bg-amber-500/5"
                      : "",
                )}
              >
                <td className="py-1.5 pl-3 pr-1 tnum text-muted text-center">{row.rank}</td>
                <td className="py-1.5 px-1 font-medium text-fg truncate max-w-[88px]">{row.team}</td>
                <td className="py-1.5 px-1 tnum text-center text-muted">{row.played}</td>
                <td className="py-1.5 px-1 tnum text-center text-muted">{row.won}</td>
                <td className="py-1.5 px-1 tnum text-center text-muted">{row.drawn}</td>
                <td className="py-1.5 px-1 tnum text-center text-muted">{row.lost}</td>
                <td
                  className={cn(
                    "py-1.5 px-1 tnum text-center",
                    row.goal_difference > 0
                      ? "text-pitch"
                      : row.goal_difference < 0
                        ? "text-signal"
                        : "text-muted",
                  )}
                >
                  {row.goal_difference > 0 ? `+${row.goal_difference}` : row.goal_difference}
                </td>
                <td className="py-1.5 px-1 tnum text-center font-semibold text-fg">{row.points}</td>
                <td className="py-1.5 pl-1 pr-3 text-right">
                  <QualTag row={row} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {matches.length > 0 && (
          <div className="px-3 py-2 border-t border-line/30">
            {matches.map((m) => (
              <GroupFixture key={m.match_id} match={m} />
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function BestThirdTable({ rows }: { rows: WC2026GroupRow[] }) {
  if (!rows.length) return null;
  const qualified = rows.slice(0, 8);
  const rest = rows.slice(8);
  return (
    <Card>
      <CardHeader className="py-2.5 flex items-center justify-between">
        <span className="kicker text-[11px]">Best third-place qualifiers</span>
        <span className="text-[9px] text-muted">top 8 of 12 advance</span>
      </CardHeader>
      <CardBody className="p-0 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-line/50">
              <th className="py-1.5 pl-3 pr-1 text-left text-[9px] text-muted font-medium w-5">#</th>
              <th className="py-1.5 px-1 text-left text-[9px] text-muted font-medium">Team</th>
              <th className="py-1.5 px-1 text-center text-[9px] text-muted font-medium w-10">Grp</th>
              <th className="py-1.5 px-1 text-center text-[9px] text-muted font-medium tnum w-9">GD</th>
              <th className="py-1.5 pr-3 text-center text-[9px] text-muted font-medium tnum w-8">Pts</th>
            </tr>
          </thead>
          <tbody>
            {[...qualified, ...rest].map((row, i) => (
              <tr
                key={row.team}
                className={cn(
                  "border-b border-line/30 last:border-0",
                  i < 8 ? "bg-amber-500/5" : "",
                  i === 7 ? "border-b-2 border-amber-500/30" : "",
                )}
              >
                <td className="py-1.5 pl-3 pr-1 tnum text-muted text-center">{i + 1}</td>
                <td className="py-1.5 px-1 font-medium text-fg">{row.team}</td>
                <td className="py-1.5 px-1 text-center text-muted">{row.group}</td>
                <td
                  className={cn(
                    "py-1.5 px-1 tnum text-center",
                    row.goal_difference > 0
                      ? "text-pitch"
                      : row.goal_difference < 0
                        ? "text-signal"
                        : "text-muted",
                  )}
                >
                  {row.goal_difference > 0 ? `+${row.goal_difference}` : row.goal_difference}
                </td>
                <td className="py-1.5 pr-3 tnum text-center font-semibold text-fg">{row.points}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}

// ── Mode / run controls ───────────────────────────────────────────────────────

const RUN_OPTIONS: [number, string][] = [
  [1, "Single"],
  [1000, "1K"],
  [5000, "5K"],
  [10000, "10K"],
  [50000, "50K"],
];

const MODES: { value: PredictionMode; label: string }[] = [
  { value: "ensemble", label: "Ensemble" },
  { value: "statistical", label: "Statistical" },
  { value: "ml", label: "ML" },
];

function ModeButtons({
  value,
  onChange,
}: {
  value: PredictionMode;
  onChange: (mode: PredictionMode) => void;
}) {
  return (
    <div className="flex gap-1 flex-wrap">
      {MODES.map((mode) => (
        <button
          key={mode.value}
          onClick={() => onChange(mode.value)}
          className={`h-9 px-3 rounded-md border text-xs uppercase tracking-[0.12em] transition-colors ${
            value === mode.value
              ? "border-pitch bg-pitch/10 text-pitch"
              : "border-line text-muted hover:text-fg"
          }`}
        >
          {mode.label}
        </button>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function WC2026BracketPage() {
  const [runs, setRuns] = useState(10000);
  const [predictionMode, setPredictionMode] = useState<PredictionMode>("ensemble");
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const sim = useWC2026Simulate();

  const runSimulation = (nextRuns = runs) => {
    sim.mutate({ runs: nextRuns, predictionMode, seed: null, deterministic: false });
  };

  const runSingleRandom = () => {
    setRuns(1);
    runSimulation(1);
  };

  const groupEntries = Object.entries(sim.data?.group_tables ?? {}).sort(([a], [b]) =>
    a.localeCompare(b),
  );

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker mb-2">World Cup 2026</p>
          <h1 className="display text-4xl text-fg">Bracket Simulator</h1>
          <p className="text-muted mt-2 max-w-2xl">
            Project the 48-team group stage, the eight best third-place qualifiers,
            and every knockout matchup through the final. Click any team name to view
            their squad.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <ModeButtons value={predictionMode} onChange={setPredictionMode} />
          <div className="flex gap-1">
            {RUN_OPTIONS.map(([value, label]) => (
              <button
                key={value}
                onClick={() => setRuns(value)}
                className={`tnum h-9 px-3 rounded-md border text-sm transition-colors ${
                  runs === value
                    ? "border-pitch bg-pitch/10 text-pitch"
                    : "border-line text-muted hover:text-fg"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <Button onClick={() => runSimulation()} disabled={sim.isPending}>
            <RefreshCw className={`h-4 w-4 ${sim.isPending ? "animate-spin" : ""}`} />
            {sim.data ? "Rerun" : "Run"}
          </Button>
          <Button variant="outline" onClick={runSingleRandom} disabled={sim.isPending}>
            <Shuffle className="h-4 w-4" />
            Random run
          </Button>
        </div>
      </header>

      <DataFreshnessStrip />

      {sim.isError && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-signal/30 bg-signal/10 px-4 py-3 text-sm">
          <p className="text-signal">{(sim.error as Error).message}</p>
          <Button variant="outline" size="sm" onClick={() => runSimulation()}>
            Retry
          </Button>
        </div>
      )}

      {sim.isPending && (
        <div className="space-y-5">
          <div className="grid gap-4 md:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 12 }).map((_, i) => (
              <Skeleton key={i} className="h-64" />
            ))}
          </div>
        </div>
      )}

      {!sim.data && !sim.isPending && (
        <Card>
          <CardBody className="py-16 text-center">
            <Trophy className="mx-auto mb-4 h-10 w-10 text-pitch" aria-hidden />
            <h2 className="display text-2xl text-fg mb-2">
              Generate a full tournament path
            </h2>
            <p className="text-muted max-w-md mx-auto mb-5">
              Run the simulator to create group tables, best third-place rankings,
              knockout matchups, and a champion projection. Then click any team name
              to explore their squad.
            </p>
            <Button onClick={() => runSimulation()}>Run bracket simulation</Button>
          </CardBody>
        </Card>
      )}

      {sim.data && !sim.isPending && (
        <div className="space-y-10">
          {/* ── Summary cards ── */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardBody className="py-5">
                <p className="kicker mb-1">Champion</p>
                <div className="display text-3xl text-fg">
                  {sim.data.champion ?? "TBD"}
                </div>
                {sim.data.champion_probability != null && (
                  <p className="tnum text-pitch text-sm mt-1">
                    {pct(sim.data.champion_probability)} tournament odds
                  </p>
                )}
              </CardBody>
            </Card>
            <Card>
              <CardBody className="py-5">
                <p className="kicker mb-1">Runner-up</p>
                <div className="display text-3xl text-fg">
                  {sim.data.runner_up ?? "TBD"}
                </div>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="py-5">
                <p className="kicker mb-1">Third place</p>
                <div className="display text-3xl text-fg">
                  {sim.data.third_place ?? "TBD"}
                </div>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="py-5">
                <p className="kicker mb-1">Qualified to R32</p>
                <div className="display text-3xl text-fg">
                  {sim.data.qualified_teams?.length ?? 0}
                </div>
                <p className="text-xs text-muted mt-1">
                  24 automatic plus 8 best thirds
                </p>
              </CardBody>
            </Card>
          </div>

          {/* ── Simulation meta + save ── */}
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
            <span>
              <span className="tnum text-fg">{sim.data.runs.toLocaleString()}</span>{" "}
              run{sim.data.runs === 1 ? "" : "s"}
            </span>
            <span>
              Mode{" "}
              <span className="text-fg uppercase">
                {sim.data.prediction_mode ?? "ensemble"}
              </span>
            </span>
            {sim.data.seed != null && (
              <span>
                Seed <span className="tnum text-fg">{sim.data.seed}</span>
              </span>
            )}
            <div className="flex gap-2 sm:ml-auto">
              <SaveSimulationButton
                defaultName={`WC 2026 bracket (${sim.data.runs.toLocaleString()} runs)`}
                simulationType="wc2026"
                edition="2026"
                runs={sim.data.runs}
                seed={sim.data.seed}
                deterministic={sim.data.deterministic}
                tournamentResult={sim.data}
                championProbabilities={sim.data.teams}
                bracketOutput={{
                  group_tables: sim.data.group_tables,
                  group_stage_matches: sim.data.group_stage_matches,
                  qualified_teams: sim.data.qualified_teams,
                  best_third_place: sim.data.best_third_place,
                  knockout_bracket: sim.data.knockout_bracket,
                  matches: sim.data.matches,
                  prediction_mode: sim.data.prediction_mode,
                }}
              />
              <Link href="/saved">
                <Button variant="ghost" size="sm">
                  View Saved
                </Button>
              </Link>
            </div>
          </div>

          {/* ── Group stage ── */}
          {groupEntries.length > 0 && (
            <section className="space-y-4">
              <div>
                <p className="kicker mb-1">Group stage</p>
                <h2 className="display text-2xl text-fg">Tables and simulated fixtures</h2>
                <p className="text-xs text-muted mt-1">
                  <span className="inline-block w-2 h-2 rounded-sm bg-pitch/30 mr-1" />
                  Green = automatic qualifier&nbsp;&nbsp;
                  <span className="inline-block w-2 h-2 rounded-sm bg-amber-500/30 mr-1" />
                  Amber = best-third qualifier
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {groupEntries.map(([label, rows]) => (
                  <GroupCard
                    key={label}
                    label={label}
                    rows={rows}
                    matches={sim.data!.group_stage_matches?.[label] ?? []}
                  />
                ))}
              </div>

              {sim.data.best_third_place && sim.data.best_third_place.length > 0 && (
                <div className="max-w-sm">
                  <BestThirdTable rows={sim.data.best_third_place} />
                </div>
              )}
            </section>
          )}

          {/* ── Knockout bracket ── */}
          <section className="space-y-4">
            <div>
              <p className="kicker mb-1">Knockout bracket</p>
              <h2 className="display text-2xl text-fg">Round of 32 → Champion</h2>
              <p className="text-xs text-muted mt-1">
                Click any team name to view their squad. Winners advance through
                connected branches.
              </p>
            </div>
            {sim.data.knockout_bracket && sim.data.knockout_bracket.length > 0 ? (
              <TournamentBracket
                rounds={sim.data.knockout_bracket}
                champion={sim.data.champion}
                championProbability={sim.data.champion_probability}
                onTeamClick={setSelectedTeam}
              />
            ) : (
              <Card>
                <CardBody className="py-10 text-center text-muted">
                  Knockout bracket data not available in this simulation result.
                </CardBody>
              </Card>
            )}
          </section>
        </div>
      )}

      {/* Squad panel — slides in from right when a team is clicked */}
      <SquadPanel teamName={selectedTeam} onClose={() => setSelectedTeam(null)} />
    </div>
  );
}
