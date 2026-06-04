"use client";

import { motion } from "framer-motion";
import type { TeamProbability } from "@/lib/types";
import { pct } from "@/lib/utils";

// A probability-driven "funnel" bracket: each column is a knockout round and
// shows the teams most likely to reach it, narrowing to the projected champion.
// (A fixture-by-fixture bracket needs a single tournament draw; this view
// summarises the full Monte Carlo distribution, which is more informative.)

interface Props {
  teams: TeamProbability[];
}

const ROUNDS: { key: keyof TeamProbability; label: string; take: number }[] = [
  { key: "round_of_16", label: "Round of 16", take: 16 },
  { key: "quarter", label: "Quarter-finals", take: 8 },
  { key: "semi", label: "Semi-finals", take: 4 },
  { key: "final", label: "Final", take: 2 },
  { key: "champion", label: "Champion", take: 1 },
];

export function Bracket({ teams }: Props) {
  return (
    <div className="overflow-x-auto pb-2">
      <div className="flex gap-4 min-w-[760px]">
        {ROUNDS.map((round, ri) => {
          const ranked = [...teams]
            .sort((a, b) => (b[round.key] as number) - (a[round.key] as number))
            .slice(0, round.take);
          return (
            <div key={round.key} className="flex-1 min-w-[140px]">
              <div className="kicker mb-2 text-center">{round.label}</div>
              <div className="space-y-1.5 flex flex-col justify-center h-full">
                {ranked.map((t, i) => {
                  const value = t[round.key] as number;
                  const champ = round.key === "champion";
                  return (
                    <motion.div
                      key={t.team}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: ri * 0.06 + i * 0.015 }}
                      className={`relative rounded-md border px-2.5 py-1.5 overflow-hidden ${
                        champ ? "border-pitch bg-pitch/10" : "border-line bg-surface"
                      }`}
                    >
                      <div
                        className="absolute inset-y-0 left-0 bg-pitch/15"
                        style={{ width: `${value * 100}%` }}
                      />
                      <div className="relative flex justify-between items-center gap-2">
                        <span className={`text-xs truncate ${champ ? "text-pitch font-semibold" : "text-fg"}`}>
                          {t.team}
                        </span>
                        <span className="tnum text-[0.65rem] text-muted shrink-0">{pct(value, 0)}</span>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
