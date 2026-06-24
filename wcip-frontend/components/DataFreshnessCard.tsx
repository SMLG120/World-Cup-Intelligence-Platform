"use client";

import { AlertCircle, CheckCircle2, Database, RefreshCw } from "lucide-react";
import { ApiError, getApiBaseUrl, getApiConfigIssue } from "@/lib/api";
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

function freshnessState({
  isLoading,
  isError,
  data,
  configIssue,
}: {
  isLoading: boolean;
  isError: boolean;
  data: ReturnType<typeof useDataFreshness>["data"];
  configIssue: ReturnType<typeof getApiConfigIssue>;
}) {
  if (isLoading) {
    return { label: "Checking sources", tone: "text-muted" };
  }
  if (configIssue) {
    return { label: "Backend not configured", tone: "text-signal" };
  }
  if (isError) {
    return { label: "Backend unreachable", tone: "text-signal" };
  }
  if (!data) {
    return { label: "Data source unavailable", tone: "text-signal" };
  }
  if (data.status === "available") {
    return { label: "Predictions refreshed", tone: "text-pitch" };
  }
  if (data.status === "partial") {
    return { label: "Partial snapshot", tone: "text-[hsl(45_95%_58%)]" };
  }
  if (data.status === "unavailable") {
    return { label: "Data unavailable", tone: "text-signal" };
  }
  const missingCore = [
    data.last_elo_update,
    data.last_fifa_ranking_update,
    data.last_player_data_update,
    data.model_trained_at,
  ].filter((value) => !value).length;
  const statuses = Object.values(data.source_status ?? {});
  if (missingCore > 0 || statuses.some((status) => status === "not_loaded" || status === "failed")) {
    return { label: "Partial snapshot", tone: "text-[hsl(45_95%_58%)]" };
  }
  return { label: "Predictions refreshed", tone: "text-pitch" };
}

function errorDetail(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 0 && error.detail && typeof error.detail === "object" && "detail" in error.detail) {
      return String((error.detail as { detail: unknown }).detail);
    }
    if (error.status === 0) {
      return error.message;
    }
    return `${error.message} (${error.status})`;
  }
  if (error instanceof Error) return error.message;
  return "The backend freshness endpoint could not be reached.";
}

function sourceStatus(
  data: ReturnType<typeof useDataFreshness>["data"],
  key: string,
  fallback?: string,
) {
  return data?.sources?.[key]?.status ?? fallback ?? "unknown";
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
  const configIssue = getApiConfigIssue();
  const state = freshnessState({
    isLoading: freshness.isLoading,
    isError: freshness.isError,
    data,
    configIssue,
  });
  const isAdmin = user?.role === "admin";
  const warnings = data?.warnings ?? [];
  const hasNotice = Boolean(data?.message || warnings.length > 0);
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
          detail: `${formatDateOnly(data.last_elo_rating_date) ?? "No rating date"} · ${data.sources?.elo?.source_name ?? data.elo_data_version ?? "No version"}`,
        },
        {
          label: "FIFA ranking updated",
          value: formatUtc(data.last_fifa_ranking_update),
          detail: `${formatDateOnly(data.last_fifa_ranking_date) ?? "No ranking date"} · ${data.sources?.fifa_rankings?.source_name ?? data.fifa_data_version ?? "No version"}`,
        },
        {
          label: "Squad data updated",
          value: formatUtc(data.last_player_data_update),
          detail: data.player_data_source
            ?? data.sources?.squads?.source_name
            ?? "No squad source",
        },
        {
          label: "Latest results updated",
          value: formatUtc(data.last_match_result_update),
          detail: `${data.sources?.matches?.rows ?? 0} results loaded`,
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
        {
          label: "Source status",
          value: data.using_latest_cached_snapshot ? "Snapshot available" : "Snapshot missing",
          detail: `Elo ${sourceStatus(data, "elo", data.source_status?.elo)} · FIFA ${sourceStatus(data, "fifa_rankings", data.source_status?.fifa)} · Squads ${sourceStatus(data, "squads", data.source_status?.players)} · Ratings ${sourceStatus(data, "player_ratings")}`,
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
          <div className="min-w-0 text-xs text-signal sm:ml-auto">
            <span className="inline-flex items-center gap-1">
              <AlertCircle className="h-3.5 w-3.5" aria-hidden />
              Freshness unavailable
            </span>
            <p className="mt-1 max-w-md truncate">{errorDetail(freshness.error)}</p>
          </div>
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

      {!compact && !freshness.isError && hasNotice && (
        <div className="mt-3 rounded-md border border-[hsl(45_95%_58%/0.35)] bg-[hsl(45_95%_58%/0.08)] px-3 py-2 text-xs text-fg">
          {data?.message && <p className="font-medium">{data.message}</p>}
          {warnings.length > 0 && (
            <ul className="mt-1 space-y-1 text-muted">
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {!compact && configIssue && (
        <div className="mt-3 rounded-md border border-signal/30 bg-signal/8 px-3 py-2 text-xs text-signal">
          <p className="font-medium">{configIssue.message}</p>
          <p className="mt-1">{configIssue.detail}</p>
        </div>
      )}

      {!compact && !configIssue && freshness.isError && (
        <div className="mt-3 rounded-md border border-signal/30 bg-signal/8 px-3 py-2 text-xs text-signal">
          <p className="font-medium">Could not reach `/api/v1/data/freshness`.</p>
          <p className="mt-1">
            API base: <span className="font-mono">{getApiBaseUrl()}</span>
          </p>
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
