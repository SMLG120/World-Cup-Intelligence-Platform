"use client";

import { useState } from "react";
import { ragApi } from "@/lib/api";
import type { RagAnswer, RagAskRequest } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { RagAnswerCard } from "@/components/RagAnswerCard";

interface AskAnalystBoxProps {
  placeholder?: string;
  contextType?: string;
  teamId?: number;
  simulationId?: string;
  className?: string;
}

export function AskAnalystBox({
  placeholder = "Ask about teams, players, or the tournament...",
  contextType,
  teamId,
  simulationId,
  className = "",
}: AskAnalystBoxProps) {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState<RagAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAsk() {
    const q = query.trim();
    if (q.length < 3) return;
    setLoading(true);
    setError(null);
    setAnswer(null);
    try {
      const req: RagAskRequest = {
        query: q,
        context_type: contextType ?? null,
        team_id: teamId ?? null,
        simulation_id: simulationId ?? null,
        max_chunks: 5,
      };
      const result = await ragApi.ask(req);
      setAnswer(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to get answer.");
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") handleAsk();
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={loading}
          className="flex-1"
          maxLength={500}
        />
        <Button
          onClick={handleAsk}
          disabled={loading || query.trim().length < 3}
          size="sm"
        >
          {loading ? "Thinking..." : "Ask Analyst"}
        </Button>
      </div>

      {error && (
        <p className="text-xs text-red-500">{error}</p>
      )}

      {answer && <RagAnswerCard answer={answer} />}
    </div>
  );
}
