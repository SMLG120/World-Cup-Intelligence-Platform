"use client";

import { AlertCircle, CheckCircle2, Database, RefreshCw } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useDataFreshness, useRefreshAllData } from "@/lib/queries";
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
  const data = freshness.data;
  const state = sourceState(data?.source_status?.elo === "failed" ? "failed" : data?.source_status?.fifa);
  const isAdmin = user?.role === "admin";

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
          <Button
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
            variant="outline"
            size="sm"
            title="Refresh global data"
            className="sm:ml-auto"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refresh.isPending ? "animate-spin" : ""}`} aria-hidden />
            {refresh.isPending ? "Updating" : "Refresh Data"}
          </Button>
        )}
      </div>
      {refresh.isSuccess && (
        <div className="mt-2 text-xs text-pitch">Predictions refreshed.</div>
      )}
      {refresh.isError && (
        <div className="mt-2 text-xs text-signal">{(refresh.error as Error).message}</div>
      )}
    </div>
  );
}
