"use client";

// Lazy-loaded from /predict (next/dynamic) so recharts is not part of the
// page's initial JavaScript; the chart only renders after a prediction.
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts";
import { MODEL_LABELS } from "@/lib/model-labels";

export default function ModelComparisonChart({
  home,
  away,
  statistical,
  ml,
  ensemble,
}: {
  home: string;
  away: string;
  statistical: { home_win: number; draw: number; away_win: number };
  ml: Record<string, { home_win: number; draw: number; away_win: number }>;
  ensemble: { home_win: number; draw: number; away_win: number };
}) {
  const data = [
    { model: "Statistical", home_win: statistical.home_win * 100, draw: statistical.draw * 100, away_win: statistical.away_win * 100 },
    ...Object.entries(ml).map(([k, v]) => ({
      model: MODEL_LABELS[k] ?? k,
      home_win: v.home_win * 100,
      draw: v.draw * 100,
      away_win: v.away_win * 100,
    })),
    { model: "Ensemble", home_win: ensemble.home_win * 100, draw: ensemble.draw * 100, away_win: ensemble.away_win * 100 },
  ];

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" vertical={false} />
        <XAxis dataKey="model" stroke="hsl(var(--muted))" fontSize={10} tick={{ fill: "hsl(var(--muted))" }} />
        <YAxis tickFormatter={(v: number) => `${v}%`} stroke="hsl(var(--muted))" fontSize={10} domain={[0, 100]} />
        <Tooltip
          formatter={(v: number, name: string) => [
            `${v.toFixed(1)}%`,
            name === "home_win" ? home : name === "away_win" ? away : "Draw",
          ]}
          contentStyle={{
            background: "hsl(var(--elevated))", border: "1px solid hsl(var(--line))",
            borderRadius: 8, fontSize: 11,
          }}
          labelStyle={{ color: "hsl(var(--fg))", fontWeight: "bold" }}
        />
        <Bar dataKey="home_win" stackId="a" fill="hsl(var(--pitch))" name="home_win" />
        <Bar dataKey="draw" stackId="a" fill="hsl(var(--line))" name="draw" />
        <Bar dataKey="away_win" stackId="a" fill="hsl(var(--signal))" name="away_win" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
