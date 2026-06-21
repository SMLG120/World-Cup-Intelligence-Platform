"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  useSimulations, useDeleteSimulation, useDuplicateSimulation, useUpdateSimulation,
  useCompareSavedSimulations,
} from "@/lib/queries";
import { useAuth } from "@/lib/auth-context";
import { RequireAuth } from "@/components/require-auth";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ChampionChart } from "@/components/champion-chart";
import type { Simulation } from "@/lib/types";
import { pct } from "@/lib/utils";

interface CompareResult {
  champion_deltas?: Array<{
    simulation_id: number;
    name: string;
    deltas: Array<{ team: string; delta: number }>;
  }>;
}

const STATUS_COLOR: Record<string, string> = {
  completed: "text-pitch border-pitch/40",
  pending: "text-sky border-sky/40",
  running: "text-sky border-sky/40",
  failed: "text-signal border-signal/40",
};

function stableDate(value: string) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toISOString().slice(0, 10);
}

function SimRow({
  sim,
  selected,
  onToggleSelected,
}: {
  sim: Simulation;
  selected: boolean;
  onToggleSelected: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(sim.name);
  const [editing, setEditing] = useState(false);
  const [shareUrl, setShareUrl] = useState("");
  const del = useDeleteSimulation();
  const dup = useDuplicateSimulation();
  const upd = useUpdateSimulation();

  const champ = sim.result?.teams?.[0];

  useEffect(() => {
    setShareUrl(`${window.location.origin}/share/${sim.public_token}`);
  }, [sim.public_token]);

  return (
    <Card>
      <CardBody>
        <div className="flex flex-wrap items-center gap-3">
          {editing ? (
            <input
              autoFocus value={name} onChange={(e) => setName(e.target.value)}
              onBlur={() => { setEditing(false); if (name !== sim.name) upd.mutate({ id: sim.id, body: { name } }); }}
              onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
              className="bg-ink/60 border border-line rounded-md px-2 h-8 text-sm font-medium"
            />
          ) : (
            <button onClick={() => setEditing(true)} className="font-medium hover:text-pitch text-left">
              {sim.name}
            </button>
          )}
          <span className={`inline-flex items-center rounded px-2 py-0.5 text-[0.65rem] uppercase tracking-wider border ${STATUS_COLOR[sim.status] ?? "text-muted border-line"}`}>
            {sim.status}
          </span>
          {sim.is_public && <Badge className="text-sky border-sky/40">public</Badge>}
          <span className="tnum text-xs text-muted ml-auto">
            {stableDate(sim.created_at)}
          </span>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <label className="inline-flex items-center gap-1.5 text-muted">
            <input
              type="checkbox"
              checked={selected}
              onChange={onToggleSelected}
              className="accent-[hsl(var(--pitch))]"
            />
            Compare
          </label>
          {champ && (
            <span className="text-muted">
              Favourite: <span className="text-pitch">{champ.team}</span>{" "}
              <span className="tnum">{pct(champ.champion)}</span>
            </span>
          )}
          <span className="tnum text-muted">
            {(sim.params?.runs as number)?.toLocaleString?.() ?? "—"} runs
          </span>
          <div className="ml-auto flex gap-2">
            {sim.result && (
              <Button size="sm" variant="ghost" onClick={() => setOpen((o) => !o)}>
                {open ? "Hide" : "View"}
              </Button>
            )}
            <Button size="sm" variant="ghost"
              onClick={() => upd.mutate({ id: sim.id, body: { is_public: !sim.is_public } })}>
              {sim.is_public ? "Make private" : "Share"}
            </Button>
            {sim.is_public && (
              <Button size="sm" variant="ghost" onClick={() => navigator.clipboard?.writeText(shareUrl)}>
                Copy link
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={() => dup.mutate(sim.id)}>Save as New</Button>
            <Button size="sm" variant="danger" onClick={() => del.mutate(sim.id)}>Delete</Button>
          </div>
        </div>

        <AnimatePresence>
          {open && sim.result && (
            <motion.div
              initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }} className="overflow-hidden mt-4 pt-4 border-t border-line"
            >
              <ChampionChart teams={sim.result.teams} limit={8} />
            </motion.div>
          )}
        </AnimatePresence>
      </CardBody>
    </Card>
  );
}

function SavedInner() {
  const { user } = useAuth();
  const { data, isLoading, isError, error, refetch } = useSimulations(1, Boolean(user));
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const compare = useCompareSavedSimulations();
  const comparison = compare.data as CompareResult | undefined;

  function toggleSelected(id: number) {
    setSelectedIds((ids) => (
      ids.includes(id) ? ids.filter((value) => value !== id) : [...ids, id]
    ));
  }

  function runCompare() {
    const [baseId, ...rest] = selectedIds;
    if (!baseId || rest.length === 0) return;
    compare.mutate({ id: baseId, simulationIds: rest });
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="kicker mb-2">Library</p>
          <h1 className="display text-4xl">Saved simulations</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={runCompare}
            disabled={selectedIds.length < 2 || compare.isPending}
            variant="outline"
          >
            {compare.isPending ? "Comparing…" : "Compare Simulations"}
          </Button>
          <Link href="/wc2026/bracket"><Button>New simulation</Button></Link>
        </div>
      </header>

      {compare.isError && (
        <Card><CardBody className="text-sm text-signal">
          {(compare.error as Error).message}
        </CardBody></Card>
      )}

      {comparison?.champion_deltas?.length ? (
        <Card>
          <CardBody className="space-y-3">
            <p className="kicker">Comparison output</p>
            {comparison.champion_deltas.map((row) => {
              const deltas = [...row.deltas]
                .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
                .slice(0, 6);
              return (
                <div key={row.simulation_id} className="space-y-1">
                  <div className="text-sm font-medium">{row.name}</div>
                  <div className="grid gap-1 sm:grid-cols-2 lg:grid-cols-3">
                    {deltas.map((delta) => (
                      <div key={delta.team} className="flex justify-between text-xs border border-line rounded-md px-2 py-1">
                        <span className="text-muted">{delta.team}</span>
                        <span className={delta.delta >= 0 ? "text-pitch tnum" : "text-signal tnum"}>
                          {delta.delta > 0 ? "+" : ""}{pct(delta.delta)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </CardBody>
        </Card>
      ) : null}

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28" />)}</div>
      ) : isError ? (
        <Card>
          <CardBody className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span className="text-signal">
              {(error as Error)?.message || "Saved simulations could not be loaded."}
            </span>
            <Button variant="outline" size="sm" onClick={() => void refetch()}>
              Retry
            </Button>
          </CardBody>
        </Card>
      ) : !data || data.items.length === 0 ? (
        <Card><CardBody className="py-16 text-center text-muted text-sm">
          No saved simulations yet.{" "}
          <Link href="/wc2026/bracket" className="text-pitch hover:underline">Run one</Link> to get started.
        </CardBody></Card>
      ) : (
        <div className="space-y-3">
          {data.items.map((sim) => (
            <SimRow
              key={sim.id}
              sim={sim}
              selected={selectedIds.includes(sim.id)}
              onToggleSelected={() => toggleSelected(sim.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function SavedPage() {
  return <RequireAuth><SavedInner /></RequireAuth>;
}
