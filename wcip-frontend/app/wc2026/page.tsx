"use client";

import Link from "next/link";
import { useMemo } from "react";
import { BarChart3, CalendarClock, Database, Trophy } from "lucide-react";
import { AskAnalystBox } from "@/components/AskAnalystBox";
import {
  useDataFreshness,
  useWC2026Groups,
  useWC2026Teams,
  useWorldCupWinnerPredictions,
} from "@/lib/queries";
import type { QualifiedTeam, WorldCupWinnerPrediction } from "@/lib/types";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { DataFreshnessStrip } from "@/components/data-freshness";
import { formatProbability, normalizeProbabilityValue } from "@/lib/utils";

function stableDate(value: string | null | undefined) {
  if (!value) return "Unavailable";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Unavailable" : parsed.toISOString().slice(0, 10);
}

function StatCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail: string;
}) {
  return (
    <Card>
      <CardBody className="py-5">
        <p className="kicker mb-1">{label}</p>
        <div className="display text-3xl text-fg">{value}</div>
        <p className="mt-1 text-xs text-muted">{detail}</p>
      </CardBody>
    </Card>
  );
}

function ContenderRow({ prediction, rank }: { prediction: WorldCupWinnerPrediction; rank: number }) {
  return (
    <div className="grid grid-cols-[2rem_1fr_auto] items-center gap-3 border-b border-line/40 py-2 last:border-0">
      <span className="tnum text-xs text-muted">{rank}</span>
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-fg">{prediction.team_name}</div>
        <div className="text-[10px] text-muted">
          {prediction.fifa_code} · Group {prediction.group ?? "-"} · FIFA #{prediction.fifa_rank}
        </div>
      </div>
      <span className="tnum text-sm font-semibold text-pitch">
        {formatProbability(prediction.champion_probability)}
      </span>
    </div>
  );
}

function GroupPreview({ label, teams }: { label: string; teams: QualifiedTeam[] }) {
  return (
    <Card>
      <CardHeader className="py-3">
        <span className="kicker">Group {label}</span>
      </CardHeader>
      <CardBody className="space-y-1.5 py-2">
        {teams.map((team) => (
          <div key={team.team_name} className="flex items-center justify-between gap-3 text-xs">
            <div className="min-w-0">
              <div className="truncate text-fg">{team.team_name}</div>
              <div className="text-[10px] text-muted">{team.team_code} · {team.confederation}</div>
            </div>
            <div className="shrink-0 text-right">
              <div className="tnum text-pitch">{team.elo_rating ? Math.round(team.elo_rating) : "-"}</div>
              <div className="tnum text-[10px] text-muted">FIFA {team.fifa_rank ? `#${team.fifa_rank}` : "-"}</div>
            </div>
          </div>
        ))}
      </CardBody>
    </Card>
  );
}

export default function WC2026OverviewPage() {
  const teams = useWC2026Teams({ confirmed_only: true });
  const groups = useWC2026Groups();
  const freshness = useDataFreshness();
  const predictions = useWorldCupWinnerPredictions(5000);

  const teamsByGroup = useMemo(() => {
    const map = new Map<string, QualifiedTeam[]>();
    for (const team of teams.data ?? []) {
      const label = team.group_label ?? "TBD";
      const bucket = map.get(label) ?? [];
      bucket.push(team);
      map.set(label, bucket);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [teams.data]);

  const topPredictions = useMemo(
    () =>
      (predictions.data ?? []).map((prediction) => ({
        ...prediction,
        champion_probability: normalizeProbabilityValue(prediction.champion_probability),
      })),
    [predictions.data]
  );
  const topFour = topPredictions.slice(0, 4);
  const likelyFinal = topPredictions.slice(0, 2);
  const darkHorses = topPredictions.slice(5, 10);
  const squadCount = (teams.data ?? []).reduce((sum, team) => sum + (team.confirmed ? 1 : 0), 0);

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker mb-2">World Cup Intelligence Center</p>
          <h1 className="display text-4xl text-fg">WC 2026 Overview</h1>
          <p className="mt-2 max-w-2xl text-muted">
            A compact read on the 48-team field, data freshness, top contenders,
            and the current group picture. Full match-by-match simulation lives in Bracket.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/wc2026/bracket">
            <Button>
              <Trophy className="h-4 w-4" />
              Open Bracket Simulation
            </Button>
          </Link>
          <Link href="/teams">
            <Button variant="outline">Browse Teams</Button>
          </Link>
        </div>
      </header>

      <DataFreshnessStrip />

      <section>
        <h2 className="kicker mb-3">Ask the Analyst</h2>
        <AskAnalystBox
          contextType="tournament"
          placeholder="Ask about groups, teams, squads, or the tournament..."
        />
      </section>

      {(teams.isError || groups.isError || predictions.isError) && (
        <Card>
          <CardBody className="flex flex-wrap items-center justify-between gap-3 text-sm text-signal">
            <span>
              Some WC 2026 data could not be loaded. Check that the backend is running and seeded.
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                void teams.refetch();
                void groups.refetch();
                void predictions.refetch();
              }}
            >
              Retry
            </Button>
          </CardBody>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Qualified teams"
          value={groups.data?.qualification_status.confirmed ?? teams.data?.length ?? "-"}
          detail={`${groups.data?.qualification_status.total_slots ?? 48} tournament slots`}
        />
        <StatCard
          label="Groups"
          value={groups.data ? Object.keys(groups.data.groups).length : "-"}
          detail={groups.data?.draw_complete ? "Group draw loaded" : "Using available group data"}
        />
        <StatCard
          label="Latest Elo"
          value={stableDate(topPredictions[0]?.elo_source_date ?? freshness.data?.last_elo_rating_date)}
          detail={topPredictions[0]?.elo_snapshot_version ?? freshness.data?.elo_data_version ?? "Snapshot metadata pending"}
        />
        <StatCard
          label="Squad status"
          value={`${squadCount}/48`}
          detail={`Players updated ${stableDate(freshness.data?.last_player_data_update)}`}
        />
      </div>

      {predictions.isLoading ? (
        <div className="grid gap-5 lg:grid-cols-2">
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
        </div>
      ) : (
        <div className="grid gap-5 lg:grid-cols-2">
          <Card>
            <CardHeader className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-pitch" />
              <span className="kicker">Top champion probabilities</span>
            </CardHeader>
            <CardBody>
              {topFour.length ? (
                topFour.map((prediction, index) => (
                  <ContenderRow
                    key={prediction.team_name}
                    prediction={prediction}
                    rank={index + 1}
                  />
                ))
              ) : (
                <p className="py-8 text-center text-sm text-muted">
                  No winner predictions are available yet.
                </p>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader className="flex items-center gap-2">
              <CalendarClock className="h-4 w-4 text-pitch" />
              <span className="kicker">Most likely final and dark horses</span>
            </CardHeader>
            <CardBody className="space-y-5">
              {likelyFinal.length === 2 ? (
                <div className="rounded-lg border border-line bg-elevated/50 px-4 py-5 text-center">
                  <p className="kicker mb-2">Most likely final</p>
                  <div className="display text-2xl text-fg">
                    {likelyFinal[0].team_name}
                    <span className="mx-3 text-base text-muted">vs</span>
                    {likelyFinal[1].team_name}
                  </div>
                  <p className="mt-2 text-xs text-muted">
                    Based on the current ensemble tournament probability table.
                  </p>
                </div>
              ) : (
                <p className="text-sm text-muted">Run predictions to populate likely final data.</p>
              )}
              <div>
                <p className="kicker mb-2">Dark horse range</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {darkHorses.map((prediction) => (
                    <div
                      key={prediction.team_name}
                      className="flex items-center justify-between rounded-md border border-line px-3 py-2 text-xs"
                    >
                      <span className="truncate text-fg">{prediction.team_name}</span>
                      <span className="tnum text-pitch">{formatProbability(prediction.champion_probability)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </CardBody>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader className="flex items-center gap-2">
          <Database className="h-4 w-4 text-pitch" />
          <span className="kicker">Data freshness</span>
        </CardHeader>
        <CardBody className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["FIFA ranking", stableDate(freshness.data?.last_fifa_ranking_date), freshness.data?.fifa_data_version],
            ["Elo rating", stableDate(freshness.data?.last_elo_rating_date), freshness.data?.elo_data_version],
            ["Squads", stableDate(freshness.data?.last_player_data_update), freshness.data?.player_data_source],
            ["Model", stableDate(freshness.data?.model_trained_at), freshness.data?.model_version],
          ].map(([label, value, detail]) => (
            <div key={label} className="rounded-lg border border-line px-3 py-3">
              <div className="kicker mb-1">{label}</div>
              <div className="tnum text-sm text-fg">{value}</div>
              <div className="mt-1 truncate text-[10px] text-muted">{detail || "Pending"}</div>
            </div>
          ))}
        </CardBody>
      </Card>

      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="kicker mb-1">Latest group standings</p>
            <h2 className="display text-2xl text-fg">Pre-tournament group snapshot</h2>
            <p className="mt-1 text-xs text-muted">
              Rankings shown here are current input signals, not simulated match results.
            </p>
          </div>
          <Link href="/wc2026/bracket">
            <Button variant="outline" size="sm">Simulate group stage</Button>
          </Link>
        </div>

        {teams.isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-48" />
            ))}
          </div>
        ) : teamsByGroup.length ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {teamsByGroup.map(([label, groupTeams]) => (
              <GroupPreview key={label} label={label} teams={groupTeams} />
            ))}
          </div>
        ) : (
          <Card>
            <CardBody className="py-12 text-center text-sm text-muted">
              No WC 2026 team data is loaded yet. Run the backend seed/ETL before opening this page.
            </CardBody>
          </Card>
        )}
      </section>
    </div>
  );
}
