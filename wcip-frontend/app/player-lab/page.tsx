"use client";

import { useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { HybridPrediction, Player } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";

interface TeamOverride {
  form: number;          // 0..3 points per game
  injury_burden: number; // 0..1 fraction injured
  coach_impact: number;  // 0..2 multiplier
}

const DEFAULT_OVERRIDE: TeamOverride = {
  form: 1.5,
  injury_burden: 0.0,
  coach_impact: 1.0,
};

function OverrideSlider({
  label, hint, value, min, max, step, onChange
}: {
  label: string; hint: string; value: number; min: number; max: number; step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="flex justify-between mb-1">
        <label className="text-xs text-gray-300">{label}</label>
        <span className="text-xs font-mono text-white">{value.toFixed(2)}</span>
      </div>
      <Slider
        label=""
        display={value.toFixed(2)}
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full"
      />
      <p className="text-xs text-gray-500 mt-0.5">{hint}</p>
    </div>
  );
}

function PlayerRow({ player, onToggleInjury, onToggleSuspend }: {
  player: Player;
  onToggleInjury: (id: number, val: boolean) => void;
  onToggleSuspend: (id: number, val: boolean) => void;
}) {
  return (
    <tr className="border-b border-white/5 hover:bg-white/3">
      <td className="py-2 pr-3">
        <div className="text-sm text-white">{player.name}</div>
        <div className="text-xs text-gray-500">{player.club || "—"}</div>
      </td>
      <td className="text-xs text-gray-400 pr-3">{player.position}</td>
      <td className="text-xs text-gray-400 pr-3">{player.age || "—"}</td>
      <td className="text-xs text-gray-400 pr-3">{player.goals.toFixed(0)}</td>
      <td className="text-xs text-gray-400 pr-3">{player.xg.toFixed(1)}</td>
      <td className="pr-3">
        <button
          onClick={() => onToggleInjury(player.id, !player.injured)}
          className={`text-xs px-2 py-0.5 rounded border transition-colors ${
            player.injured
              ? "bg-red-500/20 border-red-500/40 text-red-300"
              : "bg-white/5 border-white/10 text-gray-400 hover:bg-white/10"
          }`}
        >
          {player.injured ? "Injured" : "Fit"}
        </button>
      </td>
      <td>
        <button
          onClick={() => onToggleSuspend(player.id, !player.suspended)}
          className={`text-xs px-2 py-0.5 rounded border transition-colors ${
            player.suspended
              ? "bg-amber-500/20 border-amber-500/40 text-amber-300"
              : "bg-white/5 border-white/10 text-gray-400 hover:bg-white/10"
          }`}
        >
          {player.suspended ? "Susp." : "OK"}
        </button>
      </td>
    </tr>
  );
}

export default function PlayerLabPage() {
  const [homeTeam, setHomeTeam] = useState("France");
  const [awayTeam, setAwayTeam] = useState("Brazil");
  const [homePlayers, setHomePlayers] = useState<Player[]>([]);
  const [awayPlayers, setAwayPlayers] = useState<Player[]>([]);
  const [homeOverride, setHomeOverride] = useState<TeamOverride>({ ...DEFAULT_OVERRIDE });
  const [awayOverride, setAwayOverride] = useState<TeamOverride>({ ...DEFAULT_OVERRIDE });
  const [prediction, setPrediction] = useState<HybridPrediction | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingPlayers, setLoadingPlayers] = useState(false);

  const loadPlayers = useCallback(async () => {
    setLoadingPlayers(true);
    try {
      const [h, a] = await Promise.all([
        api.wc2026Players(homeTeam).catch(() => ({ team_name: homeTeam, squad: [] })),
        api.wc2026Players(awayTeam).catch(() => ({ team_name: awayTeam, squad: [] })),
      ]);
      setHomePlayers(h.squad);
      setAwayPlayers(a.squad);
    } finally {
      setLoadingPlayers(false);
    }
  }, [homeTeam, awayTeam]);

  function togglePlayerInjury(players: Player[], id: number, val: boolean): Player[] {
    return players.map((p) => (p.id === id ? { ...p, injured: val } : p));
  }
  function togglePlayerSuspend(players: Player[], id: number, val: boolean): Player[] {
    return players.map((p) => (p.id === id ? { ...p, suspended: val } : p));
  }

  function computeInjuryBurden(players: Player[]): number {
    if (!players.length) return 0;
    return (players.filter((p) => p.injured || p.suspended).length) / players.length;
  }

  async function runPrediction() {
    setLoading(true);
    try {
      const hBurden = computeInjuryBurden(homePlayers);
      const aBurden = computeInjuryBurden(awayPlayers);
      const result = await api.mlPredict({
        home_team: homeTeam,
        away_team: awayTeam,
        home_overrides: {
          form: homeOverride.form,
          injury_burden: hBurden || homeOverride.injury_burden,
          coach_impact: homeOverride.coach_impact,
        },
        away_overrides: {
          form: awayOverride.form,
          injury_burden: aBurden || awayOverride.injury_burden,
          coach_impact: awayOverride.coach_impact,
        },
        include_shap: true,
      });
      setPrediction(result);
    } finally {
      setLoading(false);
    }
  }

  const homeInjured = homePlayers.filter((p) => p.injured || p.suspended).length;
  const awayInjured = awayPlayers.filter((p) => p.injured || p.suspended).length;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 text-white p-6">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent mb-2">
            Player Impact Lab
          </h1>
          <p className="text-gray-400">
            Modify player availability, form, and coaching — see how it changes the prediction
          </p>
        </div>

        {/* Team Setup */}
        <Card className="bg-white/5 border-white/10 mb-6">
          <CardContent className="p-4">
            <div className="flex gap-3 items-end flex-wrap">
              <div className="flex-1 min-w-32">
                <label className="text-xs text-gray-400 mb-1 block">Home Team</label>
                <Input value={homeTeam} onChange={(e) => setHomeTeam(e.target.value)}
                  className="bg-white/10 border-white/20 text-white" placeholder="e.g. France" />
              </div>
              <div className="text-gray-500 pb-2">vs</div>
              <div className="flex-1 min-w-32">
                <label className="text-xs text-gray-400 mb-1 block">Away Team</label>
                <Input value={awayTeam} onChange={(e) => setAwayTeam(e.target.value)}
                  className="bg-white/10 border-white/20 text-white" placeholder="e.g. Brazil" />
              </div>
              <Button onClick={loadPlayers} disabled={loadingPlayers} variant="outline"
                className="border-white/20 text-gray-300 hover:bg-white/10">
                {loadingPlayers ? "Loading…" : "Load Squads"}
              </Button>
              <Button onClick={runPrediction} disabled={loading}
                className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold">
                {loading ? "Predicting…" : "Run Prediction"}
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Home team controls */}
          {[
            {
              team: homeTeam, override: homeOverride, setOverride: setHomeOverride,
              players: homePlayers, setPlayers: setHomePlayers, injuredCount: homeInjured,
            },
            {
              team: awayTeam, override: awayOverride, setOverride: setAwayOverride,
              players: awayPlayers, setPlayers: setAwayPlayers, injuredCount: awayInjured,
            },
          ].map(({ team, override, setOverride, players, setPlayers, injuredCount }) => (
            <Card key={team} className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-base text-white flex items-center justify-between">
                  <span>{team}</span>
                  {injuredCount > 0 && (
                    <Badge className="bg-red-500/20 text-red-300 border-red-500/30 text-xs">
                      {injuredCount} unavailable
                    </Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <OverrideSlider
                  label="Recent Form"
                  hint="Points per game from last 5 matches (0=poor, 3=perfect)"
                  value={override.form} min={0} max={3} step={0.1}
                  onChange={(v) => setOverride((o) => ({ ...o, form: v }))}
                />
                <OverrideSlider
                  label="Injury Burden"
                  hint="Fraction of squad unavailable (0=fully fit, 1=all out)"
                  value={override.injury_burden} min={0} max={1} step={0.05}
                  onChange={(v) => setOverride((o) => ({ ...o, injury_burden: v }))}
                />
                <OverrideSlider
                  label="Coach Impact"
                  hint="Coaching quality multiplier (1.0=neutral, <1=poor, >1=elite)"
                  value={override.coach_impact} min={0.5} max={1.5} step={0.05}
                  onChange={(v) => setOverride((o) => ({ ...o, coach_impact: v }))}
                />

                {/* Squad table */}
                {players.length > 0 ? (
                  <div className="mt-4">
                    <div className="text-xs text-gray-400 mb-2 font-semibold uppercase tracking-wide">
                      Squad ({players.length})
                    </div>
                    <div className="max-h-64 overflow-y-auto">
                      <table className="w-full text-left">
                        <thead>
                          <tr className="text-gray-500 text-xs border-b border-white/10">
                            <th className="pb-1 pr-3">Player</th>
                            <th className="pr-3">Pos</th>
                            <th className="pr-3">Age</th>
                            <th className="pr-3">G</th>
                            <th className="pr-3">xG</th>
                            <th className="pr-3">Status</th>
                            <th>Susp</th>
                          </tr>
                        </thead>
                        <tbody>
                          {players.map((p) => (
                            <PlayerRow
                              key={p.id}
                              player={p}
                              onToggleInjury={(id, val) =>
                                setPlayers((ps) => togglePlayerInjury(ps, id, val))
                              }
                              onToggleSuspend={(id, val) =>
                                setPlayers((ps) => togglePlayerSuspend(ps, id, val))
                              }
                            />
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-gray-500 text-center py-4">
                    Click &#34;Load Squads&#34; to view and modify player availability
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Prediction result */}
        {prediction && (
          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-base text-white">Scenario Prediction</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center mb-4">
                <div className="text-xl font-bold text-white">
                  {prediction.home_team} vs {prediction.away_team}
                </div>
                <div className="text-sm text-gray-400 mt-1">
                  {prediction.expected_scoreline} · xG {prediction.home_xg.toFixed(2)} – {prediction.away_xg.toFixed(2)}
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4 text-center">
                {[
                  { label: "Statistical", probs: prediction.statistical, color: "text-amber-400" },
                  { label: "ML (Best)", probs: Object.values(prediction.ml_predictions)[0] || prediction.statistical, color: "text-blue-400" },
                  { label: "Ensemble", probs: prediction.ensemble, color: "text-purple-400" },
                ].map(({ label, probs, color }) => probs && (
                  <div key={label} className="bg-white/5 rounded-xl p-4 border border-white/10">
                    <div className={`text-xs font-semibold mb-3 ${color}`}>{label}</div>
                    <div className="space-y-2">
                      <div>
                        <div className="text-green-400 text-xl font-bold">{(probs.home_win * 100).toFixed(1)}%</div>
                        <div className="text-gray-500 text-xs">{prediction.home_team}</div>
                      </div>
                      <div>
                        <div className="text-gray-400 text-lg font-semibold">{(probs.draw * 100).toFixed(1)}%</div>
                        <div className="text-gray-500 text-xs">Draw</div>
                      </div>
                      <div>
                        <div className="text-red-400 text-xl font-bold">{(probs.away_win * 100).toFixed(1)}%</div>
                        <div className="text-gray-500 text-xs">{prediction.away_team}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {prediction.explanation?.narrative && (
                <div className="mt-4 bg-white/5 rounded-lg p-3 border border-white/10 text-sm text-gray-300">
                  {prediction.explanation.narrative}
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
