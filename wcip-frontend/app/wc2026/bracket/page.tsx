"use client";

import { useState } from "react";
import Link from "next/link";
import { RefreshCw, Shuffle, Trophy } from "lucide-react";
import { useWC2026Simulate } from "@/lib/queries";
import type {
  PredictionMode,
  WC2026GroupRow,
  WC2026KnockoutRound,
  WC2026Match,
  WC2026Simulation,
} from "@/lib/types";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { DataFreshnessStrip } from "@/components/data-freshness";
import { SaveSimulationButton } from "@/components/save-simulation-button";
import { pct } from "@/lib/utils";

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

function QualificationTag({ row }: { row: WC2026GroupRow }) {
  if (row.qualification_type === "automatic") {
    return <span className="text-[9px] text-pitch border border-pitch/30 rounded px-1">Q</span>;
  }
  if (row.qualification_type === "best_third") {
    return <span className="text-[9px] text-[hsl(45_95%_58%)] border border-[hsl(45_95%_58%/0.35)] rounded px-1">3rd</span>;
  }
  return <span className="text-[9px] text-muted border border-line rounded px-1">out</span>;
}

function GroupFixture({ match }: { match: WC2026Match }) {
  const prob = match.winner_probability != null ? pct(match.winner_probability) : "n/a";
  return (
    <div className="rounded border border-line/60 bg-ink/30 px-2 py-1.5 text-[10px]">
      <div className="flex items-center justify-between gap-2">
        <span className={match.winner === match.home ? "text-fg font-medium truncate" : "text-muted truncate"}>
          {match.home_code ?? match.home.slice(0, 3).toUpperCase()}
        </span>
        <span className="tnum text-fg">{match.home_goals}-{match.away_goals}</span>
        <span className={match.winner === match.away ? "text-fg font-medium truncate" : "text-muted truncate"}>
          {match.away_code ?? match.away.slice(0, 3).toUpperCase()}
        </span>
      </div>
      <div className="mt-1 flex justify-between text-muted">
        <span>{match.match_id}</span>
        <span>{match.winner ? `${match.winner} ${prob}` : `Draw ${prob}`}</span>
      </div>
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
      <CardHeader className="py-3 flex items-center justify-between">
        <span className="kicker">Group {label}</span>
        <span className="text-[10px] text-muted">Top 2 plus best thirds</span>
      </CardHeader>
      <CardBody className="space-y-3">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-[10px] text-muted border-b border-line/50">
              <th className="py-1.5 text-left font-normal">Team</th>
              <th className="py-1.5 text-right font-normal">GD</th>
              <th className="py-1.5 text-right font-normal">Pts</th>
              <th className="py-1.5 text-right font-normal">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.team} className="border-b border-line/40 last:border-0">
                <td className="py-1.5">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="tnum text-[10px] text-muted w-3">{row.rank}</span>
                    <span className={row.qualified ? "text-fg font-medium truncate" : "text-muted truncate"}>
                      {row.team}
                    </span>
                  </div>
                </td>
                <td className="py-1.5 text-right tnum text-muted">
                  {row.goal_difference > 0 ? "+" : ""}{row.goal_difference}
                </td>
                <td className="py-1.5 text-right tnum text-fg font-semibold">{row.points}</td>
                <td className="py-1.5 text-right"><QualificationTag row={row} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="grid grid-cols-2 gap-1.5">
          {matches.map((match) => <GroupFixture key={match.match_id} match={match} />)}
        </div>
      </CardBody>
    </Card>
  );
}

function MatchCard({ match }: { match: WC2026Match }) {
  const winnerProb = match.winner_probability != null ? pct(match.winner_probability) : "n/a";
  const modeLabel = (match.effective_prediction_mode ?? match.prediction_mode ?? "ensemble").replace("_", " ");
  const teamRow = (team: string, code: string | undefined, goals: number) => (
    <div className="flex items-center justify-between gap-2">
      <div className="flex min-w-0 items-center gap-2">
        <span className="w-8 shrink-0 font-mono text-[10px] text-muted">{code ?? team.slice(0, 3).toUpperCase()}</span>
        <span className={match.winner === team ? "truncate font-semibold text-fg" : "truncate text-muted"}>
          {team}
        </span>
      </div>
      <span className={`tnum shrink-0 ${match.winner === team ? "font-semibold text-pitch" : "text-fg"}`}>
        {goals}
      </span>
    </div>
  );

  return (
    <div className="rounded-md border border-line bg-elevated/50 p-3 text-xs space-y-2">
      {teamRow(match.home, match.home_code, match.home_goals)}
      {teamRow(match.away, match.away_code, match.away_goals)}
      <div className="grid grid-cols-2 gap-2 border-t border-line/50 pt-2 text-[10px] text-muted">
        <span>{match.match_id}</span>
        <span className="text-right capitalize">{match.decided_by.replace("_", " ")}</span>
        <span>Winner probability</span>
        <span className="text-right tnum text-pitch">{winnerProb}</span>
        <span>Prediction mode</span>
        <span className="text-right uppercase">{modeLabel}</span>
      </div>
      {match.advancement_reason && (
        <p className="text-[10px] leading-snug text-muted">{match.advancement_reason}</p>
      )}
    </div>
  );
}

function BracketColumns({ rounds }: { rounds?: WC2026KnockoutRound[] }) {
  const visibleRounds = (rounds ?? []).filter((round) => round.matches.length > 0);
  if (!visibleRounds.length) return null;
  return (
    <div className="overflow-x-auto pb-2">
      <div
        className="grid gap-4 min-w-[1280px]"
        style={{ gridTemplateColumns: `repeat(${visibleRounds.length}, minmax(190px, 1fr))` }}
      >
        {visibleRounds.map((round) => (
          <section key={round.round} className="space-y-2">
            <div className="kicker text-center">{round.round}</div>
            {round.matches
              .slice()
              .sort((a, b) => a.order - b.order)
              .map((match) => <MatchCard key={match.match_id} match={match} />)}
          </section>
        ))}
      </div>
    </div>
  );
}

function SummaryCards({ sim }: { sim: WC2026Simulation }) {
  return (
    <div className="grid gap-4 md:grid-cols-4">
      <Card>
        <CardBody className="py-5">
          <p className="kicker mb-1">Champion</p>
          <div className="display text-3xl text-fg">{sim.champion ?? "TBD"}</div>
          {sim.champion_probability != null && (
            <p className="tnum text-pitch text-sm mt-1">{pct(sim.champion_probability)} tournament odds</p>
          )}
        </CardBody>
      </Card>
      <Card>
        <CardBody className="py-5">
          <p className="kicker mb-1">Runner-up</p>
          <div className="display text-3xl text-fg">{sim.runner_up ?? "TBD"}</div>
        </CardBody>
      </Card>
      <Card>
        <CardBody className="py-5">
          <p className="kicker mb-1">Third place</p>
          <div className="display text-3xl text-fg">{sim.third_place ?? "TBD"}</div>
        </CardBody>
      </Card>
      <Card>
        <CardBody className="py-5">
          <p className="kicker mb-1">Qualified to R32</p>
          <div className="display text-3xl text-fg">{sim.qualified_teams?.length ?? 0}</div>
          <p className="text-xs text-muted mt-1">24 automatic plus 8 best thirds</p>
        </CardBody>
      </Card>
    </div>
  );
}

function BracketResult({ sim }: { sim: WC2026Simulation }) {
  const groupEntries = Object.entries(sim.group_tables ?? {}).sort(([a], [b]) => a.localeCompare(b));
  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
        <span><span className="tnum text-fg">{sim.runs.toLocaleString()}</span> run{sim.runs === 1 ? "" : "s"}</span>
        <span>Mode <span className="text-fg uppercase">{sim.prediction_mode ?? "ensemble"}</span></span>
        {sim.seed != null && <span>Seed <span className="tnum text-fg">{sim.seed}</span></span>}
        <div className="flex gap-2 sm:ml-auto">
          <SaveSimulationButton
            defaultName={`WC 2026 bracket (${sim.runs.toLocaleString()} runs)`}
            simulationType="wc2026"
            edition="2026"
            runs={sim.runs}
            seed={sim.seed}
            deterministic={sim.deterministic}
            tournamentResult={sim}
            championProbabilities={sim.teams}
            bracketOutput={{
              group_tables: sim.group_tables,
              group_stage_matches: sim.group_stage_matches,
              qualified_teams: sim.qualified_teams,
              best_third_place: sim.best_third_place,
              knockout_bracket: sim.knockout_bracket,
              matches: sim.matches,
              prediction_mode: sim.prediction_mode,
            }}
          />
          <Link href="/saved">
            <Button variant="ghost" size="sm">View Saved</Button>
          </Link>
        </div>
      </div>

      <SummaryCards sim={sim} />

      <section className="space-y-4">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="kicker mb-1">Group stage</p>
            <h2 className="display text-2xl text-fg">Tables and simulated fixtures</h2>
          </div>
          <span className="text-xs text-muted">{sim.best_third_place?.length ?? 0} best third-place teams selected</span>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {groupEntries.map(([label, rows]) => (
            <GroupCard
              key={label}
              label={label}
              rows={rows}
              matches={sim.group_stage_matches?.[label] ?? []}
            />
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <p className="kicker mb-1">Knockout bracket</p>
          <h2 className="display text-2xl text-fg">Round of 32 to champion</h2>
        </div>
        <BracketColumns rounds={sim.knockout_bracket} />
      </section>
    </div>
  );
}

export default function WC2026BracketPage() {
  const [runs, setRuns] = useState(10000);
  const [predictionMode, setPredictionMode] = useState<PredictionMode>("ensemble");
  const sim = useWC2026Simulate();

  const runSimulation = (nextRuns = runs) => {
    sim.mutate({ runs: nextRuns, predictionMode, seed: null, deterministic: false });
  };

  const runSingleRandom = () => {
    setRuns(1);
    runSimulation(1);
  };

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker mb-2">World Cup 2026</p>
          <h1 className="display text-4xl text-fg">Bracket Simulator</h1>
          <p className="text-muted mt-2 max-w-2xl">
            Project the 48-team group stage, the eight best third-place qualifiers, and every knockout matchup through the final.
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
                  runs === value ? "border-pitch bg-pitch/10 text-pitch" : "border-line text-muted hover:text-fg"
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
          <Button variant="outline" size="sm" onClick={() => runSimulation()}>Retry</Button>
        </div>
      )}

      {sim.isPending && (
        <div className="space-y-5">
          <div className="grid gap-4 md:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-72" />)}
          </div>
        </div>
      )}

      {!sim.data && !sim.isPending && (
        <Card>
          <CardBody className="py-16 text-center">
            <Trophy className="mx-auto mb-4 h-10 w-10 text-pitch" aria-hidden />
            <h2 className="display text-2xl text-fg mb-2">Generate a full tournament path</h2>
            <p className="text-muted max-w-md mx-auto mb-5">
              Run the simulator to create group tables, best third-place rankings, knockout matchups, and a champion projection.
            </p>
            <Button onClick={() => runSimulation()}>Run bracket simulation</Button>
          </CardBody>
        </Card>
      )}

      {sim.data && !sim.isPending && <BracketResult sim={sim.data} />}
    </div>
  );
}
