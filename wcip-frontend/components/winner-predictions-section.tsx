"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { RefreshCw } from "lucide-react";
import { useWorldCupWinnerPredictions } from "@/lib/queries";
import type { ApiError } from "@/lib/api";
import type { WorldCupWinnerPrediction } from "@/lib/types";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

const COLORS = [
  "hsl(75 95% 55%)",
  "hsl(200 90% 62%)",
  "hsl(45 95% 58%)",
  "hsl(280 70% 68%)",
  "hsl(8 90% 64%)",
  "hsl(140 70% 50%)",
  "hsl(220 90% 62%)",
  "hsl(25 90% 58%)",
];

function pct(value: number, digits = 1) {
  return `${value.toFixed(digits)}%`;
}

function ChampionProbabilityChart({ rows }: { rows: WorldCupWinnerPrediction[] }) {
  const data = rows.slice(0, 10);
  return (
    <ResponsiveContainer width="100%" height={Math.max(260, data.length * 34)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 32, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" horizontal={false} />
        <XAxis type="number" tickFormatter={(v) => `${v}%`} stroke="hsl(var(--muted))" fontSize={11} />
        <YAxis
          type="category"
          dataKey="team_name"
          width={96}
          stroke="hsl(var(--muted))"
          fontSize={11}
          tick={{ fill: "hsl(var(--fg))" }}
        />
        <Tooltip
          formatter={(v: number) => [pct(v), "Champion"]}
          contentStyle={{
            background: "hsl(var(--surface))",
            border: "1px solid hsl(var(--line))",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Bar dataKey="champion_probability" radius={[0, 4, 4, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function ModelComparisonChart({ rows }: { rows: WorldCupWinnerPrediction[] }) {
  const data = rows.slice(0, 10);
  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" vertical={false} />
        <XAxis
          dataKey="fifa_code"
          stroke="hsl(var(--muted))"
          fontSize={11}
          tick={{ fill: "hsl(var(--muted))" }}
        />
        <YAxis tickFormatter={(v) => `${v}%`} stroke="hsl(var(--muted))" fontSize={11} />
        <Tooltip
          formatter={(v: number, name: string) => [
            pct(v),
            name === "statistical_probability"
              ? "Statistical"
              : name === "ml_probability"
                ? "ML"
                : "Ensemble",
          ]}
          contentStyle={{
            background: "hsl(var(--surface))",
            border: "1px solid hsl(var(--line))",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="statistical_probability" fill="hsl(45 95% 58%)" name="Statistical" />
        <Bar dataKey="ml_probability" fill="hsl(200 90% 62%)" name="ML" />
        <Bar dataKey="ensemble_probability" fill="hsl(75 95% 55%)" name="Ensemble" />
      </BarChart>
    </ResponsiveContainer>
  );
}

function ConfederationBreakdown({ rows }: { rows: WorldCupWinnerPrediction[] }) {
  const grouped = Object.values(
    rows.reduce<Record<string, { confederation: string; champion_probability: number }>>((acc, row) => {
      const key = row.confederation || "Unknown";
      acc[key] ??= { confederation: key, champion_probability: 0 };
      acc[key].champion_probability += row.champion_probability;
      return acc;
    }, {})
  ).sort((a, b) => b.champion_probability - a.champion_probability);

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={grouped} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" vertical={false} />
        <XAxis dataKey="confederation" stroke="hsl(var(--muted))" fontSize={11} />
        <YAxis tickFormatter={(v) => `${v}%`} stroke="hsl(var(--muted))" fontSize={11} />
        <Tooltip
          formatter={(v: number) => [pct(v), "Champion Share"]}
          contentStyle={{
            background: "hsl(var(--surface))",
            border: "1px solid hsl(var(--line))",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Bar dataKey="champion_probability" fill="hsl(200 90% 62%)" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function PredictionTable({ rows }: { rows: WorldCupWinnerPrediction[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="kicker text-left border-b border-line">
            <th className="py-3 pr-3 font-normal">#</th>
            <th className="py-3 pr-3 font-normal">Team</th>
            <th className="py-3 pr-3 font-normal">Group</th>
            <th className="py-3 pr-3 font-normal text-right">FIFA</th>
            <th className="py-3 pr-3 font-normal text-right">Elo</th>
            <th className="py-3 pr-3 font-normal text-right">Champion</th>
            <th className="py-3 pr-3 font-normal text-right">Final</th>
            <th className="py-3 pr-3 font-normal text-right">Semi</th>
            <th className="py-3 pr-3 font-normal text-right">Quarter</th>
            <th className="py-3 pr-3 font-normal text-right">ML</th>
            <th className="py-3 pr-3 font-normal text-right">Stat</th>
            <th className="py-3 font-normal text-right">Ensemble</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.team_name} className="border-b border-line/50">
              <td className="py-2 pr-3 tnum text-muted">{row.rank}</td>
              <td className="py-2 pr-3">
                <div className="font-medium text-fg">{row.team_name}</div>
                <div className="text-[11px] text-muted">{row.fifa_code} · {row.confederation}</div>
              </td>
              <td className="py-2 pr-3 text-muted">{row.group ?? "TBD"}</td>
              <td className="py-2 pr-3 text-right tnum">{row.fifa_rank}</td>
              <td className="py-2 pr-3 text-right tnum">{row.elo_rating_used ? Math.round(row.elo_rating_used) : "n/a"}</td>
              <td className="py-2 pr-3 text-right tnum text-pitch">{pct(row.champion_probability)}</td>
              <td className="py-2 pr-3 text-right tnum">{pct(row.final_probability)}</td>
              <td className="py-2 pr-3 text-right tnum">{pct(row.semifinal_probability)}</td>
              <td className="py-2 pr-3 text-right tnum">{pct(row.quarterfinal_probability)}</td>
              <td className="py-2 pr-3 text-right tnum">{pct(row.ml_probability)}</td>
              <td className="py-2 pr-3 text-right tnum">{pct(row.statistical_probability)}</td>
              <td className="py-2 text-right tnum">{pct(row.ensemble_probability)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FavoritesList({ rows }: { rows: WorldCupWinnerPrediction[] }) {
  return (
    <div className="space-y-2">
      {rows.slice(0, 10).map((row) => (
        <div key={row.team_name} className="flex items-center justify-between gap-3 border-b border-line/50 pb-2">
          <div>
            <div className="font-medium text-fg">{row.rank}. {row.team_name}</div>
            <div className="text-xs text-muted">{row.explanation}</div>
          </div>
          <div className="tnum text-pitch">{pct(row.champion_probability)}</div>
        </div>
      ))}
    </div>
  );
}

function DarkHorseList({ rows }: { rows: WorldCupWinnerPrediction[] }) {
  const darkHorses = rows
    .filter((row) => row.rank > 8 && row.champion_probability >= 1.25)
    .slice(0, 8);

  if (!darkHorses.length) {
    return <p className="text-sm text-muted">No dark-horse teams cross the current threshold.</p>;
  }

  return (
    <div className="space-y-2">
      {darkHorses.map((row) => (
        <div key={row.team_name} className="flex items-center justify-between gap-3 border-b border-line/50 pb-2">
          <div>
            <div className="font-medium text-fg">{row.team_name}</div>
            <div className="text-xs text-muted">FIFA {row.fifa_rank} · {row.group ?? "TBD"}</div>
          </div>
          <div className="tnum text-[hsl(45_95%_58%)]">{pct(row.champion_probability)}</div>
        </div>
      ))}
    </div>
  );
}

export function WinnerPredictionsSection({ compact = false }: { compact?: boolean }) {
  const query = useWorldCupWinnerPredictions(compact ? 1000 : 5000);
  const rows = query.data ?? [];

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="kicker mb-1">World Cup Winner Predictions</p>
          <h2 className="display text-2xl">2026 title forecast</h2>
          {rows[0]?.data_snapshot_version && (
            <p className="text-xs text-muted mt-1">
              Snapshot <span className="tnum">{rows[0].data_snapshot_version}</span>
            </p>
          )}
        </div>
        <Button onClick={() => query.refetch()} disabled={query.isFetching} variant="outline" size="sm">
          <RefreshCw className={`h-3.5 w-3.5 ${query.isFetching ? "animate-spin" : ""}`} aria-hidden />
          {query.isFetching ? "Refreshing" : "Update Predictions"}
        </Button>
      </div>

      {query.isLoading && (
        <div className="grid gap-5 lg:grid-cols-2">
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
        </div>
      )}

      {query.isError && (
        <Card>
          <CardBody className="space-y-3">
            <div className="text-signal font-medium">Winner predictions could not be loaded.</div>
            <p className="text-sm text-muted">{(query.error as Error).message}</p>
            {process.env.NODE_ENV === "development" && (
              <pre className="text-xs text-muted overflow-x-auto bg-elevated rounded-md p-3">
                {JSON.stringify({
                  status: (query.error as ApiError).status,
                  errorCode: (query.error as ApiError).errorCode,
                  requestId: (query.error as ApiError).requestId,
                }, null, 2)}
              </pre>
            )}
            <Button onClick={() => query.refetch()} size="sm">Retry</Button>
          </CardBody>
        </Card>
      )}

      {!query.isLoading && !query.isError && rows.length === 0 && (
        <Card>
          <CardBody className="text-sm text-muted">No winner predictions are available.</CardBody>
        </Card>
      )}

      {rows.length > 0 && (
        <>
          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader><span className="kicker">Champion Probability Bar Chart</span></CardHeader>
              <CardBody><ChampionProbabilityChart rows={rows} /></CardBody>
            </Card>
            <Card>
              <CardHeader><span className="kicker">Model Comparison Chart</span></CardHeader>
              <CardBody><ModelComparisonChart rows={rows} /></CardBody>
            </Card>
          </div>

          {!compact && (
            <div className="grid gap-5 lg:grid-cols-3">
              <Card>
                <CardHeader><span className="kicker">Confederation Breakdown</span></CardHeader>
                <CardBody><ConfederationBreakdown rows={rows} /></CardBody>
              </Card>
              <Card>
                <CardHeader><span className="kicker">Top 10 Favorites</span></CardHeader>
                <CardBody><FavoritesList rows={rows} /></CardBody>
              </Card>
              <Card>
                <CardHeader><span className="kicker">Dark Horse Teams</span></CardHeader>
                <CardBody><DarkHorseList rows={rows} /></CardBody>
              </Card>
            </div>
          )}

          <Card>
            <CardHeader className="flex justify-between items-baseline">
              <span className="kicker">Ranked table</span>
              <span className="tnum text-xs text-muted">
                {rows.reduce((sum, row) => sum + row.champion_probability, 0).toFixed(1)}% total
              </span>
            </CardHeader>
            <CardBody>
              <PredictionTable rows={compact ? rows.slice(0, 12) : rows} />
            </CardBody>
          </Card>
        </>
      )}
    </section>
  );
}
