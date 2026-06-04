"use client";

import { useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  useSimulations, useDeleteSimulation, useDuplicateSimulation, useUpdateSimulation,
} from "@/lib/queries";
import { RequireAuth } from "@/components/require-auth";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ChampionChart } from "@/components/champion-chart";
import type { Simulation } from "@/lib/types";
import { pct } from "@/lib/utils";

const STATUS_COLOR: Record<string, string> = {
  completed: "text-pitch border-pitch/40",
  pending: "text-sky border-sky/40",
  running: "text-sky border-sky/40",
  failed: "text-signal border-signal/40",
};

function SimRow({ sim }: { sim: Simulation }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(sim.name);
  const [editing, setEditing] = useState(false);
  const del = useDeleteSimulation();
  const dup = useDuplicateSimulation();
  const upd = useUpdateSimulation();

  const champ = sim.result?.teams?.[0];
  const shareUrl = typeof window !== "undefined"
    ? `${window.location.origin}/share/${sim.public_token}` : "";

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
            {new Date(sim.created_at).toLocaleDateString()}
          </span>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
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
            <Button size="sm" variant="ghost" onClick={() => dup.mutate(sim.id)}>Duplicate</Button>
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
  const { data, isLoading } = useSimulations();

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between">
        <div>
          <p className="kicker mb-2">Library</p>
          <h1 className="display text-4xl">Saved simulations</h1>
        </div>
        <Link href="/tournament"><Button>New simulation</Button></Link>
      </header>

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28" />)}</div>
      ) : !data || data.items.length === 0 ? (
        <Card><CardBody className="py-16 text-center text-muted text-sm">
          No saved simulations yet.{" "}
          <Link href="/tournament" className="text-pitch hover:underline">Run one</Link> to get started.
        </CardBody></Card>
      ) : (
        <div className="space-y-3">
          {data.items.map((sim) => <SimRow key={sim.id} sim={sim} />)}
        </div>
      )}
    </div>
  );
}

export default function SavedPage() {
  return <RequireAuth><SavedInner /></RequireAuth>;
}
