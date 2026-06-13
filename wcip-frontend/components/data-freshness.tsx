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

function shortDate(value?: string | null) {
  if (!value) return "Not loaded";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function sourceState(status?: string) {
  if (!status || status === "not_loaded") return { label: "Data source unavailable", tone: "text-signal" };
  if (status === "failed") return { label: "Using latest cached snapshot", tone: "text-[hsl(45_95%_58%)]" };
  if (status === "started") return { label: "Updating ratings...", tone: "text-[hsl(45_95%_58%)]" };
  return { label: "Predictions refreshed", tone: "text-pitch" };
}

export function DataFreshnessStrip({ compact = false }: { compact?: boolean }) {
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

  return (
    <div className="rounded-md border border-line bg-elevated/50 px-3 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <Database className="h-4 w-4 text-pitch shrink-0" aria-hidden />
          <span className="kicker">Data freshness</span>
          <Badge className={state.tone}>
            {state.label}
          </Badge>
        </div>

        {freshness.isLoading ? (
          <span className="text-xs text-muted">Loading snapshot status...</span>
        ) : freshness.isError ? (
          <span className="inline-flex items-center gap-1 text-xs text-signal">
            <AlertCircle className="h-3.5 w-3.5" aria-hidden />
            Freshness unavailable
          </span>
        ) : data ? (
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
            <span>Elo <span className="tnum text-fg">{shortDate(data.last_elo_update)}</span></span>
            <span>FIFA <span className="tnum text-fg">{shortDate(data.last_fifa_ranking_update)}</span></span>
            {!compact && (
              <>
                <span>Matches <span className="tnum text-fg">{shortDate(data.last_match_result_update)}</span></span>
                <span>Players <span className="tnum text-fg">{shortDate(data.last_player_data_update)}</span></span>
                <span>Model <span className="tnum text-fg">{data.model_version ?? "Not trained"}</span></span>
                <span>Feature <span className="tnum text-fg">{data.feature_version}</span></span>
              </>
            )}
          </div>
        ) : null}

        {data?.using_latest_cached_snapshot && (
          <span className="inline-flex items-center gap-1 text-xs text-pitch sm:ml-auto">
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
            Latest cached snapshot
          </span>
        )}

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
