"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useTeams } from "@/lib/queries";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { DataFreshnessStrip } from "@/components/data-freshness";
import { AskAnalystBox } from "@/components/AskAnalystBox";

type SortKey = "elo" | "fifa_rank" | "group" | "name";

export default function TeamsPage() {
  const { data: teams, isLoading, isError, error, refetch } = useTeams();
  const [sort, setSort] = useState<SortKey>("elo");

  const sorted = useMemo(() => {
    if (!teams) return [];
    const arr = [...teams];
    if (sort === "elo") arr.sort((a, b) => b.elo - a.elo);
    else if (sort === "fifa_rank") arr.sort((a, b) => a.fifa_rank - b.fifa_rank);
    else if (sort === "group") arr.sort((a, b) => (a.group ?? "Z").localeCompare(b.group ?? "Z") || a.name.localeCompare(b.name));
    else arr.sort((a, b) => a.name.localeCompare(b.name));
    return arr;
  }, [teams, sort]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker mb-2">Nations</p>
          <h1 className="display text-4xl">Teams</h1>
          <p className="text-muted mt-2 max-w-2xl">
            Browse the 2026 field with current ranking inputs, group assignment,
            coach coverage, and squad ingestion status.
          </p>
        </div>
        <div>
          <span className="kicker block mb-1.5">Sort by</span>
          <Select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} className="w-44">
            <option value="elo">Elo rating</option>
            <option value="fifa_rank">FIFA rank</option>
            <option value="group">Group</option>
            <option value="name">Name</option>
          </Select>
        </div>
      </header>

      <DataFreshnessStrip compact />

      <AskAnalystBox
        contextType="team"
        placeholder="Ask about any team's Elo, squad, coach, or group..."
      />

      <Card>
        <CardHeader><span className="kicker">All 48 nations</span></CardHeader>
        <CardBody>
          {isLoading ? (
            <div className="space-y-2">{Array.from({ length: 10 }).map((_, i) => <Skeleton key={i} className="h-11" />)}</div>
          ) : isError ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-signal/30 bg-signal/10 px-4 py-4 text-sm">
              <span className="text-signal">
                {(error as Error)?.message || "Teams could not be loaded. Check the backend and try again."}
              </span>
              <Button variant="outline" size="sm" onClick={() => void refetch()}>
                Retry
              </Button>
            </div>
          ) : sorted.length === 0 ? (
            <div className="py-16 text-center text-sm text-muted">
              No teams are loaded yet. Run the backend database seed or WC2026 ETL.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="kicker text-left border-b border-line">
                    <th className="pb-2 font-normal w-8">#</th>
                    <th className="pb-2 font-normal">Team</th>
                    <th className="pb-2 font-normal">Group</th>
                    <th className="pb-2 font-normal">Confederation</th>
                    <th className="pb-2 font-normal">Coach</th>
                    <th className="pb-2 font-normal text-right">Squad</th>
                    <th className="pb-2 font-normal text-right">FIFA</th>
                    <th className="pb-2 font-normal text-right">Elo</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((t, i) => (
                    <tr key={t.id} className="border-b border-line/50 hover:bg-elevated/40 transition-colors">
                      <td className="py-2 tnum text-muted">{i + 1}</td>
                      <td className="py-2">
                        <Link href={`/team/${t.id}`} className="font-medium hover:text-pitch transition-colors">
                          {t.name}
                        </Link>
                        <span className="ml-2 text-muted text-xs tnum">{t.fifa_code ?? t.code}</span>
                      </td>
                      <td className="py-2 text-muted tnum">{t.group ?? t.group_label ?? "TBD"}</td>
                      <td className="py-2"><Badge>{t.confederation}</Badge></td>
                      <td className="py-2 text-muted">{t.coach ?? "Pending"}</td>
                      <td className="py-2 text-right tnum text-muted">{t.squad_count ?? 0}</td>
                      <td className="py-2 text-right tnum text-muted">{t.fifa_rank}</td>
                      <td className="py-2 text-right tnum text-pitch">{Math.round(t.elo)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
