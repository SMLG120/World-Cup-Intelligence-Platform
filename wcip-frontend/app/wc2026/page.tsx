"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { QualifiedTeam, WC2026Groups, WC2026Simulation } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { WinnerPredictionsSection } from "@/components/winner-predictions-section";
import { SaveSimulationButton } from "@/components/save-simulation-button";

const CONFEDERATION_COLORS: Record<string, string> = {
  UEFA: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  CONMEBOL: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30",
  CAF: "bg-green-500/20 text-green-300 border-green-500/30",
  AFC: "bg-red-500/20 text-red-300 border-red-500/30",
  CONCACAF: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  OFC: "bg-gray-500/20 text-gray-300 border-gray-500/30",
};

function TeamCard({ team }: { team: QualifiedTeam }) {
  return (
    <div className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-white/5 transition-colors">
      <div className="flex items-center gap-2">
        <span className="text-xs font-mono text-gray-400 w-8">{team.team_code}</span>
        <span className="text-sm text-white">{team.team_name}</span>
        {team.host_nation && (
          <span className="text-xs bg-amber-500/20 text-amber-300 border border-amber-500/30 px-1 py-0.5 rounded">Host</span>
        )}
      </div>
      <span className={`text-xs px-1.5 py-0.5 rounded border ${CONFEDERATION_COLORS[team.confederation] || "bg-gray-500/20 text-gray-300"}`}>
        {team.confederation}
      </span>
    </div>
  );
}

function GroupCard({ label, teams }: { label: string; teams: string[] }) {
  return (
    <div className="bg-white/5 border border-white/10 rounded-xl p-4">
      <div className="text-lg font-bold text-white mb-3">Group {label}</div>
      {teams.map((team) => (
        <div key={team} className="text-sm text-gray-300 py-1 border-b border-white/5 last:border-0">
          {team}
        </div>
      ))}
    </div>
  );
}

export default function WC2026Page() {
  const [teams, setTeams] = useState<QualifiedTeam[]>([]);
  const [groups, setGroups] = useState<WC2026Groups | null>(null);
  const [simulation, setSimulation] = useState<WC2026Simulation | null>(null);
  const [loading, setLoading] = useState(true);
  const [simRunning, setSimRunning] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);
  const [simRuns, setSimRuns] = useState("10000");
  const [tab, setTab] = useState<"teams" | "groups" | "simulation">("teams");
  const [confFilter, setConfFilter] = useState("all");

  useEffect(() => {
    Promise.all([api.wc2026Teams(), api.wc2026Groups()])
      .then(([t, g]) => { setTeams(t); setGroups(g); })
      .finally(() => setLoading(false));
  }, []);

  const filteredTeams = confFilter === "all"
    ? teams
    : teams.filter((t) => t.confederation === confFilter);

  const confederations = Array.from(new Set(teams.map((t) => t.confederation))).sort();

  async function runSimulation() {
    setSimRunning(true);
    setSimError(null);
    try {
      const result = await api.wc2026Simulate(parseInt(simRuns), undefined, {
        seed: null,
        deterministic: false,
      });
      setSimulation(result);
      setTab("simulation");
    } catch (err) {
      setSimError(err instanceof Error ? err.message : "Simulation failed.");
    } finally {
      setSimRunning(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 text-white p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-4xl">🏆</span>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-amber-400 to-yellow-300 bg-clip-text text-transparent">
              FIFA World Cup 2026
            </h1>
          </div>
          <p className="text-gray-400">
            June 11 – July 19, 2026 · United States, Canada & Mexico · 48 teams · 104 matches
          </p>
          {groups && (
            <div className="flex gap-4 mt-3 text-sm">
              <span className="text-gray-400">
                <span className="text-white font-semibold">{groups.qualification_status.confirmed}</span>
                /{groups.qualification_status.total_slots} teams qualified
              </span>
              <span className={groups.draw_complete ? "text-green-400" : "text-amber-400"}>
                {groups.draw_complete ? "✓ Group draw complete" : "⏳ Draw pending"}
              </span>
            </div>
          )}
        </div>

        <div className="mb-8">
          <WinnerPredictionsSection />
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-white/5 p-1 rounded-xl w-fit">
          {(["teams", "groups", "simulation"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all capitalize ${
                tab === t ? "bg-amber-500 text-black" : "text-gray-400 hover:text-white"
              }`}
            >
              {t === "teams" ? `Teams (${teams.length})` : t === "groups" ? "Groups" : "Simulation"}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-40 bg-white/5" />
            ))}
          </div>
        ) : tab === "teams" ? (
          <div>
            {/* Confederation filter */}
            <div className="flex gap-2 mb-4 flex-wrap">
              <button
                onClick={() => setConfFilter("all")}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                  confFilter === "all" ? "bg-white text-black border-white" : "border-white/20 text-gray-400 hover:border-white/40"
                }`}
              >
                All ({teams.length})
              </button>
              {confederations.map((conf) => (
                <button
                  key={conf}
                  onClick={() => setConfFilter(conf)}
                  className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                    confFilter === conf
                      ? "bg-white text-black border-white"
                      : "border-white/20 text-gray-400 hover:border-white/40"
                  }`}
                >
                  {conf} ({teams.filter((t) => t.confederation === conf).length})
                </button>
              ))}
            </div>

            <Card className="bg-white/5 border-white/10">
              <CardContent className="p-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-1">
                  {filteredTeams.map((team) => (
                    <TeamCard key={team.team_name} team={team} />
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        ) : tab === "groups" ? (
          groups?.draw_complete ? (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {Object.entries(groups.groups).map(([label, groupTeams]) => (
                <GroupCard key={label} label={label} teams={groupTeams} />
              ))}
            </div>
          ) : (
            <div className="text-center py-20">
              <div className="text-5xl mb-4">🎲</div>
              <h2 className="text-xl font-semibold text-white mb-2">Group Draw Pending</h2>
              <p className="text-gray-400 max-w-md mx-auto">
                The official FIFA group draw hasn&#39;t taken place yet. Once the draw is held, groups will
                appear here automatically when the ETL pipeline updates.
              </p>
              <div className="mt-6 text-sm text-gray-500">
                In the meantime, use the Simulation tab to run predictions using provisional groups.
              </div>
            </div>
          )
        ) : (
          <div>
            <div className="flex items-center gap-4 mb-6">
              <Select
                value={simRuns}
                onChange={(e) => setSimRuns(e.target.value)}
                className="w-40"
              >
                {[["1000", "1K runs"], ["5000", "5K runs"], ["10000", "10K runs"],
                  ["50000", "50K runs"]].map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </Select>
              <Button onClick={runSimulation} disabled={simRunning}
                className="bg-amber-500 hover:bg-amber-400 text-black font-semibold">
                {simRunning ? "Simulating…" : "Run Tournament Simulation"}
              </Button>
            </div>
            {simError && (
              <div className="mb-4 text-sm text-red-300 border border-red-500/30 bg-red-500/10 rounded-lg px-3 py-2">
                {simError}
              </div>
            )}

            {simulation ? (
              <div>
                <div className="flex flex-wrap items-center gap-3 text-sm text-gray-400 mb-4">
                  <span>
                    {simulation.runs.toLocaleString()} simulations ·{" "}
                    {simulation.draw_complete ? "Official groups" : "Provisional groups (draw pending)"}
                  </span>
                  {simulation.seed !== undefined && simulation.seed !== null && (
                    <span>Seed <span className="text-white font-mono">{simulation.seed}</span></span>
                  )}
                  <div className="flex gap-2 sm:ml-auto">
                    <SaveSimulationButton
                      defaultName={`WC 2026 simulation (${simulation.runs.toLocaleString()} runs)`}
                      simulationType="wc2026"
                      edition="2026"
                      runs={simulation.runs}
                      seed={simulation.seed}
                      deterministic={simulation.deterministic}
                      tournamentResult={simulation}
                      championProbabilities={simulation.teams}
                    />
                    <Link href="/saved">
                      <Button variant="ghost" size="sm">View Saved Simulations</Button>
                    </Link>
                  </div>
                </div>
                <div className="grid grid-cols-1 gap-2">
                  {simulation.teams.slice(0, 20).map((t, i) => (
                    <div key={t.team}
                      className="flex items-center gap-3 bg-white/5 border border-white/10 rounded-lg px-4 py-3 hover:bg-white/8 transition-colors">
                      <span className="text-gray-500 w-6 text-sm font-mono">{i + 1}</span>
                      <span className="text-white font-medium flex-1">{t.team}</span>
                      <div className="flex gap-6 text-sm">
                        <div className="text-center">
                          <div className="text-amber-400 font-bold">{(t.champion * 100).toFixed(1)}%</div>
                          <div className="text-gray-500 text-xs">Champion</div>
                        </div>
                        <div className="text-center hidden sm:block">
                          <div className="text-blue-400 font-semibold">{(t.final * 100).toFixed(1)}%</div>
                          <div className="text-gray-500 text-xs">Final</div>
                        </div>
                        <div className="text-center hidden md:block">
                          <div className="text-purple-400 font-semibold">{(t.semi * 100).toFixed(1)}%</div>
                          <div className="text-gray-500 text-xs">Semi</div>
                        </div>
                      </div>
                      <div className="w-24 h-1.5 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-amber-500 rounded-full"
                          style={{ width: `${Math.min(100, t.champion * 100 * 5)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-center py-20 text-gray-500">
                Run a simulation to see World Cup 2026 championship probabilities
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
