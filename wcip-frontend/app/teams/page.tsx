"use client";

import { useState, useMemo } from "react";
import { useTeams } from "@/lib/queries";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { DataFreshnessStrip } from "@/components/data-freshness";

type SortKey = "elo" | "fifa_rank" | "name";

export default function TeamsPage() {
  const { data: teams, isLoading } = useTeams();
  const [sort, setSort] = useState<SortKey>("elo");

  const sorted = useMemo(() => {
    if (!teams) return [];
    const arr = [...teams];
    if (sort === "elo") arr.sort((a, b) => b.elo - a.elo);
    else if (sort === "fifa_rank") arr.sort((a, b) => a.fifa_rank - b.fifa_rank);
    else arr.sort((a, b) => a.name.localeCompare(b.name));
    return arr;
  }, [teams, sort]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker mb-2">Nations</p>
          <h1 className="display text-4xl">Teams</h1>
        </div>
        <div>
          <span className="kicker block mb-1.5">Sort by</span>
          <Select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} className="w-44">
            <option value="elo">Elo rating</option>
            <option value="fifa_rank">FIFA rank</option>
            <option value="name">Name</option>
          </Select>
        </div>
      </header>

      <DataFreshnessStrip compact />

      <Card>
        <CardHeader><span className="kicker">All 48 nations</span></CardHeader>
        <CardBody>
          {isLoading ? (
            <div className="space-y-2">{Array.from({ length: 10 }).map((_, i) => <Skeleton key={i} className="h-11" />)}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="kicker text-left border-b border-line">
                    <th className="pb-2 font-normal w-8">#</th>
                    <th className="pb-2 font-normal">Team</th>
                    <th className="pb-2 font-normal">Confederation</th>
                    <th className="pb-2 font-normal text-right">FIFA</th>
                    <th className="pb-2 font-normal text-right">Elo</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((t, i) => (
                    <tr key={t.id} className="border-b border-line/50 hover:bg-elevated/40 transition-colors">
                      <td className="py-2 tnum text-muted">{i + 1}</td>
                      <td className="py-2">
                        <span className="font-medium">{t.name}</span>
                        <span className="ml-2 text-muted text-xs tnum">{t.code}</span>
                      </td>
                      <td className="py-2"><Badge>{t.confederation}</Badge></td>
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
