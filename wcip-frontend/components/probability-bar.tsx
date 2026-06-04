"use client";

import { motion } from "framer-motion";
import type { MatchProbabilities } from "@/lib/types";
import { pct } from "@/lib/utils";

interface Props {
  home: string;
  away: string;
  probabilities: MatchProbabilities;
}

export function ProbabilityBar({ home, away, probabilities }: Props) {
  const segments = [
    { key: "home", label: home, value: probabilities.home_win, color: "hsl(var(--pitch))", text: "text-pitch" },
    { key: "draw", label: "Draw", value: probabilities.draw, color: "hsl(var(--sky))", text: "text-sky" },
    { key: "away", label: away, value: probabilities.away_win, color: "hsl(var(--signal))", text: "text-signal" },
  ];

  return (
    <div>
      <div className="flex h-12 w-full overflow-hidden rounded-md border border-line">
        {segments.map((s, i) => (
          <motion.div
            key={s.key}
            initial={{ width: 0 }}
            animate={{ width: `${s.value * 100}%` }}
            transition={{ duration: 0.7, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
            className="flex items-center justify-center"
            style={{ backgroundColor: s.color }}
          >
            {s.value > 0.08 && (
              <span className="tnum text-sm font-semibold text-ink">{pct(s.value, 0)}</span>
            )}
          </motion.div>
        ))}
      </div>
      <div className="mt-2 flex justify-between text-xs">
        {segments.map((s) => (
          <div key={s.key} className="flex flex-col">
            <span className={`uppercase tracking-wide ${s.text}`}>{s.label}</span>
            <span className="tnum text-muted">{pct(s.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
