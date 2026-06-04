"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { MLModel } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

const MODEL_COLORS: Record<string, string> = {
  logistic: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  random_forest: "bg-green-500/20 text-green-300 border-green-500/30",
  xgboost: "bg-orange-500/20 text-orange-300 border-orange-500/30",
  lightgbm: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  catboost: "bg-pink-500/20 text-pink-300 border-pink-500/30",
};

const MODEL_LABELS: Record<string, string> = {
  logistic: "Logistic Regression",
  random_forest: "Random Forest",
  xgboost: "XGBoost",
  lightgbm: "LightGBM",
  catboost: "CatBoost",
};

function MetricBar({
  label, value, max = 1, lowerIsBetter = false, unit = ""
}: {
  label: string; value: number | null; max?: number; lowerIsBetter?: boolean; unit?: string;
}) {
  if (value === null) return (
    <div className="flex justify-between text-xs py-1 border-b border-white/5">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-600">Not trained</span>
    </div>
  );

  const pct = Math.min(100, (value / max) * 100);
  const isGood = lowerIsBetter ? value < max * 0.5 : value > max * 0.5;
  const barColor = isGood ? "bg-green-500" : "bg-amber-500";

  return (
    <div className="py-1 border-b border-white/5">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-400">{label}</span>
        <span className="text-white font-mono">{value.toFixed(3)}{unit}</span>
      </div>
      <div className="h-1 bg-white/10 rounded-full overflow-hidden">
        <div
          className={`h-full ${barColor} rounded-full transition-all`}
          style={{ width: lowerIsBetter ? `${100 - pct}%` : `${pct}%` }}
        />
      </div>
    </div>
  );
}

function ModelCard({ model }: { model: MLModel }) {
  const colorClass = MODEL_COLORS[model.model_name] || "bg-gray-500/20 text-gray-300";
  const label = MODEL_LABELS[model.model_name] || model.model_name;

  return (
    <Card className="bg-white/5 border-white/10 hover:bg-white/8 transition-colors">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <span className={`text-xs px-2 py-0.5 rounded border ${colorClass} mb-2 inline-block`}>
              {label}
            </span>
            <div className="text-xs text-gray-500">
              v{model.version} · {model.training_samples?.toLocaleString() || "?"} samples
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-400">Ensemble Weight</div>
            <div className="text-lg font-bold text-white">{(model.ensemble_weight * 100).toFixed(1)}%</div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <MetricBar label="Accuracy" value={model.accuracy} max={1} />
        <MetricBar label="F1 Score" value={model.f1_score} max={1} />
        <MetricBar label="Brier Score" value={model.brier_score} max={1} lowerIsBetter />
        <MetricBar label="Log Loss" value={model.log_loss} max={2} lowerIsBetter />
        <MetricBar label="Calibration" value={model.calibration_score} max={1} />

        {model.trained_at && (
          <div className="text-xs text-gray-600 mt-2 text-right">
            Trained {new Date(model.trained_at).toLocaleDateString()}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FeatureImportanceChart({ features }: { features: Record<string, number> }) {
  const sorted = Object.entries(features)
    .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
    .slice(0, 10);
  const maxAbs = Math.max(...sorted.map(([, v]) => Math.abs(v)));

  return (
    <div className="space-y-2">
      {sorted.map(([name, value]) => {
        const pct = maxAbs > 0 ? (Math.abs(value) / maxAbs) * 100 : 0;
        const isPositive = value >= 0;
        return (
          <div key={name} className="flex items-center gap-3">
            <div className="text-xs text-gray-400 w-44 text-right truncate">{name.replace(/_/g, " ")}</div>
            <div className="flex-1 flex items-center gap-1">
              <div className="w-full h-3 bg-white/5 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${isPositive ? "bg-blue-500" : "bg-red-500"}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className={`text-xs font-mono w-16 ${isPositive ? "text-blue-400" : "text-red-400"}`}>
                {value > 0 ? "+" : ""}{value.toFixed(3)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function ModelsPage() {
  const [models, setModels] = useState<MLModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [features, setFeatures] = useState<Record<string, number> | null>(null);
  const [featHome, setFeatHome] = useState("France");
  const [featAway, setFeatAway] = useState("Brazil");
  const [featLoading, setFeatLoading] = useState(false);

  useEffect(() => {
    api.mlModels()
      .then(setModels)
      .finally(() => setLoading(false));
  }, []);

  async function loadFeatures() {
    setFeatLoading(true);
    try {
      const fv = await api.mlFeatures(featHome, featAway);
      setFeatures(fv.features);
    } finally {
      setFeatLoading(false);
    }
  }

  const activeModels = models.filter((m) => m.is_active);
  const hasModels = activeModels.length > 0;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 text-white p-6">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-orange-400 to-red-400 bg-clip-text text-transparent mb-2">
            Model Dashboard
          </h1>
          <p className="text-gray-400">
            Trained ML models, evaluation metrics, and feature importance
          </p>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-60 bg-white/5 rounded-xl" />
            ))}
          </div>
        ) : hasModels ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
            {activeModels.map((m) => (
              <ModelCard key={m.id} model={m} />
            ))}
          </div>
        ) : (
          <Card className="bg-white/5 border-white/10 mb-8">
            <CardContent className="p-8 text-center">
              <div className="text-4xl mb-3">🤖</div>
              <h2 className="text-lg font-semibold text-white mb-2">No Trained Models Yet</h2>
              <p className="text-gray-400 text-sm max-w-md mx-auto mb-4">
                Models haven&#39;t been trained yet. To train:
              </p>
              <ol className="text-sm text-gray-400 text-left inline-block space-y-1">
                <li>1. Run the ETL pipeline to load historical match data</li>
                <li>2. Call <code className="text-amber-400">POST /api/v1/ml/train</code> (admin required)</li>
                <li>3. Or run <code className="text-amber-400">python -m ml.train</code> from the backend</li>
              </ol>
            </CardContent>
          </Card>
        )}

        {/* Ensemble weights summary */}
        {hasModels && (
          <Card className="bg-white/5 border-white/10 mb-8">
            <CardHeader>
              <CardTitle className="text-sm text-gray-300">Ensemble Weight Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2 h-8 rounded-full overflow-hidden">
                {activeModels.map((m) => {
                  const colorMap: Record<string, string> = {
                    logistic: "bg-blue-500",
                    random_forest: "bg-green-500",
                    xgboost: "bg-orange-500",
                    lightgbm: "bg-purple-500",
                    catboost: "bg-pink-500",
                  };
                  return (
                    <div
                      key={m.model_name}
                      className={`${colorMap[m.model_name] || "bg-gray-500"} transition-all`}
                      style={{ width: `${m.ensemble_weight * 100}%` }}
                      title={`${MODEL_LABELS[m.model_name]}: ${(m.ensemble_weight * 100).toFixed(1)}%`}
                    />
                  );
                })}
              </div>
              <div className="flex gap-4 mt-3 flex-wrap">
                {activeModels.map((m) => {
                  const colorMap: Record<string, string> = {
                    logistic: "bg-blue-500",
                    random_forest: "bg-green-500",
                    xgboost: "bg-orange-500",
                    lightgbm: "bg-purple-500",
                    catboost: "bg-pink-500",
                  };
                  return (
                    <div key={m.model_name} className="flex items-center gap-1 text-xs">
                      <div className={`w-2 h-2 rounded-full ${colorMap[m.model_name] || "bg-gray-500"}`} />
                      <span className="text-gray-400">{MODEL_LABELS[m.model_name]}</span>
                      <span className="text-white">{(m.ensemble_weight * 100).toFixed(1)}%</span>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Feature importance explorer */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-sm text-gray-300">Feature Vector Explorer</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-3 mb-4 items-end flex-wrap">
              <div className="flex-1 min-w-28">
                <label className="text-xs text-gray-400 mb-1 block">Home</label>
                <input
                  value={featHome}
                  onChange={(e) => setFeatHome(e.target.value)}
                  className="w-full bg-white/10 border border-white/20 text-white text-sm rounded-lg px-3 py-2 outline-none focus:border-blue-400"
                />
              </div>
              <div className="text-gray-500 pb-2 text-sm">vs</div>
              <div className="flex-1 min-w-28">
                <label className="text-xs text-gray-400 mb-1 block">Away</label>
                <input
                  value={featAway}
                  onChange={(e) => setFeatAway(e.target.value)}
                  className="w-full bg-white/10 border border-white/20 text-white text-sm rounded-lg px-3 py-2 outline-none focus:border-blue-400"
                />
              </div>
              <button
                onClick={loadFeatures}
                disabled={featLoading}
                className="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50"
              >
                {featLoading ? "Loading…" : "Compute Features"}
              </button>
            </div>
            {features ? (
              <FeatureImportanceChart features={features} />
            ) : (
              <p className="text-gray-500 text-sm text-center py-6">
                Enter two teams to see the 17-feature vector
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
