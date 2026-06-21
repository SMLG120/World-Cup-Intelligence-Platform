"use client";

/**
 * TournamentBracket — visual knockout bracket for World Cup 2026.
 *
 * Layout: absolute-positioned match cards within a fixed-height container,
 * with SVG connector lines drawn between rounds to show advancement paths.
 *
 * Match pairing follows sequential order (M49+M50 → M65, M51+M52 → M66, ...),
 * which mirrors the backend's build_2026_bracket() sequential pairing.
 */

import { motion } from "framer-motion";
import { Trophy } from "lucide-react";
import type { WC2026KnockoutRound, WC2026Match } from "@/lib/types";
import { pct } from "@/lib/utils";
import { cn } from "@/lib/utils";

// ── Layout constants ─────────────────────────────────────────────────────────
const CARD_H = 82;          // px height of each match card
const CARD_W = 196;         // px width of each match card column
const CONN_W = 44;          // px width of connector SVG between rounds
const R32_UNIT = CARD_H + 8; // 90px per R32 slot (card + gap)
const TOTAL_H = 16 * R32_UNIT - 8; // 1432px total bracket height

// ── Round ordering ───────────────────────────────────────────────────────────
const MAIN_ROUNDS = [
  "Round of 32",
  "Round of 16",
  "Quarter-finals",
  "Semi-finals",
  "Final",
] as const;

// ── Position calculator ──────────────────────────────────────────────────────
/**
 * Returns top-y positions for each match in each round.
 * Each round's match is centered between the two feeding matches from the
 * previous round (standard binary-tree bracket alignment).
 */
function calcBracketPositions(): Record<string, number[]> {
  const r32 = Array.from({ length: 16 }, (_, i) => i * R32_UNIT);

  function parentTops(childTops: number[]): number[] {
    return Array.from({ length: childTops.length / 2 }, (_, i) => {
      const c0 = childTops[2 * i] + CARD_H / 2;
      const c1 = childTops[2 * i + 1] + CARD_H / 2;
      return (c0 + c1) / 2 - CARD_H / 2;
    });
  }

  const r16 = parentTops(r32);
  const qf = parentTops(r16);
  const sf = parentTops(qf);
  const final = parentTops(sf);

  return {
    "Round of 32": r32,
    "Round of 16": r16,
    "Quarter-finals": qf,
    "Semi-finals": sf,
    "Final": final,
  };
}

const POSITIONS = calcBracketPositions();

// ── Helper: sort matches by order field ───────────────────────────────────────
function sorted(round: WC2026KnockoutRound): WC2026Match[] {
  return [...round.matches].sort((a, b) => a.order - b.order);
}

// ── SVG connector between two rounds ─────────────────────────────────────────
function ConnectorSvg({
  childTops,
  parentTops,
}: {
  childTops: number[];
  parentTops: number[];
}) {
  const midX = CONN_W / 2;
  return (
    <svg
      width={CONN_W}
      height={TOTAL_H}
      className="shrink-0"
      style={{ overflow: "visible" }}
      aria-hidden
    >
      {parentTops.map((parentTop, i) => {
        const topChild = childTops[2 * i];
        const botChild = childTops[2 * i + 1];
        if (topChild === undefined || botChild === undefined) return null;

        const topCenter = topChild + CARD_H / 2;
        const botCenter = botChild + CARD_H / 2;
        const parCenter = parentTop + CARD_H / 2;

        return (
          <g
            key={i}
            stroke="hsl(var(--line))"
            strokeWidth={1.5}
            fill="none"
            strokeOpacity={0.5}
          >
            {/* Horizontal arm from top child right edge to midX */}
            <line x1={0} y1={topCenter} x2={midX} y2={topCenter} />
            {/* Horizontal arm from bottom child right edge to midX */}
            <line x1={0} y1={botCenter} x2={midX} y2={botCenter} />
            {/* Vertical spine connecting both child arms */}
            <line x1={midX} y1={topCenter} x2={midX} y2={botCenter} />
            {/* Horizontal line to parent match */}
            <line x1={midX} y1={parCenter} x2={CONN_W} y2={parCenter} />
          </g>
        );
      })}
    </svg>
  );
}

// ── Individual match card ─────────────────────────────────────────────────────
function BracketMatchCard({
  match,
  onTeamClick,
}: {
  match: WC2026Match;
  onTeamClick?: (team: string) => void;
}) {
  const winnerProb =
    match.winner_probability != null ? pct(match.winner_probability) : null;
  const modeLabel = (match.effective_prediction_mode ?? match.prediction_mode ?? "ens")
    .replace("_fallback", "")
    .split("_")
    .map((s) => s[0])
    .join("")
    .toUpperCase()
    .slice(0, 3);

  const teamRow = (team: string, code: string | undefined, goals: number) => (
    <button
      key={team}
      onClick={() => onTeamClick?.(team)}
      title={`View ${team} squad`}
      className={cn(
        "flex items-center justify-between gap-1 w-full text-left px-2 py-[3px]",
        "rounded-sm text-[11px] transition-colors",
        match.winner === team
          ? "text-fg font-semibold bg-pitch/10 hover:bg-pitch/20"
          : "text-muted hover:bg-elevated hover:text-fg",
      )}
    >
      <div className="flex items-center gap-1.5 min-w-0">
        <span className="font-mono text-[9px] text-muted w-6 shrink-0">
          {code ?? team.slice(0, 3).toUpperCase()}
        </span>
        <span className="truncate">{team}</span>
      </div>
      <span
        className={cn(
          "tnum shrink-0 font-semibold text-[11px]",
          match.winner === team && "text-pitch",
        )}
      >
        {goals}
      </span>
    </button>
  );

  return (
    <div
      className={cn(
        "border rounded-md bg-surface/90 overflow-hidden",
        match.winner ? "border-line shadow-sm" : "border-line/40",
      )}
      style={{ height: CARD_H }}
    >
      <div className="flex flex-col justify-center h-full py-1.5">
        {teamRow(match.home, match.home_code, match.home_goals)}
        <div className="border-t border-line/20 my-0.5 mx-2" />
        {teamRow(match.away, match.away_code, match.away_goals)}
        {(winnerProb || match.match_id) && (
          <div className="flex justify-between items-center px-2 pt-0.5 text-[9px] text-muted/80">
            <span className="font-mono">{match.match_id}</span>
            {winnerProb && (
              <span className="tnum text-pitch font-medium">{winnerProb}</span>
            )}
            {modeLabel && (
              <span className="uppercase tracking-wide">{modeLabel}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Champion card at end of bracket ──────────────────────────────────────────
function ChampionCard({
  champion,
  probability,
  topOffset,
}: {
  champion: string;
  probability?: number | null;
  topOffset: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: 0.3 }}
      className="absolute shrink-0"
      style={{ top: topOffset - 32, left: 0, width: 160 }}
    >
      <div className="rounded-lg border border-pitch/60 bg-pitch/8 p-3 text-center shadow-lg">
        <Trophy className="mx-auto mb-1.5 h-5 w-5 text-pitch" aria-hidden />
        <p className="kicker text-[9px] text-pitch mb-1">Champion</p>
        <p className="font-bold text-sm text-fg leading-tight">{champion}</p>
        {probability != null && (
          <p className="tnum text-[10px] text-pitch mt-1">
            {pct(probability)} odds
          </p>
        )}
      </div>
    </motion.div>
  );
}

// ── Third-place match card ────────────────────────────────────────────────────
function ThirdPlaceCard({
  match,
  onTeamClick,
}: {
  match: WC2026Match;
  onTeamClick?: (team: string) => void;
}) {
  return (
    <div className="mt-6 pt-6 border-t border-line/40">
      <p className="kicker text-[10px] mb-2 text-muted">Third-place match</p>
      <div style={{ width: CARD_W }}>
        <BracketMatchCard match={match} onTeamClick={onTeamClick} />
      </div>
      {match.winner && (
        <p className="text-[10px] text-muted mt-1.5">
          <span className="text-fg font-medium">{match.winner}</span> finishes third
          {match.winner_probability != null && (
            <span className="tnum text-pitch ml-1">
              ({pct(match.winner_probability)} probability)
            </span>
          )}
        </p>
      )}
    </div>
  );
}

// ── Round column ─────────────────────────────────────────────────────────────
function RoundColumn({
  roundName,
  matches,
  onTeamClick,
}: {
  roundName: string;
  matches: WC2026Match[];
  onTeamClick?: (team: string) => void;
}) {
  const tops = POSITIONS[roundName];
  if (!tops) return null;

  return (
    <div
      className="relative shrink-0"
      style={{ width: CARD_W, height: TOTAL_H }}
    >
      {matches.map((match, i) => {
        const top = tops[i] ?? 0;
        return (
          <motion.div
            key={match.match_id}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: i * 0.02 }}
            style={{
              position: "absolute",
              top,
              left: 0,
              width: CARD_W,
              height: CARD_H,
            }}
          >
            <BracketMatchCard match={match} onTeamClick={onTeamClick} />
          </motion.div>
        );
      })}
    </div>
  );
}

// ── Main bracket component ───────────────────────────────────────────────────
interface TournamentBracketProps {
  rounds: WC2026KnockoutRound[];
  champion?: string | null;
  championProbability?: number | null;
  onTeamClick?: (team: string) => void;
}

export function TournamentBracket({
  rounds,
  champion,
  championProbability,
  onTeamClick,
}: TournamentBracketProps) {
  const roundMap = new Map(rounds.map((r) => [r.round, sorted(r)]));

  const mainRoundData = MAIN_ROUNDS.map((name) => ({
    name,
    matches: roundMap.get(name) ?? [],
  })).filter((r) => r.matches.length > 0);

  const thirdPlaceMatches = roundMap.get("Third-place match") ?? [];
  const thirdPlaceMatch = thirdPlaceMatches[0] ?? null;

  const finalTop = POSITIONS["Final"]?.[0] ?? 0;
  const championTop = finalTop + CARD_H / 2;

  // Champion column offset from left
  const champLeft =
    mainRoundData.length * CARD_W +
    (mainRoundData.length - 1) * CONN_W +
    16;

  return (
    <div className="space-y-2">
      {/* Round labels row */}
      <div className="flex items-end overflow-x-auto pb-0" style={{ minWidth: champLeft + 160 }}>
        {mainRoundData.map((r, ri) => (
          <div key={r.name} className="flex items-end">
            <div
              className="kicker text-[10px] text-center text-muted"
              style={{ width: CARD_W }}
            >
              {r.name}
            </div>
            {ri < mainRoundData.length - 1 && (
              <div style={{ width: CONN_W }} />
            )}
          </div>
        ))}
        <div className="kicker text-[10px] text-center text-pitch" style={{ width: 160, paddingLeft: 16 }}>
          Champion
        </div>
      </div>

      {/* Bracket scroll container */}
      <div
        className="overflow-x-auto overflow-y-visible pb-4"
        style={{ minHeight: TOTAL_H + 8 }}
      >
        <div
          className="relative flex"
          style={{ width: champLeft + 160, height: TOTAL_H }}
        >
          {/* Round columns interleaved with connector SVGs */}
          {mainRoundData.map((r, ri) => (
            <div key={r.name} className="flex items-start">
              <RoundColumn
                roundName={r.name}
                matches={r.matches}
                onTeamClick={onTeamClick}
              />
              {ri < mainRoundData.length - 1 && (
                <ConnectorSvg
                  childTops={POSITIONS[r.name]?.slice(0, r.matches.length * 2) ?? []}
                  parentTops={POSITIONS[mainRoundData[ri + 1].name]?.slice(0, mainRoundData[ri + 1].matches.length) ?? []}
                />
              )}
            </div>
          ))}

          {/* Champion display — horizontally after Final, vertically centered on FINAL match */}
          {champion && (
            <div
              className="shrink-0"
              style={{ position: "relative", width: 160, paddingLeft: 16 }}
            >
              {/* Connector line from FINAL to champion card */}
              <svg
                style={{
                  position: "absolute",
                  left: 0,
                  top: 0,
                  width: 16,
                  height: TOTAL_H,
                  overflow: "visible",
                }}
                aria-hidden
              >
                <line
                  x1={0}
                  y1={championTop}
                  x2={16}
                  y2={championTop}
                  stroke="hsl(var(--pitch))"
                  strokeWidth={1.5}
                  strokeOpacity={0.6}
                />
              </svg>
              <ChampionCard
                champion={champion}
                probability={championProbability}
                topOffset={championTop}
              />
            </div>
          )}
        </div>
      </div>

      {/* Third-place match — below the main bracket */}
      {thirdPlaceMatch && (
        <ThirdPlaceCard match={thirdPlaceMatch} onTeamClick={onTeamClick} />
      )}
    </div>
  );
}
