"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { useSimulations } from "@/lib/queries";
import { RequireAuth } from "@/components/require-auth";
import { Card, CardBody } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Simulation } from "@/lib/types";
import { pct } from "@/lib/utils";

const DOT: Record<string, string> = {
  completed: "bg-pitch", failed: "bg-signal", pending: "bg-sky", running: "bg-sky",
};

function HistoryInner() {
  const { data, isLoading } = useSimulations(1);
  const items: Simulation[] = data?.items ?? [];

  return (
    <div className="space-y-6">
      <header>
        <p className="kicker mb-2">Activity</p>
        <h1 className="display text-4xl">History</h1>
        <p className="text-muted mt-2 text-sm max-w-2xl">
          A timeline of your simulation runs, most recent first.
        </p>
      </header>

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
      ) : items.length === 0 ? (
        <Card><CardBody className="py-16 text-center text-muted text-sm">
          No activity yet. <Link href="/tournament" className="text-pitch hover:underline">Run a simulation</Link>.
        </CardBody></Card>
      ) : (
        <div className="relative pl-6">
          <div className="absolute left-[7px] top-1 bottom-1 w-px bg-line" />
          <div className="space-y-5">
            {items.map((sim, i) => {
              const champ = sim.result?.teams?.[0];
              return (
                <motion.div
                  key={sim.id}
                  initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className="relative"
                >
                  <span className={`absolute -left-[22px] top-1.5 h-3.5 w-3.5 rounded-full border-2 border-ink ${DOT[sim.status] ?? "bg-muted"}`} />
                  <Link href="/saved" className="block group">
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <span className="font-medium group-hover:text-pitch">{sim.name}</span>
                      <span className="text-xs uppercase tracking-wide text-muted">{sim.status}</span>
                      <span className="tnum text-xs text-muted ml-auto">
                        {new Date(sim.created_at).toLocaleString()}
                      </span>
                    </div>
                    <p className="text-xs text-muted mt-0.5">
                      {sim.kind} · {(sim.params?.runs as number)?.toLocaleString?.() ?? "—"} runs
                      {champ && <> · favourite <span className="text-pitch">{champ.team}</span> {pct(champ.champion)}</>}
                    </p>
                  </Link>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default function HistoryPage() {
  return <RequireAuth><HistoryInner /></RequireAuth>;
}
