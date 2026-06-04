"use client";

import { useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { HybridPrediction } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

const MODEL_LABELS: Record<string, string> = {
  logistic: "Logistic Regression",
  random_forest: "Random Forest",
  xgboost: "XGBoost",
  lightgbm: "LightGBM",
  catboost: "CatBoost",
};

function OutcomeBar({ label, probs, color }: {
  label: string;
  probs: { home_win: number; draw: number; away_win: number };
  color: string;
}) {
  const hw = (probs.home_win * 100).toFixed(1);
  const dr = (probs.draw * 100).toFixed(1);
  const aw = (probs.away_win * 100).toFixed(1);
  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <span className={`text-xs font-semibold ${color}`}>{label}</span>
        <div className="flex gap-4 text-xs text-gray-400">
          <span className="text-green-400 font-medium">{hw}%</span>
          <span className="text-gray-400">{dr}%</span>
          <span className="text-red-400 font-medium">{aw}%</span>
        </div>
      </div>
      <div className="flex h-3 rounded-full overflow-hidden">
        <div className="bg-green-500 transition-all" style={{ width: `${probs.home_win * 100}%` }} />
        <div className="bg-gray-500 transition-all" style={{ width: `${probs.draw * 100}%` }} />
        <div className="bg-red-500 transition-all" style={{ width: `${probs.away_win * 100}%` }} />
      </div>
    </div>
  );
}

function ExplanationPanel({ prediction }: { prediction: HybridPrediction }) {
  const { explanation } = prediction;
  if (!explanation) return null;
  return (
    <Card className="bg-white/5 border-white/10 mt-4">
      <CardHeader>
        <CardTitle className="text-sm text-gray-300">AI Explanation</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {explanation.narrative && (
          <p className="text-sm text-gray-300 bg-white/5 rounded-lg p-3 border border-white/10">
            {explanation.narrative}
          </p>
        )}
        <div className="grid grid-cols-2 gap-4">
          {explanation.top_positive.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-green-400 mb-2">
                Favours {prediction.home_team}
              </div>
              {explanation.top_positive.map((f) => (
                <div key={f.name} className="flex justify-between text-xs py-1 border-b border-white/5">
                  <span className="text-gray-400">{f.display_name}</span>
                  <span className="text-green-400 font-mono">+{f.impact.toFixed(3)}</span>
                </div>
              ))}
            </div>
          )}
          {explanation.top_negative.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-red-400 mb-2">
                Favours {prediction.away_team}
              </div>
              {explanation.top_negative.map((f) => (
                <div key={f.name} className="flex justify-between text-xs py-1 border-b border-white/5">
                  <span className="text-gray-400">{f.display_name}</span>
                  <span className="text-red-400 font-mono">{f.impact.toFixed(3)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function ComparePage() {
  const [homeTeam, setHomeTeam] = useState("France");
  const [awayTeam, setAwayTeam] = useState("Brazil");
  const [prediction, setPrediction] = useState<HybridPrediction | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const predict = useCallback(async () => {
    if (!homeTeam.trim() || !awayTeam.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.mlPredict({
        home_team: homeTeam,
        away_team: awayTeam,
        include_shap: true,
      });
      setPrediction(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Prediction failed");
    } finally {
      setLoading(false);
    }
  }, [homeTeam, awayTeam]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 text-white p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent mb-2">
            Prediction Comparison
          </h1>
          <p className="text-gray-400">
            Compare Statistical, Machine Learning, and Ensemble predictions side-by-side
          </p>
        </div>

        {/* Team selector */}
        <Card className="bg-white/5 border-white/10 mb-6">
          <CardContent className="p-4">
            <div className="flex gap-3 items-end">
              <div className="flex-1">
                <label className="text-xs text-gray-400 mb-1 block">Home Team</label>
                <Input
                  value={homeTeam}
                  onChange={(e) => setHomeTeam(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && predict()}
                  placeholder="e.g. France"
                  className="bg-white/10 border-white/20 text-white placeholder:text-gray-500"
                />
              </div>
              <div className="text-gray-500 pb-2 font-bold">vs</div>
              <div className="flex-1">
                <label className="text-xs text-gray-400 mb-1 block">Away Team</label>
                <Input
                  value={awayTeam}
                  onChange={(e) => setAwayTeam(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && predict()}
                  placeholder="e.g. Brazil"
                  className="bg-white/10 border-white/20 text-white placeholder:text-gray-500"
                />
              </div>
              <Button
                onClick={predict}
                disabled={loading}
                className="bg-blue-600 hover:bg-blue-500 text-white font-semibold"
              >
                {loading ? "Predicting…" : "Compare"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {error && (
          <div className="bg-red-500/20 border border-red-500/30 rounded-lg p-3 mb-4 text-red-300 text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-24 bg-white/5 rounded-xl" />
            ))}
          </div>
        ) : prediction ? (
          <div className="space-y-4">
            {/* Match header */}
            <div className="text-center py-4">
              <div className="text-2xl font-bold text-white">
                {prediction.home_team}
                <span className="text-gray-500 mx-3">vs</span>
                {prediction.away_team}
              </div>
              <div className="text-sm text-gray-400 mt-1">
                Expected: {prediction.expected_scoreline} ·
                xG {prediction.home_xg.toFixed(2)} – {prediction.away_xg.toFixed(2)}
              </div>
              <div className="flex justify-center gap-4 mt-2 text-xs">
                <span className="text-gray-400">
                  Confidence: <span className="text-white">{(prediction.confidence_score * 100).toFixed(0)}%</span>
                </span>
                <span className="text-gray-400">
                  Model Agreement: <span className="text-white">{(prediction.model_agreement * 100).toFixed(0)}%</span>
                </span>
              </div>
            </div>

            {/* Legend */}
            <div className="flex gap-6 text-xs justify-center text-gray-400">
              <span><span className="inline-block w-3 h-3 bg-green-500 rounded-sm mr-1" />Home Win</span>
              <span><span className="inline-block w-3 h-3 bg-gray-500 rounded-sm mr-1" />Draw</span>
              <span><span className="inline-block w-3 h-3 bg-red-500 rounded-sm mr-1" />Away Win</span>
            </div>

            {/* Three-layer comparison */}
            <Card className="bg-white/5 border-white/10">
              <CardContent className="p-4 space-y-5">
                <OutcomeBar
                  label="Statistical (Elo + Poisson)"
                  probs={prediction.statistical}
                  color="text-amber-400"
                />
                {Object.entries(prediction.ml_predictions).map(([model, probs]) => (
                  <OutcomeBar
                    key={model}
                    label={MODEL_LABELS[model] || model}
                    probs={probs}
                    color="text-blue-400"
                  />
                ))}
                <div className="border-t border-white/10 pt-4">
                  <OutcomeBar
                    label="🎯 Ensemble (Weighted Average)"
                    probs={prediction.ensemble}
                    color="text-purple-400"
                  />
                </div>
              </CardContent>
            </Card>

            {/* Probability numbers table */}
            <Card className="bg-white/5 border-white/10">
              <CardContent className="p-4">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-400 text-xs border-b border-white/10">
                      <th className="text-left py-2">Model</th>
                      <th className="text-right text-green-400">{prediction.home_team}</th>
                      <th className="text-right text-gray-400">Draw</th>
                      <th className="text-right text-red-400">{prediction.away_team}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-white/5">
                      <td className="py-2 text-amber-400">Statistical</td>
                      <td className="text-right text-green-400">{(prediction.statistical.home_win * 100).toFixed(1)}%</td>
                      <td className="text-right text-gray-400">{(prediction.statistical.draw * 100).toFixed(1)}%</td>
                      <td className="text-right text-red-400">{(prediction.statistical.away_win * 100).toFixed(1)}%</td>
                    </tr>
                    {Object.entries(prediction.ml_predictions).map(([model, probs]) => (
                      <tr key={model} className="border-b border-white/5">
                        <td className="py-2 text-blue-400">{MODEL_LABELS[model] || model}</td>
                        <td className="text-right text-green-400">{(probs.home_win * 100).toFixed(1)}%</td>
                        <td className="text-right text-gray-400">{(probs.draw * 100).toFixed(1)}%</td>
                        <td className="text-right text-red-400">{(probs.away_win * 100).toFixed(1)}%</td>
                      </tr>
                    ))}
                    <tr className="font-bold">
                      <td className="py-2 text-purple-400">Ensemble</td>
                      <td className="text-right text-green-400">{(prediction.ensemble.home_win * 100).toFixed(1)}%</td>
                      <td className="text-right text-gray-400">{(prediction.ensemble.draw * 100).toFixed(1)}%</td>
                      <td className="text-right text-red-400">{(prediction.ensemble.away_win * 100).toFixed(1)}%</td>
                    </tr>
                  </tbody>
                </table>
              </CardContent>
            </Card>

            {/* SHAP Explanation */}
            <ExplanationPanel prediction={prediction} />
          </div>
        ) : (
          <div className="text-center py-20 text-gray-500">
            Enter two teams above and click Compare to see the full prediction breakdown
          </div>
        )}
      </div>
    </div>
  );
}
