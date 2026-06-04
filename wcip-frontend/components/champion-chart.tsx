"use client";

import {
  Bar, BarChart, Cell, ErrorBar, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { TeamProbability } from "@/lib/types";
import { pct, teamColor } from "@/lib/utils";

interface Props {
  teams: TeamProbability[];
  limit?: number;
}

export function ChampionChart({ teams, limit = 10 }: Props) {
  const data = teams.slice(0, limit).map((t) => ({
    team: t.team,
    champion: +(t.champion * 100).toFixed(2),
    // ErrorBar expects [lowOffset, highOffset] from the value.
    err: [
      +((t.champion - t.champion_ci_low) * 100).toFixed(2),
      +((t.champion_ci_high - t.champion) * 100).toFixed(2),
    ],
  }));

  return (
    <ResponsiveContainer width="100%" height={Math.max(240, data.length * 34)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
        <XAxis
          type="number" tickFormatter={(v) => `${v}%`}
          stroke="hsl(var(--muted))" fontSize={11}
          tick={{ fill: "hsl(var(--muted))" }}
        />
        <YAxis
          type="category" dataKey="team" width={92}
          stroke="hsl(var(--muted))" fontSize={12}
          tick={{ fill: "hsl(var(--fg))" }}
        />
        <Tooltip
          cursor={{ fill: "hsl(var(--elevated))" }}
          contentStyle={{
            background: "hsl(var(--surface))", border: "1px solid hsl(var(--line))",
            borderRadius: 8, fontSize: 12,
          }}
          labelStyle={{ color: "hsl(var(--fg))" }}
          formatter={(v: number) => [`${v}%`, "Champion"]}
        />
        <Bar dataKey="champion" radius={[0, 3, 3, 0]} isAnimationActive>
          {data.map((_, i) => (
            <Cell key={i} fill={teamColor(i)} />
          ))}
          <ErrorBar dataKey="err" stroke="hsl(var(--fg) / 0.5)" strokeWidth={1.5} width={4} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function ChampionLegend() {
  return (
    <p className="text-xs text-muted mt-2">
      Bars show champion probability; whiskers are the 95% confidence interval
      across simulations.
    </p>
  );
}

export { pct };
