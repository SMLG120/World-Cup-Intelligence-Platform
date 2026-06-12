"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { useSimulateTournament } from "@/lib/queries";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ChampionChart, ChampionLegend } from "@/components/champion-chart";
import { Bracket } from "@/components/bracket";
import { WinnerPredictionsSection } from "@/components/winner-predictions-section";
import { pct, ordinal } from "@/lib/utils";

// Sync endpoint caps at 2000 runs; larger runs use the authed async /simulations.
const RUN_OPTIONS = [500, 1000, 2000];

export default function TournamentPage() {
  const mutation = useSimulateTournament();
  const [runs, setRuns] = useState(1000);
  const result = mutation.data;

  const run = () => mutation.mutate({ edition: "2022", runs });

  return (
    <div className="space-y-8">
      <header>
        <p className="kicker mb-2">Monte Carlo</p>
        <h1 className="display text-4xl">Tournament simulation</h1>
        <p className="text-muted mt-2 max-w-2xl">
          Simulate the full 2022 World Cup — group stage through final — many
          times over and aggregate how often each nation reaches each round.
        </p>
      </header>

      <WinnerPredictionsSection compact />

      <Card>
        <CardBody className="flex flex-wrap items-end gap-4">
          <div>
            <span className="kicker block mb-1.5">Simulations</span>
            <div className="flex gap-2">
              {RUN_OPTIONS.map((r) => (
                <button
                  key={r}
                  onClick={() => setRuns(r)}
                  className={`tnum px-3 h-10 rounded-md border text-sm transition-colors ${
                    runs === r ? "border-pitch text-pitch bg-pitch/10" : "border-line text-muted hover:text-fg"
                  }`}
                >
                  {r.toLocaleString()}
                </button>
              ))}
            </div>
          </div>
          <Button onClick={run} disabled={mutation.isPending} size="lg">
            {mutation.isPending ? "Running…" : "Run simulation"}
          </Button>
          <p className="text-xs text-muted basis-full sm:basis-auto sm:ml-auto self-center max-w-xs">
            Runs above 2,000 dispatch to a background worker — sign in and use
            saved simulations for 10k–50k.
          </p>
        </CardBody>
      </Card>

      {mutation.isPending && (
        <div className="grid gap-5 lg:grid-cols-2">
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
        </div>
      )}

      {mutation.isError && (
        <p className="text-signal">{(mutation.error as Error).message}</p>
      )}

      {result && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">
          <div className="grid gap-5 lg:grid-cols-[1.1fr_1fr]">
            <Card>
              <CardHeader className="flex justify-between items-baseline">
                <span className="kicker">Champion probability</span>
                <span className="tnum text-xs text-muted">{result.runs.toLocaleString()} runs</span>
              </CardHeader>
              <CardBody>
                <ChampionChart teams={result.teams} limit={10} />
                <ChampionLegend />
              </CardBody>
            </Card>

            <Card>
              <CardHeader><span className="kicker">Projected finish</span></CardHeader>
              <CardBody className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="kicker text-left border-b border-line">
                      <th className="pb-2 font-normal">Team</th>
                      <th className="pb-2 font-normal text-right">Champ</th>
                      <th className="pb-2 font-normal text-right">Final</th>
                      <th className="pb-2 font-normal text-right">Semi</th>
                      <th className="pb-2 font-normal text-right">E[pos]</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.teams.slice(0, 12).map((t) => (
                      <tr key={t.team} className="border-b border-line/50">
                        <td className="py-1.5">{t.team}</td>
                        <td className="py-1.5 text-right tnum text-pitch">{pct(t.champion)}</td>
                        <td className="py-1.5 text-right tnum text-muted">{pct(t.final)}</td>
                        <td className="py-1.5 text-right tnum text-muted">{pct(t.semi)}</td>
                        <td className="py-1.5 text-right tnum text-muted">{ordinal(t.expected_finish)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader><span className="kicker">Advancement funnel</span></CardHeader>
            <CardBody><Bracket teams={result.teams} /></CardBody>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
