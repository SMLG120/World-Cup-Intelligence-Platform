"use client";

import { use } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useTeam, useEloHistory } from "@/lib/queries";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-md border border-line p-4">
      <div className="kicker">{label}</div>
      <div className={`tnum text-2xl mt-1 ${accent ? "text-pitch" : "text-fg"}`}>{value}</div>
    </div>
  );
}

export default function TeamPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const teamId = Number(id);
  const { data: team, isLoading, isError } = useTeam(teamId);
  const { data: history } = useEloHistory(teamId);

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
    label: p.opponent ?? "seed",
  }));

  return (
    <div className="space-y-8">
      <motion.header
        initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
        className="flex flex-wrap items-end justify-between gap-4"
      >
        <div>
          <Link href="/teams" className="kicker hover:text-pitch">← Teams</Link>
          <h1 className="display text-5xl mt-2">{team.name}</h1>
          <div className="flex items-center gap-2 mt-2">
            <Badge>{team.confederation}</Badge>
            <Badge>{team.code}</Badge>
          </div>
        </div>
        <Link href="/simulate"><Button>Simulate a match</Button></Link>
      </motion.header>

      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Elo rating" value={String(Math.round(team.elo))} accent />
        <Stat label="FIFA rank" value={`#${team.fifa_rank}`} />
        <Stat label="Confederation" value={team.confederation} />
        <Stat label="Code" value={team.code} />
      </div>

      <Card>
        <CardHeader><span className="kicker">Elo trend</span></CardHeader>
        <CardBody>
          {trend.length <= 1 ? (
            <p className="text-sm text-muted py-8 text-center">
              Only the seed rating is stored so far. As real match results are
              ingested, this chart fills in the rating after each game.
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={trend} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                <defs>
                  <linearGradient id="elo" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="hsl(var(--pitch))" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="hsl(var(--pitch))" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="point" stroke="hsl(var(--muted))" fontSize={11} />
                <YAxis domain={["dataMin - 30", "dataMax + 30"]} stroke="hsl(var(--muted))" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--surface))", border: "1px solid hsl(var(--line))",
                    borderRadius: 8, fontSize: 12,
                  }}
                  labelStyle={{ color: "hsl(var(--fg))" }}
                />
                <Area type="monotone" dataKey="rating" stroke="hsl(var(--pitch))"
                  strokeWidth={2} fill="url(#elo)" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
