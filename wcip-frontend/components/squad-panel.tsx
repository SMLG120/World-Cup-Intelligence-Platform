"use client";

/**
 * SquadPanel — sliding side panel showing a team's real squad from the database.
 * Opens when a team name is clicked in the bracket or simulation UI.
 * Data comes from GET /world-cup/players/{team_name} (PDF-ingested squad)
 * and GET /world-cup/teams/{team_name} (team detail + coach).
 */

import { useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, User, ShieldAlert } from "lucide-react";
import { useWC2026Players, useWC2026TeamDetail } from "@/lib/queries";
import type { Player } from "@/lib/types";
import { cn } from "@/lib/utils";

// ── Position config ───────────────────────────────────────────────────────────
const POSITION_ORDER = ["GK", "DEF", "MID", "FWD"] as const;
const POSITION_LABELS: Record<string, string> = {
  GK: "Goalkeepers",
  DEF: "Defenders",
  MID: "Midfielders",
  FWD: "Forwards",
};

// ── Player row ────────────────────────────────────────────────────────────────
function PlayerRow({ player, rank }: { player: Player; rank: number }) {
  const displayName = player.name_on_shirt ?? player.name;
  const caps = player.international_caps ?? 0;
  const goals = player.international_goals ?? 0;

  return (
    <div className="flex items-center gap-2 py-1.5 border-b border-line/25 last:border-0 text-xs group">
      {/* Shirt number / rank */}
      <span className="tnum text-[10px] text-muted w-5 text-right shrink-0">
        {player.shirt_number ?? rank}
      </span>

      {/* Name + club */}
      <div className="flex-1 min-w-0">
        <div
          className={cn(
            "truncate font-medium leading-tight",
            caps >= 50 ? "text-fg" : "text-fg/90",
          )}
        >
          {displayName}
        </div>
        {player.club && (
          <div className="text-[10px] text-muted truncate">{player.club}</div>
        )}
      </div>

      {/* Stats */}
      <div className="shrink-0 flex items-center gap-2 text-[10px]">
        {player.height_cm != null && (
          <span className="text-muted">{player.height_cm}cm</span>
        )}
        {caps > 0 && (
          <span className="tnum text-pitch font-medium" title="International caps">
            {caps}
          </span>
        )}
        {goals > 0 && (
          <span className="tnum text-muted" title="International goals">
            {goals}g
          </span>
        )}
      </div>
    </div>
  );
}

// ── Stat chip ─────────────────────────────────────────────────────────────────
function StatChip({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col items-center px-3 py-1.5 bg-elevated rounded-md">
      <span className="tnum text-sm font-bold text-fg">{value}</span>
      <span className="text-[9px] text-muted uppercase tracking-wide">{label}</span>
    </div>
  );
}

// ── Squad panel ───────────────────────────────────────────────────────────────
interface SquadPanelProps {
  teamName: string | null;
  onClose: () => void;
}

export function SquadPanel({ teamName, onClose }: SquadPanelProps) {
  const enabled = !!teamName;
  const { data: squadData, isLoading: squadLoading } = useWC2026Players(
    teamName ?? "",
    enabled,
  );
  const { data: teamDetail, isLoading: detailLoading } = useWC2026TeamDetail(
    teamName ?? "",
    enabled,
  );

  const isLoading = squadLoading || detailLoading;

  // Group players by position and sort by caps desc within each group
  const byPosition = useMemo(() => {
    const players = squadData?.squad ?? [];
    const groups: Record<string, Player[]> = {};
    for (const p of players) {
      const pos = p.position ?? "Unknown";
      if (!groups[pos]) groups[pos] = [];
      groups[pos].push(p);
    }
    for (const pos of Object.keys(groups)) {
      groups[pos].sort(
        (a, b) => (b.international_caps ?? 0) - (a.international_caps ?? 0),
      );
    }
    return groups;
  }, [squadData]);

  const totalPlayers = squadData?.squad?.length ?? 0;
  const totalCaps = (squadData?.squad ?? []).reduce(
    (s, p) => s + (p.international_caps ?? 0),
    0,
  );
  const topScorer = [...(squadData?.squad ?? [])].sort(
    (a, b) => (b.international_goals ?? 0) - (a.international_goals ?? 0),
  )[0];

  return (
    <AnimatePresence>
      {teamName && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/50 z-40 backdrop-blur-[2px]"
          />

          {/* Panel */}
          <motion.aside
            key="panel"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 32, stiffness: 320 }}
            className="fixed right-0 top-0 bottom-0 w-80 max-w-[92vw] bg-surface border-l border-line z-50 flex flex-col"
            aria-label={`${teamName} squad`}
          >
            {/* Sticky header */}
            <div className="sticky top-0 bg-surface/95 backdrop-blur border-b border-line p-4 flex items-start justify-between gap-3 shrink-0">
              <div className="min-w-0">
                <p className="kicker text-[9px] text-muted mb-0.5">Squad</p>
                <h2 className="font-bold text-lg text-fg leading-tight truncate">
                  {teamName}
                </h2>
                {teamDetail && (
                  <p className="text-[11px] text-muted mt-0.5">
                    {teamDetail.confederation} ·{" "}
                    <span className="tnum text-pitch">
                      Elo {Math.round(teamDetail.elo)}
                    </span>{" "}
                    · #{teamDetail.fifa_rank}
                  </p>
                )}
              </div>
              <button
                onClick={onClose}
                aria-label="Close squad panel"
                className="shrink-0 p-1.5 rounded-md hover:bg-elevated transition-colors"
              >
                <X className="h-4 w-4 text-muted" />
              </button>
            </div>

            {/* Scrollable body */}
            <div className="flex-1 overflow-y-auto">
              {isLoading ? (
                <LoadingSkeleton />
              ) : (
                <>
                  {/* Coach */}
                  {teamDetail?.coach?.name && (
                    <div className="px-4 py-3 border-b border-line/50">
                      <p className="kicker text-[9px] text-muted mb-1.5">
                        Head Coach
                      </p>
                      <div className="flex items-center gap-2">
                        <div className="h-7 w-7 rounded-full bg-elevated flex items-center justify-center shrink-0">
                          <User className="h-3.5 w-3.5 text-muted" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-fg">
                            {teamDetail.coach.name}
                          </p>
                          {teamDetail.coach.win_pct != null && (
                            <p className="text-[10px] text-muted">
                              {(teamDetail.coach.win_pct * 100).toFixed(0)}% win rate
                              {teamDetail.coach.impact_score != null && (
                                <span>
                                  {" "}
                                  · impact{" "}
                                  {teamDetail.coach.impact_score.toFixed(2)}
                                </span>
                              )}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Squad summary stats */}
                  {totalPlayers > 0 && (
                    <div className="px-4 py-3 border-b border-line/50">
                      <div className="flex gap-2 justify-around">
                        <StatChip label="Players" value={totalPlayers} />
                        <StatChip label="Total caps" value={totalCaps.toLocaleString()} />
                        {topScorer && (topScorer.international_goals ?? 0) > 0 && (
                          <StatChip
                            label="Top scorer"
                            value={`${topScorer.international_goals}g`}
                          />
                        )}
                      </div>
                      {topScorer && (topScorer.international_goals ?? 0) > 0 && (
                        <p className="text-[10px] text-muted text-center mt-1.5">
                          Top scorer:{" "}
                          <span className="text-fg font-medium">
                            {topScorer.name_on_shirt ?? topScorer.name}
                          </span>
                        </p>
                      )}
                    </div>
                  )}

                  {/* Incomplete squad warning */}
                  {!squadLoading && totalPlayers > 0 && totalPlayers < 20 && (
                    <div className="mx-4 mt-3 px-3 py-2 rounded-md border border-[hsl(45_95%_58%/0.5)] bg-[hsl(45_95%_58%/0.07)] flex items-start gap-2">
                      <ShieldAlert className="h-3.5 w-3.5 text-[hsl(45_95%_58%)] mt-0.5 shrink-0" />
                      <p className="text-[11px] text-[hsl(45_95%_58%)] leading-snug">
                        Squad data incomplete ({totalPlayers} players). Ingest
                        the FIFA PDF to see the full roster.
                      </p>
                    </div>
                  )}

                  {!squadLoading && totalPlayers === 0 && (
                    <div className="mx-4 mt-3 px-3 py-2 rounded-md border border-signal/30 bg-signal/8 flex items-start gap-2">
                      <ShieldAlert className="h-3.5 w-3.5 text-signal mt-0.5 shrink-0" />
                      <p className="text-[11px] text-signal leading-snug">
                        No squad data available. Ingest the FIFA WC 2026 squad
                        PDF via Admin → Ingest Squad PDF.
                      </p>
                    </div>
                  )}

                  {/* Players by position */}
                  <div className="px-4 py-3 space-y-4">
                    {POSITION_ORDER.map((pos) => {
                      const players = byPosition[pos] ?? [];
                      if (!players.length) return null;
                      return (
                        <section key={pos}>
                          <p className="kicker text-[9px] text-muted mb-1.5 flex items-center justify-between">
                            <span>{POSITION_LABELS[pos]}</span>
                            <span className="tnum">{players.length}</span>
                          </p>
                          <div>
                            {players.map((player, idx) => (
                              <PlayerRow
                                key={player.id}
                                player={player}
                                rank={idx + 1}
                              />
                            ))}
                          </div>
                        </section>
                      );
                    })}

                    {/* Unknown position catch-all */}
                    {Object.entries(byPosition)
                      .filter(([pos]) => !POSITION_ORDER.includes(pos as never))
                      .map(([pos, players]) => (
                        <section key={pos}>
                          <p className="kicker text-[9px] text-muted mb-1.5">
                            {pos} ({players.length})
                          </p>
                          <div>
                            {players.map((player, idx) => (
                              <PlayerRow
                                key={player.id}
                                player={player}
                                rank={idx + 1}
                              />
                            ))}
                          </div>
                        </section>
                      ))}
                  </div>

                  {/* Simulation explanation */}
                  {teamDetail && totalPlayers > 0 && (
                    <SimExplanation
                      teamDetail={teamDetail}
                      players={squadData?.squad ?? []}
                    />
                  )}
                </>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

// ── Loading skeleton ──────────────────────────────────────────────────────────
function LoadingSkeleton() {
  return (
    <div className="p-4 space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-10 bg-elevated/50 rounded-md animate-pulse" />
      ))}
    </div>
  );
}

// ── Simulation explanation (plain text, no invented facts) ────────────────────
function SimExplanation({
  teamDetail,
  players,
}: {
  teamDetail: { elo: number; fifa_rank: number; attack: number; defence: number; squad_stats: { avg_age: number } };
  players: Player[];
}) {
  const totalCaps = players.reduce((s, p) => s + (p.international_caps ?? 0), 0);
  const avgCaps = players.length ? Math.round(totalCaps / players.length) : 0;
  const gks = players.filter((p) => p.position === "GK");
  const avgGkHeight =
    gks.length
      ? Math.round(
          gks.reduce((s, p) => s + (p.height_cm ?? 180), 0) / gks.length,
        )
      : null;
  const topAttackers = [...players]
    .filter((p) => p.position === "FWD")
    .sort((a, b) => (b.international_goals ?? 0) - (a.international_goals ?? 0))
    .slice(0, 2);

  const lines: string[] = [];
  if (avgCaps >= 30)
    lines.push(
      `Squad experience is high — average ${avgCaps} caps per player.`,
    );
  if (avgGkHeight && avgGkHeight >= 190)
    lines.push(`Goalkeepers average ${avgGkHeight}cm, providing an aerial advantage.`);
  if (topAttackers.length > 0 && (topAttackers[0].international_goals ?? 0) >= 10)
    lines.push(
      `Attack is led by ${topAttackers[0].name_on_shirt ?? topAttackers[0].name} (${topAttackers[0].international_goals} international goals).`,
    );
  if (teamDetail.attack > 1.05)
    lines.push("Above-average attacking multiplier applied in simulations.");
  if (teamDetail.defence < 0.97)
    lines.push("Defensive multiplier slightly below average.");

  if (!lines.length) return null;

  return (
    <div className="mx-4 mb-4 px-3 py-3 rounded-md border border-line/40 bg-elevated/40 text-[11px] text-muted leading-relaxed space-y-1">
      <p className="kicker text-[9px] mb-1.5">Simulation context</p>
      {lines.map((line, i) => (
        <p key={i}>{line}</p>
      ))}
    </div>
  );
}
