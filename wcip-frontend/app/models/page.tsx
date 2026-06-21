"use client";

import { useEffect, useMemo, useState } from "react";
import { Activity, AlertCircle, Brain, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type { MLModel } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { DataFreshnessStrip } from "@/components/data-freshness";

type ModelKey = "logistic" | "random_forest" | "xgboost" | "lightgbm" | "catboost";

interface ModelMeta {
  label: string;
  modelType: string;
  role: string;
  description: string;
  strengths: string;
  limitations: string;
  color: string;
}

interface ModelView {
  key: ModelKey;
  record: MLModel;
  meta: ModelMeta;
  mlWeight: number;
  finalContribution: number;
}

const MODEL_ORDER: ModelKey[] = ["logistic", "random_forest", "xgboost", "lightgbm", "catboost"];
const HYBRID_STATISTICAL_SHARE = 0.3;
const HYBRID_ML_SHARE = 0.7;

const MODEL_META: Record<ModelKey, ModelMeta> = {
  logistic: {
    label: "Logistic Regression",
    modelType: "Calibrated linear classifier",
    role: "Stable baseline and interpretability anchor",
    description: "A calibrated linear baseline that helps keep probabilities stable and interpretable.",
    strengths: "Clear feature direction, fast training, reliable probability baseline.",
    limitations: "Cannot capture complex nonlinear football interactions on its own.",
    color: "bg-sky-500/15 text-sky-200 border-sky-400/30",
  },
  random_forest: {
    label: "Random Forest",
    modelType: "Tree ensemble",
    role: "Noise-resistant nonlinear model",
    description: "Uses many decision trees to capture nonlinear feature interactions and reduce noisy-feature risk.",
    strengths: "Robust to noisy inputs and useful for squad, form, and ranking interactions.",
    limitations: "Can be less well calibrated without validation-based weighting.",
    color: "bg-emerald-500/15 text-emerald-200 border-emerald-400/30",
  },
  xgboost: {
    label: "XGBoost",
    modelType: "Gradient boosting",
    role: "High-signal tabular predictor",
    description: "A gradient boosting model optimized for structured prediction and strong sports tabular performance.",
    strengths: "Strong at ranking subtle interactions between Elo, form, and player-strength features.",
    limitations: "Needs careful validation to avoid overfitting sparse international match patterns.",
    color: "bg-orange-500/15 text-orange-200 border-orange-400/30",
  },
  lightgbm: {
    label: "LightGBM",
    modelType: "Fast gradient boosting",
    role: "Efficient boosted-tree challenger",
    description: "A fast gradient boosting model designed for efficient training and strong large-feature performance.",
    strengths: "Efficient training, good nonlinear performance, and useful cross-check against XGBoost.",
    limitations: "Can be sensitive to sparse or weakly populated player features.",
    color: "bg-violet-500/15 text-violet-200 border-violet-400/30",
  },
  catboost: {
    label: "CatBoost",
    modelType: "Ordered gradient boosting",
    role: "Squad and team interaction specialist",
    description: "Handles categorical-style football signals well and captures squad/team interactions effectively.",
    strengths: "Good fit for team identity, squad profile, ranking, and form interactions.",
    limitations: "Still depends on complete, legally sourced player and coach data.",
    color: "bg-rose-500/15 text-rose-200 border-rose-400/30",
  },
};

function normalizeModelName(name: string): ModelKey | null {
  const normalized = name.toLowerCase().replace(/[\s-]+/g, "_");
  if (normalized.includes("logistic")) return "logistic";
  if (normalized.includes("random") || normalized.includes("forest")) return "random_forest";
  if (normalized.includes("xgboost") || normalized.includes("xgb")) return "xgboost";
  if (normalized.includes("lightgbm") || normalized.includes("lgbm")) return "lightgbm";
  if (normalized.includes("catboost") || normalized.includes("cat")) return "catboost";
  return null;
}

function latestTime(model: MLModel): number {
  const trained = model.trained_at ? Date.parse(model.trained_at) : 0;
  return Number.isFinite(trained) ? trained : 0;
}

function normalizeModels(models: MLModel[]): ModelView[] {
  const latestByModel = new Map<ModelKey, MLModel>();

  for (const model of models) {
    if (!model.is_active) continue;
    const key = normalizeModelName(model.model_name);
    if (!key) continue;
    const current = latestByModel.get(key);
    if (
      !current ||
      latestTime(model) > latestTime(current) ||
      (latestTime(model) === latestTime(current) && model.id > current.id)
    ) {
      latestByModel.set(key, model);
    }
  }

  const selected = MODEL_ORDER
    .map((key) => ({ key, record: latestByModel.get(key) }))
    .filter((item): item is { key: ModelKey; record: MLModel } => Boolean(item.record));

  const totalWeight = selected.reduce((sum, item) => sum + safeWeight(item.record.ensemble_weight), 0);
  const equalWeight = selected.length > 0 ? 1 / selected.length : 0;

  return selected.map(({ key, record }) => {
    const mlWeight = totalWeight > 0 ? safeWeight(record.ensemble_weight) / totalWeight : equalWeight;
    return {
      key,
      record,
      meta: MODEL_META[key],
      mlWeight,
      finalContribution: mlWeight * HYBRID_ML_SHARE,
    };
  });
}

function safeWeight(value: number | null | undefined): number {
  return Number.isFinite(value) && value && value > 0 ? value : 0;
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function fmtMetric(value: number | null | undefined, digits = 3): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "Unavailable";
}

function fmtDate(value: string | null | undefined): string {
  if (!value) return "Unavailable";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Unavailable" : parsed.toISOString().slice(0, 10);
}

function statusLabel(model: MLModel): string {
  if (model.requires_recalibration) return "Needs recalibration";
  return model.calibration_status || "Active";
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-white/5 py-1.5 text-xs">
      <span className="text-gray-400">{label}</span>
      <span className="font-mono text-white">{value}</span>
    </div>
  );
}

function ModelCard({ model }: { model: ModelView }) {
  return (
    <Card className="bg-white/5 border-white/10">
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <Badge className={model.meta.color}>{model.meta.label}</Badge>
            <CardTitle className="mt-3 text-base">{model.meta.modelType}</CardTitle>
            <p className="mt-1 text-xs text-gray-400">{model.meta.role}</p>
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-400">Final contribution</div>
            <div className="text-xl font-bold text-white">{pct(model.finalContribution)}</div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm leading-6 text-gray-300">{model.meta.description}</p>
        <div>
          <MetricRow label="ML-only weight" value={pct(model.mlWeight)} />
          <MetricRow label="Accuracy" value={fmtMetric(model.record.accuracy)} />
          <MetricRow label="Log loss" value={fmtMetric(model.record.log_loss)} />
          <MetricRow label="Last trained" value={fmtDate(model.record.trained_at)} />
          <MetricRow label="Version" value={model.record.version || "Unavailable"} />
          <MetricRow label="Status" value={statusLabel(model.record)} />
        </div>
        <div className="grid gap-3 text-xs text-gray-400">
          <div>
            <div className="mb-1 font-semibold text-gray-300">Strengths</div>
            <p>{model.meta.strengths}</p>
          </div>
          <div>
            <div className="mb-1 font-semibold text-gray-300">Limitations</div>
            <p>{model.meta.limitations}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function WeightBar({ models }: { models: ModelView[] }) {
  return (
    <div className="overflow-hidden rounded-lg border border-white/10">
      <div className="flex h-9">
        <div
          className="bg-amber-400/80"
          style={{ width: `${HYBRID_STATISTICAL_SHARE * 100}%` }}
          title={`Statistical Engine: ${pct(HYBRID_STATISTICAL_SHARE)}`}
        />
        {models.map((model) => (
          <div
            key={model.key}
            className={barColor(model.key)}
            style={{ width: `${model.finalContribution * 100}%` }}
            title={`${model.meta.label}: ${pct(model.finalContribution)}`}
          />
        ))}
      </div>
    </div>
  );
}

function barColor(key: ModelKey): string {
  return {
    logistic: "bg-sky-500",
    random_forest: "bg-emerald-500",
    xgboost: "bg-orange-500",
    lightgbm: "bg-violet-500",
    catboost: "bg-rose-500",
  }[key];
}

function FeatureImportanceChart({ features }: { features: Record<string, number> }) {
  const sorted = Object.entries(features)
    .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
    .slice(0, 10);
  const maxAbs = Math.max(...sorted.map(([, value]) => Math.abs(value)), 0);

  return (
    <div className="space-y-2">
      {sorted.map(([name, value]) => {
        const width = maxAbs > 0 ? (Math.abs(value) / maxAbs) * 100 : 0;
        return (
          <div key={name} className="grid grid-cols-[10rem_1fr_4rem] items-center gap-3">
            <div className="truncate text-right text-xs text-gray-400">{name.replace(/_/g, " ")}</div>
            <div className="h-3 overflow-hidden rounded-full bg-white/5">
              <div
                className={`h-full rounded-full ${value >= 0 ? "bg-sky-500" : "bg-signal"}`}
                style={{ width: `${width}%` }}
              />
            </div>
            <span className={`text-xs font-mono ${value >= 0 ? "text-sky-300" : "text-signal"}`}>
              {value > 0 ? "+" : ""}{value.toFixed(3)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function ModelsPage() {
  const [models, setModels] = useState<MLModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [features, setFeatures] = useState<Record<string, number> | null>(null);
  const [featHome, setFeatHome] = useState("France");
  const [featAway, setFeatAway] = useState("Brazil");
  const [featLoading, setFeatLoading] = useState(false);
  const [featError, setFeatError] = useState<string | null>(null);

  const modelViews = useMemo(() => normalizeModels(models), [models]);
  const latestModel = modelViews
    .map((model) => model.record)
    .sort((a, b) => latestTime(b) - latestTime(a))[0];
  const activeCount = models.filter((model) => model.is_active).length;
  const duplicateCount = Math.max(0, activeCount - modelViews.length);
  const needsRecalibration = modelViews.filter((model) => model.record.requires_recalibration).length;

  async function loadModels() {
    setLoading(true);
    setError(null);
    try {
      const rows = await api.mlModels();
      setModels(Array.isArray(rows) ? rows : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load model registry.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadModels();
  }, []);

  async function loadFeatures() {
    setFeatLoading(true);
    setFeatError(null);
    try {
      const fv = await api.mlFeatures(featHome, featAway);
      setFeatures(fv.features);
    } catch (err) {
      setFeatures(null);
      setFeatError(err instanceof Error ? err.message : "Feature vector could not be loaded.");
    } finally {
      setFeatLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 p-6 text-white">
      <div className="mx-auto max-w-6xl">
        <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <Badge className="border-pitch/30 text-pitch">Hybrid Prediction System</Badge>
            <h1 className="mt-3 text-3xl font-bold text-white">Model Dashboard</h1>
            <p className="mt-2 max-w-2xl text-sm text-gray-400">
              Statistical baselines, ML models, ensemble weights, data freshness, and model health.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={loadModels} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Retry
          </Button>
        </header>

        {error && (
          <Card className="mb-8 border-signal/30 bg-signal/10">
            <CardContent className="flex flex-col gap-3 p-5 md:flex-row md:items-center md:justify-between">
              <div className="flex items-start gap-3">
                <AlertCircle className="mt-0.5 h-5 w-5 text-signal" />
                <div>
                  <div className="font-semibold text-white">Model registry unavailable</div>
                  <p className="text-sm text-gray-300">{error}</p>
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={loadModels}>Retry</Button>
            </CardContent>
          </Card>
        )}

        <section className="mb-8 grid gap-4 md:grid-cols-3">
          <Card className="bg-white/5 border-white/10 md:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Brain className="h-4 w-4 text-pitch" />
                Hybrid Prediction System
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 text-sm text-gray-300 md:grid-cols-3">
              <div>
                <div className="text-2xl font-bold text-white">{pct(HYBRID_STATISTICAL_SHARE)}</div>
                <div className="text-xs uppercase tracking-wide text-gray-500">Statistical baseline</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-white">{pct(HYBRID_ML_SHARE)}</div>
                <div className="text-xs uppercase tracking-wide text-gray-500">ML ensemble</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-white">{modelViews.length}/5</div>
                <div className="text-xs uppercase tracking-wide text-gray-500">Active ML families</div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Activity className="h-4 w-4 text-amber-300" />
                Model Health
              </CardTitle>
            </CardHeader>
            <CardContent>
              <MetricRow label="Latest version" value={latestModel?.version || "Unavailable"} />
              <MetricRow label="Last trained" value={fmtDate(latestModel?.trained_at)} />
              <MetricRow label="Needs recalibration" value={String(needsRecalibration)} />
              <MetricRow label="Duplicate registry rows hidden" value={String(duplicateCount)} />
            </CardContent>
          </Card>
        </section>

        <section className="mb-8">
          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-base">Statistical Engine</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 text-sm text-gray-300 md:grid-cols-[1.4fr_1fr]">
              <p className="leading-6">
                Elo ratings, Poisson score modeling, and Monte Carlo tournament simulation form the statistical
                baseline. It is displayed separately from the ML models and contributes {pct(HYBRID_STATISTICAL_SHARE)}
                of the final hybrid prediction.
              </p>
              <div className="rounded-lg border border-white/10 bg-white/5 p-4">
                <MetricRow label="Engine" value="Elo + Poisson + Monte Carlo" />
                <MetricRow label="Final contribution" value={pct(HYBRID_STATISTICAL_SHARE)} />
                <MetricRow label="Role" value="Calibration floor" />
              </div>
            </CardContent>
          </Card>
        </section>

        <section className="mb-8">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold text-white">Machine Learning Models</h2>
              <p className="text-sm text-gray-400">Each model family is shown once using the latest active registry row.</p>
            </div>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 5 }).map((_, index) => (
                <Skeleton key={index} className="h-80 bg-white/5" />
              ))}
            </div>
          ) : modelViews.length > 0 ? (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {modelViews.map((model) => (
                <ModelCard key={model.key} model={model} />
              ))}
            </div>
          ) : (
            <Card className="bg-white/5 border-white/10">
              <CardContent className="p-8 text-center">
                <h2 className="text-lg font-semibold text-white">No Active ML Models</h2>
                <p className="mx-auto mt-2 max-w-md text-sm text-gray-400">
                  Train or activate the model registry before reviewing ensemble weights.
                </p>
              </CardContent>
            </Card>
          )}
        </section>

        {modelViews.length > 0 && (
          <section className="mb-8">
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-base">Ensemble Weighting</CardTitle>
              </CardHeader>
              <CardContent>
                <WeightBar models={modelViews} />
                <div className="mt-4 grid gap-2 text-xs md:grid-cols-2 lg:grid-cols-3">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-amber-400" />
                    <span className="text-gray-400">Statistical Engine</span>
                    <span className="font-mono text-white">{pct(HYBRID_STATISTICAL_SHARE)}</span>
                  </div>
                  {modelViews.map((model) => (
                    <div key={model.key} className="flex items-center gap-2">
                      <span className={`h-2 w-2 rounded-full ${barColor(model.key)}`} />
                      <span className="text-gray-400">{model.meta.label}</span>
                      <span className="font-mono text-white">{pct(model.finalContribution)}</span>
                    </div>
                  ))}
                </div>
                <p className="mt-4 text-sm text-gray-400">
                  ML-only weights are normalized across the five ML families. Final contribution multiplies that
                  ML-only share by the hybrid ML allocation.
                </p>
              </CardContent>
            </Card>
          </section>
        )}

        <section className="mb-8">
          <h2 className="mb-4 text-xl font-semibold text-white">Data Freshness</h2>
          <DataFreshnessStrip />
        </section>

        <section>
          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-base">Feature Vector Explorer</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-4 flex flex-wrap items-end gap-3">
                <div className="min-w-40 flex-1">
                  <label className="mb-1 block text-xs text-gray-400">Home</label>
                  <input
                    value={featHome}
                    onChange={(event) => setFeatHome(event.target.value)}
                    className="w-full rounded-lg border border-white/20 bg-white/10 px-3 py-2 text-sm text-white outline-none focus:border-pitch"
                  />
                </div>
                <div className="pb-2 text-sm text-gray-500">vs</div>
                <div className="min-w-40 flex-1">
                  <label className="mb-1 block text-xs text-gray-400">Away</label>
                  <input
                    value={featAway}
                    onChange={(event) => setFeatAway(event.target.value)}
                    className="w-full rounded-lg border border-white/20 bg-white/10 px-3 py-2 text-sm text-white outline-none focus:border-pitch"
                  />
                </div>
                <Button onClick={loadFeatures} disabled={featLoading}>
                  <RefreshCw className={`h-4 w-4 ${featLoading ? "animate-spin" : ""}`} />
                  {featLoading ? "Computing" : "Compute Features"}
                </Button>
              </div>
              {featError ? (
                <div className="rounded-lg border border-signal/30 bg-signal/10 px-4 py-3 text-sm text-signal">
                  {featError}
                </div>
              ) : features ? (
                <FeatureImportanceChart features={features} />
              ) : (
                <p className="py-6 text-center text-sm text-gray-500">
                  Enter two teams to inspect the current feature vector.
                </p>
              )}
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
