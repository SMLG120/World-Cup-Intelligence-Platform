"use client";

import { useState } from "react";
import { ragApi } from "@/lib/api";
import type { RagAnswer } from "@/lib/types";
import { RagAnswerCard } from "@/components/RagAnswerCard";
import { Button } from "@/components/ui/button";

interface PredictionExplanationPanelProps {
  homeTeam: string;
  awayTeam: string;
  teamId?: number;
  simulationId?: string;
  className?: string;
}

export function PredictionExplanationPanel({
  homeTeam,
  awayTeam,
  teamId,
  simulationId,
  className = "",
}: PredictionExplanationPanelProps) {
  const [answer, setAnswer] = useState<RagAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleExplain() {
    setLoading(true);
    setError(null);
    try {
      const result = await ragApi.ask({
        query: `What are the key stats and squad details for ${homeTeam} vs ${awayTeam}?`,
        context_type: "team",
        team_id: teamId ?? null,
        simulation_id: simulationId ?? null,
        max_chunks: 6,
      });
      setAnswer(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load explanation.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={`space-y-3 ${className}`}>
      {!answer && !loading && (
        <Button variant="outline" size="sm" onClick={handleExplain}>
          Explain this matchup
        </Button>
      )}

      {loading && (
        <p className="text-xs text-muted animate-pulse">Loading analysis...</p>
      )}

      {error && (
        <p className="text-xs text-red-500">{error}</p>
      )}

      {answer && <RagAnswerCard answer={answer} />}
    </div>
  );
}
