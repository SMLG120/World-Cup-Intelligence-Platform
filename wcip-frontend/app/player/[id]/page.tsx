"use client";

import { use } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid, Cell,
} from "recharts";
import { useWC2026Players } from "@/lib/queries";
import type { Player } from "@/lib/types";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

// ── Stat box ──────────────────────────────────────────────────────────────────

function Stat({
  label, value, sub, accent,
}: {
  label: string; value: string | number; sub?: string; accent?: boolean;
}) {
  return (
    <div className="rounded-lg border border-line p-4 bg-surface/60">
      <div className="kicker">{label}</div>
      <div className={`tnum text-2xl mt-1 ${accent ? "text-pitch" : "text-fg"}`}>{value}</div>
      {sub && <div className="text-xs text-muted mt-0.5">{sub}</div>}
    </div>
  );
}

// ── Performance radar ─────────────────────────────────────────────────────────

function PerformanceRadar({ player }: { player: Player }) {
  const normalize = (v: number, max: number) => Math.min(100, (v / max) * 100);

  const data = [
    { subject: "Goals", value: normalize(player.goals, 20), raw: player.goals },
    { subject: "Assists", value: normalize(player.assists, 15), raw: player.assists },
    { subject: "xG", value: normalize(player.xg, 20), raw: player.xg.toFixed(1) },
    { subject: "xA", value: normalize(player.xag, 15), raw: player.xag.toFixed(1) },
    { subject: "Fitness", value: player.fitness_score * 100, raw: `${(player.fitness_score * 100).toFixed(0)}%` },
    { subject: "Caps", value: normalize(player.international_caps, 100), raw: player.international_caps },
  ];

  return (
    <ResponsiveContainer width="100%" height={280}>
      <RadarChart data={data} margin={{ top: 12, right: 20, bottom: 12, left: 20 }}>
        <PolarGrid stroke="hsl(var(--line))" />
        <PolarAngleAxis
          dataKey="subject"
          tick={{ fill: "hsl(var(--muted))", fontSize: 11 }}
        />
        <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} axisLine={false} />
        <Radar
          name="Player"
          dataKey="value"
          stroke="hsl(var(--pitch))"
          fill="hsl(var(--pitch))"
          fillOpacity={0.25}
          strokeWidth={2}
        />
        <Tooltip
          formatter={(v: number) => [v.toFixed(1), "Score"]}
          contentStyle={{
            background: "hsl(var(--elevated))", border: "1px solid hsl(var(--line))",
            borderRadius: 8, fontSize: 11,
          }}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}

// ── Stat bars ─────────────────────────────────────────────────────────────────

function StatBar({ label, value, max, colour = "hsl(var(--pitch))" }: {
  label: string; value: number; max: number; colour?: string;
}) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted">{label}</span>
        <span className="tnum text-fg">{typeof value === "number" && Number.isInteger(value) ? value : value.toFixed(2)}</span>
      </div>
      <div className="h-1.5 bg-elevated rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{ background: colour }}
        />
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PlayerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const searchParams = useSearchParams();
  const teamName = searchParams.get("team") ?? "";

  const { data: squadData, isLoading, isError } = useWC2026Players(teamName, !!teamName);

  const player = squadData?.squad.find((p) => String(p.id) === id) ?? null;

  if (!teamName) {
    return (
      <div className="py-16 text-center">
        <h1 className="display text-2xl mb-2">Team required</h1>
        <p className="text-muted mb-4">Navigate to a player from a team page.</p>
        <Link href="/teams"><Button variant="outline">Browse teams</Button></Link>
      </div>
    );
  }

  if (isLoading) {
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

  if (isError || !squadData) {
    return (
      <div className="py-16 text-center">
        <p className="text-signal mb-4">Failed to load squad data.</p>
        <Link href="/teams"><Button variant="outline">Back to teams</Button></Link>
      </div>
    );
  }

  if (!player) {
    return (
      <div className="py-16 text-center">
        <h1 className="display text-2xl mb-2">Player not found</h1>
        <Link href="/teams"><Button variant="outline">Back to teams</Button></Link>
      </div>
    );
  }

  const positionColour = player.position === "GK" ? "hsl(45 95% 58%)"
    : ["CB", "LB", "RB", "LWB", "RWB"].includes(player.position) ? "hsl(200 90% 62%)"
    : ["CM", "CDM", "CAM", "LM", "RM"].includes(player.position) ? "hsl(280 70% 68%)"
    : "hsl(var(--pitch))";

  return (
    <div className="space-y-8">
      <motion.header
        initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
        className="flex flex-wrap items-end justify-between gap-4"
      >
        <div>
          <Link href={`/teams`} className="kicker hover:text-pitch transition-colors">← Teams / {teamName}</Link>
          <h1 className="display text-5xl mt-2">{player.name}</h1>
          <div className="flex items-center gap-3 mt-2">
            <span
              className="text-xs border px-2 py-0.5 rounded"
              style={{ borderColor: positionColour, color: positionColour }}
            >
              {player.position}
            </span>
            {player.club && (
              <span className="text-xs border border-line px-2 py-0.5 rounded text-muted">{player.club}</span>
            )}
            {player.age && (
              <span className="text-xs text-muted">{player.age} yrs</span>
            )}
            {player.injured && (
              <span className="text-xs bg-signal/20 border border-signal/40 text-signal px-2 py-0.5 rounded">Injured</span>
            )}
            {player.suspended && (
              <span className="text-xs bg-[hsl(45_95%_58%/0.2)] border border-[hsl(45_95%_58%/0.4)] text-[hsl(45_95%_58%)] px-2 py-0.5 rounded">Suspended</span>
            )}
          </div>
        </div>
      </motion.header>

      {/* Core stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Goals" value={player.goals} accent />
        <Stat label="Assists" value={player.assists} />
        <Stat label="xG" value={player.xg.toFixed(2)} sub="expected goals" />
        <Stat label="Fitness" value={`${(player.fitness_score * 100).toFixed(0)}%`} sub={player.injured ? "injured" : "available"} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Int'l caps" value={player.international_caps} />
        <Stat label="Int'l goals" value={player.international_goals} />
        <Stat label="xA" value={player.xag.toFixed(2)} sub="expected assists" />
        <Stat label="Minutes" value={player.minutes_played.toLocaleString()} sub="played" />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* Radar chart */}
        <Card>
          <CardHeader><span className="kicker">Performance radar</span></CardHeader>
          <CardBody>
            <PerformanceRadar player={player} />
          </CardBody>
        </Card>

        {/* Stat bars */}
        <Card>
          <CardHeader><span className="kicker">Attacking output</span></CardHeader>
          <CardBody className="space-y-4">
            <StatBar label="Goals" value={player.goals} max={20} />
            <StatBar label="xG (expected goals)" value={player.xg} max={20} colour="hsl(var(--pitch))" />
            <StatBar label="Assists" value={player.assists} max={15} colour="hsl(200 90% 62%)" />
            <StatBar label="xA (expected assists)" value={player.xag} max={15} colour="hsl(200 90% 62%)" />
            <StatBar label="International goals" value={player.international_goals} max={50} colour="hsl(45 95% 58%)" />
            <StatBar label="International caps" value={player.international_caps} max={150} colour="hsl(45 95% 58%)" />
            <StatBar label="Fitness score" value={player.fitness_score * 100} max={100} colour="hsl(140 70% 50%)" />
          </CardBody>
        </Card>
      </div>

      {/* Market value */}
      {player.market_value_eur !== null && player.market_value_eur > 0 && (
        <Card>
          <CardBody>
            <div className="flex items-center justify-between">
              <span className="kicker">Market value</span>
              <span className="text-lg font-semibold text-pitch tnum">
                {player.market_value_eur >= 1_000_000
                  ? `€${(player.market_value_eur / 1_000_000).toFixed(1)}M`
                  : `€${(player.market_value_eur / 1_000).toFixed(0)}K`}
              </span>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
