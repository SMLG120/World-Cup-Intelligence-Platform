"use client";

import { use } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  CartesianGrid,
} from "recharts";
import { useTeam, useEloHistory, useTeamSquad, useWC2026TeamDetail } from "@/lib/queries";
import type { Player } from "@/lib/types";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { DataFreshnessStrip } from "@/components/data-freshness";
import { AskAnalystBox } from "@/components/AskAnalystBox";
import { ShieldAlert } from "lucide-react";

// ── Stat box ──────────────────────────────────────────────────────────────────

function Stat({
  label, value, accent, sub,
}: {
  label: string; value: string | number; accent?: boolean; sub?: string;
}) {
  return (
    <div className="rounded-lg border border-line p-4 bg-surface/60">
      <div className="kicker">{label}</div>
      <div className={`tnum text-2xl mt-1 ${accent ? "text-pitch" : "text-fg"}`}>{value}</div>
      {sub && <div className="text-xs text-muted mt-0.5">{sub}</div>}
    </div>
  );
}

// ── Team radar ────────────────────────────────────────────────────────────────

function TeamRadar({ detail }: { detail: { attack: number; defence: number; chemistry: number; form_ppg: number; squad_stats: { avg_fitness: number } } }) {
  const data = [
    { subject: "Attack", value: Math.min(100, detail.attack * 50), full: 100 },
    { subject: "Defence", value: Math.min(100, detail.defence * 50), full: 100 },
    { subject: "Chemistry", value: detail.chemistry * 100, full: 100 },
    { subject: "Form", value: Math.min(100, (detail.form_ppg / 3) * 100), full: 100 },
    { subject: "Fitness", value: detail.squad_stats.avg_fitness * 100, full: 100 },
  ];

  return (
    <ResponsiveContainer width="100%" height={280}>
      <RadarChart data={data} margin={{ top: 12, right: 20, bottom: 12, left: 20 }}>
        <PolarGrid stroke="hsl(var(--line))" />
        <PolarAngleAxis
          dataKey="subject"
          tick={{ fill: "hsl(var(--muted))", fontSize: 12 }}
        />
        <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} axisLine={false} />
        <Radar
          name="Team"
          dataKey="value"
          stroke="hsl(var(--pitch))"
          fill="hsl(var(--pitch))"
          fillOpacity={0.25}
          strokeWidth={2}
        />
        <Tooltip
          formatter={(v: number) => [`${v.toFixed(1)}`, "Score"]}
          contentStyle={{
            background: "hsl(var(--elevated))", border: "1px solid hsl(var(--line))",
            borderRadius: 8, fontSize: 11,
          }}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}

// ── Elo trend ─────────────────────────────────────────────────────────────────

function EloTrend({ history }: { history: { rating: number; opponent: string | null; recorded_at: string }[] }) {
  const data = history.map((p, i) => ({
    point: i + 1,
    rating: Math.round(p.rating),
    label: p.opponent ?? "seed",
  }));

  if (data.length <= 1) {
    return (
      <p className="text-muted text-sm py-8 text-center">
        Only the seed rating is stored so far. As match results are ingested, this chart fills in.
      </p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
        <defs>
          <linearGradient id="elo-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--pitch))" stopOpacity={0.4} />
            <stop offset="100%" stopColor="hsl(var(--pitch))" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" />
        <XAxis dataKey="point" stroke="hsl(var(--muted))" fontSize={11} />
        <YAxis domain={["dataMin - 30", "dataMax + 30"]} stroke="hsl(var(--muted))" fontSize={11} />
        <Tooltip
          formatter={(v: number) => [v, "Elo"]}
          labelFormatter={(l: number) => data[l - 1]?.label ?? `Match ${l}`}
          contentStyle={{
            background: "hsl(var(--elevated))", border: "1px solid hsl(var(--line))",
            borderRadius: 8, fontSize: 11,
          }}
          labelStyle={{ color: "hsl(var(--fg))", fontWeight: "bold" }}
        />
        <Area type="monotone" dataKey="rating" stroke="hsl(var(--pitch))" strokeWidth={2} fill="url(#elo-grad)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ── Squad brief ───────────────────────────────────────────────────────────────

function SquadBrief({
  players,
  teamName,
}: {
  players: Player[];
  teamName: string;
}) {
  if (!players.length) {
    return (
      <p className="text-muted text-sm text-center py-6">
        Squad data incomplete — check ingestion status.
      </p>
    );
  }

  const positionOrder: Record<string, number> = { GK: 0, DEF: 1, DF: 1, MID: 2, MF: 2, FWD: 3, FW: 3 };
  const sorted = [...players].sort((a, b) => {
    const byPosition = (positionOrder[a.position] ?? 9) - (positionOrder[b.position] ?? 9);
    if (byPosition !== 0) return byPosition;
    return (a.shirt_number ?? 99) - (b.shirt_number ?? 99) || a.name.localeCompare(b.name);
  });

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="kicker border-b border-line">
          <th className="py-2 text-left font-normal">Player</th>
          <th className="py-2 text-left font-normal hidden sm:table-cell">Pos</th>
          <th className="py-2 text-left font-normal hidden md:table-cell">Club</th>
          <th className="py-2 text-right font-normal hidden sm:table-cell">Ht</th>
          <th className="py-2 text-right font-normal">Caps</th>
          <th className="py-2 text-right font-normal">G</th>
          <th className="py-2 text-right font-normal hidden sm:table-cell">A</th>
          <th className="py-2 text-right font-normal">Status</th>
          <th className="py-2 text-right font-normal hidden md:table-cell">Profile</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((p) => {
          const isPlaceholder = p.data_source === "world_cup_2026_placeholder";
          return (
            <tr key={p.id} className="border-b border-line/40 hover:bg-elevated/60 transition-colors">
              <td className="py-1.5 font-medium">
                <span>{p.name}</span>
                {isPlaceholder && <span className="ml-2 text-[10px] uppercase tracking-wide text-muted">placeholder</span>}
              </td>
              <td className="py-1.5 text-muted text-xs hidden sm:table-cell">{p.position}</td>
              <td className="py-1.5 text-muted text-xs hidden md:table-cell">{p.club ?? "-"}</td>
              <td className="py-1.5 text-right tnum text-muted hidden sm:table-cell">
                {p.height_cm ? `${p.height_cm}` : "-"}
              </td>
              <td className="py-1.5 text-right tnum text-muted">{p.international_caps ?? 0}</td>
              <td className="py-1.5 text-right tnum text-muted">{p.international_goals ?? p.goals ?? 0}</td>
              <td className="py-1.5 text-right tnum text-muted hidden sm:table-cell">{p.assists ?? 0}</td>
              <td className="py-1.5 text-right">
                {isPlaceholder ? (
                  <span className="text-xs text-muted">Pending</span>
                ) : p.injured ? (
                  <span className="text-xs text-signal">Injured</span>
                ) : p.suspended ? (
                  <span className="text-xs text-[hsl(45_95%_58%)]">Susp.</span>
                ) : (
                  <span className="text-xs text-pitch">Fit</span>
                )}
              </td>
              <td className="py-1.5 text-right hidden md:table-cell">
                {isPlaceholder ? (
                  <span className="text-xs text-muted">Pending</span>
                ) : (
                  <Link
                    href={`/player/${p.id}?team=${encodeURIComponent(teamName)}`}
                    className="text-xs text-muted hover:text-pitch transition-colors"
                  >
                    View →
                  </Link>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TeamPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const teamId = Number(id);

  const { data: team, isLoading, isError } = useTeam(teamId);
  const { data: history } = useEloHistory(teamId);
  const { data: wc2026Detail } = useWC2026TeamDetail(team?.name ?? "", !!team?.name);
  const { data: squadData, isLoading: squadLoading, isError: squadError } = useTeamSquad(teamId, !!team);

  if (isError) {
    return (
      <div className="py-16 text-center">
        <h1 className="display text-3xl mb-2">Team not found</h1>
        <Link href="/teams"><Button variant="outline">Back to teams</Button></Link>
      </div>
    );
  }

  if (isLoading || !team) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-12 w-64" />
        <div className="grid gap-4 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  const trend = (history ?? []).map((p, i) => ({
    point: i + 1,
    rating: Math.round(p.rating),
    opponent: p.opponent ?? "seed",
    recorded_at: p.recorded_at,
  }));
  const coachIsPlaceholder = wc2026Detail?.coach.data_source === "world_cup_2026_placeholder";
  const coachSub = coachIsPlaceholder
    ? "Placeholder"
    : wc2026Detail?.coach.formation ?? undefined;

  return (
    <div className="space-y-8">
      <motion.header
        initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
        className="flex flex-wrap items-end justify-between gap-4"
      >
        <div>
          <Link href="/teams" className="kicker hover:text-pitch transition-colors">← Teams</Link>
          <h1 className="display text-5xl mt-2">{team.name}</h1>
          <div className="flex items-center gap-3 mt-2">
            <span className="text-xs border border-line px-2 py-0.5 rounded text-muted">{team.confederation}</span>
            <span className="text-xs border border-line px-2 py-0.5 rounded text-muted font-mono">{team.code}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <Link href={`/predict?home=${encodeURIComponent(team.name)}`}>
            <Button variant="outline" size="sm">Predict match</Button>
          </Link>
        </div>
      </motion.header>

      <DataFreshnessStrip compact />

      {/* Core stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Elo rating" value={Math.round(team.elo)} accent />
          <Stat label="FIFA rank" value={`#${team.fifa_rank}`} />
        {wc2026Detail ? (
          <>
            <Stat label="Form (ppg)" value={wc2026Detail.form_ppg.toFixed(2)} sub="points per game" />
            <Stat label="Squad size" value={wc2026Detail.squad_size} sub={`${wc2026Detail.injured_count} injured`} />
          </>
        ) : (
          <>
            <Stat label="Confederation" value={team.confederation} />
            <Stat label="Code" value={team.code} />
          </>
        )}
      </div>

      {/* WC2026 detail rows */}
      {wc2026Detail && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Attack" value={wc2026Detail.attack.toFixed(3)} accent />
          <Stat label="Defence" value={wc2026Detail.defence.toFixed(3)} />
          <Stat label="Chemistry" value={`${(wc2026Detail.chemistry * 100).toFixed(0)}%`} />
          <Stat
            label="Coach"
            value={squadData?.coach ?? wc2026Detail.coach.name ?? "Unknown"}
            sub={coachSub}
          />
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        {/* Elo trend */}
        <Card>
          <CardHeader><span className="kicker">Elo trend</span></CardHeader>
          <CardBody>
            <EloTrend history={trend} />
          </CardBody>
        </Card>

        {/* Radar chart — if WC2026 detail available */}
        {wc2026Detail ? (
          <Card>
            <CardHeader><span className="kicker">Team strength radar</span></CardHeader>
            <CardBody>
              <TeamRadar detail={wc2026Detail} />
            </CardBody>
          </Card>
        ) : (
          <Card>
            <CardBody className="flex items-center justify-center py-12 text-center">
              <div>
                <div className="text-3xl mb-2">🌐</div>
                <p className="text-muted text-sm max-w-xs">
                  Strength radar available for WC 2026 qualified teams with squad data loaded.
                </p>
              </div>
            </CardBody>
          </Card>
        )}
      </div>

      {/* RAG analyst box */}
      <section>
        <h2 className="kicker mb-3">Ask About This Team</h2>
        <AskAnalystBox
          contextType="team"
          teamId={team.id}
          placeholder={`Ask about ${team.name}'s squad, stats, or coach...`}
        />
      </section>

      {/* Squad table */}
      <Card>
        <CardHeader className="flex items-baseline justify-between">
          <span className="kicker">Squad</span>
          {squadData && (
            <span className="text-xs text-muted">{squadData.squad.length} players</span>
          )}
        </CardHeader>
        <CardBody>
          {squadLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : squadError ? (
            <p className="text-signal text-sm text-center py-6">
              Squad data could not be loaded for this team.
            </p>
          ) : (
            <>
              {(squadData?.squad_count ?? squadData?.squad.length ?? 0) > 0
                && (squadData?.squad_count ?? squadData?.squad.length ?? 0) < 20 && (
                <div className="mb-3 flex items-start gap-2 rounded-md border border-[hsl(45_95%_58%/0.5)] bg-[hsl(45_95%_58%/0.07)] px-3 py-2 text-[11px] text-[hsl(45_95%_58%)]">
                  <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <p>Squad data incomplete — check ingestion status.</p>
                </div>
              )}
              <SquadBrief players={squadData?.squad ?? []} teamName={team.name} />
            </>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
