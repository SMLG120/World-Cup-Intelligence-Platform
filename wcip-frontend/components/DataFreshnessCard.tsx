"use client";

import { AlertCircle, CheckCircle2, Database, RefreshCw } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import {
  useAdminRetrainIfNeeded,
  useDataFreshness,
  useMLRetrain,
  useRefreshAllData,
  useRefreshElo,
  useRefreshFifaRankings,
  useRefreshPlayers,
} from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

function formatUtc(value?: string | null) {
  if (!value) return "Not loaded";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  const year = parsed.getUTCFullYear();
  const month = String(parsed.getUTCMonth() + 1).padStart(2, "0");
  const day = String(parsed.getUTCDate()).padStart(2, "0");
  const hour = String(parsed.getUTCHours()).padStart(2, "0");
  const minute = String(parsed.getUTCMinutes()).padStart(2, "0");
  return `${year}-${month}-${day} ${hour}:${minute} UTC`;
}

function formatDateOnly(value?: string | null) {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toISOString().slice(0, 10);
}

function sourceState(status?: string) {
  if (!status || status === "not_loaded") {
    return { label: "Data source unavailable", tone: "text-signal" };
  }
  if (status === "failed") {
    return { label: "Using latest cached snapshot", tone: "text-[hsl(45_95%_58%)]" };
  }
  if (status === "started") {
    return { label: "Updating data...", tone: "text-[hsl(45_95%_58%)]" };
  }
  return { label: "Predictions refreshed", tone: "text-pitch" };
}

function FreshnessRow({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string | null;
}) {
  return (
    <div className="min-w-0 rounded-md border border-line/70 px-3 py-2">
      <div className="kicker mb-1">{label}</div>
      <div className="tnum text-sm text-fg">{value}</div>
      {detail && <div className="mt-1 truncate text-[10px] text-muted">{detail}</div>}
    </div>
  );
}

export function DataFreshnessCard({ compact = false }: { compact?: boolean }) {
  const { user } = useAuth();
  const freshness = useDataFreshness();
  const refresh = useRefreshAllData();
  const refreshElo = useRefreshElo();
  const refreshFifa = useRefreshFifaRankings();
  const refreshPlayers = useRefreshPlayers();
  const retrainCheck = useAdminRetrainIfNeeded();
  const retrain = useMLRetrain();

  const data = freshness.data;
  const state = sourceState(data?.source_status?.elo === "failed" ? "failed" : data?.source_status?.fifa);
  const isAdmin = user?.role === "admin";
  const adminPending = refresh.isPending || refreshElo.isPending || refreshFifa.isPending
    || refreshPlayers.isPending || retrainCheck.isPending || retrain.isPending;
  const adminActions = [
    { label: "Elo", run: () => refreshElo.mutate(), pending: refreshElo.isPending, title: "Refresh Elo ratings" },
    { label: "FIFA", run: () => refreshFifa.mutate(), pending: refreshFifa.isPending, title: "Refresh FIFA rankings" },
    { label: "Players", run: () => refreshPlayers.mutate(), pending: refreshPlayers.isPending, title: "Refresh player data" },
    { label: "All", run: () => refresh.mutate(), pending: refresh.isPending, title: "Refresh all data" },
    { label: "Check", run: () => retrainCheck.mutate({ apply: true }), pending: retrainCheck.isPending, title: "Check retraining thresholds" },
    { label: "Retrain", run: () => retrain.mutate("all"), pending: retrain.isPending, title: "Trigger model retraining" },
  ];

  const rows = data
    ? [
        {
          label: "Elo updated",
          value: formatUtc(data.last_elo_update),
          detail: `${formatDateOnly(data.last_elo_rating_date) ?? "No rating date"} · ${data.elo_data_version ?? "No version"}`,
        },
        {
          label: "FIFA ranking updated",
          value: formatUtc(data.last_fifa_ranking_update),
          detail: `${formatDateOnly(data.last_fifa_ranking_date) ?? "No ranking date"} · ${data.fifa_data_version ?? "No version"}`,
        },
        {
          label: "Squad data updated",
          value: formatUtc(data.last_player_data_update),
          detail: data.player_data_source ?? "No squad source",
        },
        {
          label: "Latest results updated",
          value: formatUtc(data.last_match_result_update),
          detail: "Match results source",
        },
        {
          label: "Model trained",
          value: formatUtc(data.model_trained_at),
          detail: data.model_version ?? "No active model",
        },
        {
          label: "Prediction data snapshot",
          value: formatUtc(data.data_snapshot_timestamp),
          detail: data.data_snapshot_version,
        },
      ]
    : [];
  const visibleRows = compact ? rows.slice(0, 3) : rows;

  return (
    <div className="rounded-md border border-line bg-elevated/50 px-3 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Database className="h-4 w-4 shrink-0 text-pitch" aria-hidden />
          <span className="kicker">Data freshness</span>
          <Badge className={state.tone}>{state.label}</Badge>
        </div>

        {freshness.isLoading ? (
          <span className="text-xs text-muted">Loading snapshot status...</span>
        ) : freshness.isError ? (
          <span className="inline-flex items-center gap-1 text-xs text-signal">
            <AlertCircle className="h-3.5 w-3.5" aria-hidden />
            Freshness unavailable
          </span>
        ) : data?.using_latest_cached_snapshot ? (
          <span className="inline-flex items-center gap-1 text-xs text-pitch sm:ml-auto">
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
            Latest cached snapshot
          </span>
        ) : null}

        {isAdmin && (
          <div className="flex flex-wrap gap-1 sm:ml-auto">
            {adminActions.map((action) => (
              <Button
                key={action.label}
                onClick={action.run}
                disabled={adminPending}
                variant="outline"
                size="sm"
                title={action.title}
              >
                <RefreshCw className={`h-3.5 w-3.5 ${action.pending ? "animate-spin" : ""}`} aria-hidden />
                {action.pending ? "..." : action.label}
              </Button>
            ))}
          </div>
        )}
      </div>

      {visibleRows.length > 0 && (
        <div className={`mt-3 grid gap-2 ${compact ? "sm:grid-cols-3" : "sm:grid-cols-2 xl:grid-cols-3"}`}>
          {visibleRows.map((row) => (
            <FreshnessRow key={row.label} {...row} />
          ))}
        </div>
      )}

      {(refresh.isSuccess || refreshElo.isSuccess || refreshFifa.isSuccess || refreshPlayers.isSuccess || retrainCheck.isSuccess || retrain.isSuccess) && (
        <div className="mt-2 text-xs text-pitch">Data workflow updated.</div>
      )}
      {(refresh.isError || refreshElo.isError || refreshFifa.isError || refreshPlayers.isError || retrainCheck.isError || retrain.isError) && (
        <div className="mt-2 text-xs text-signal">
          {((refresh.error || refreshElo.error || refreshFifa.error || refreshPlayers.error || retrainCheck.error || retrain.error) as Error).message}
        </div>
      )}
    </div>
  );
}

export function DataFreshnessStrip({ compact = false }: { compact?: boolean }) {
  return <DataFreshnessCard compact={compact} />;
}
