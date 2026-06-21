"use client";

import { useState } from "react";
import { ragApi } from "@/lib/api";
import type { RagAnswer, RagAskRequest } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { RagAnswerCard } from "@/components/RagAnswerCard";
import { AlertCircle, RotateCcw } from "lucide-react";

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
  const canAsk = query.trim().length >= 3 && !loading;

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
      const detail = err instanceof Error ? err.message : "The analyst service did not respond.";
      setError(`Analyst answer unavailable. ${detail}`);
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
          disabled={!canAsk}
          size="sm"
        >
          {loading ? "Thinking..." : "Ask Analyst"}
        </Button>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-md border border-signal/30 bg-signal/8 px-3 py-2 text-xs text-signal">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <div className="min-w-0 flex-1">
            <p>{error}</p>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="mt-1 h-7 px-2 text-signal"
              onClick={handleAsk}
              disabled={!canAsk}
            >
              <RotateCcw className="mr-1 h-3 w-3" />
              Retry
            </Button>
          </div>
        </div>
      )}

      {answer && <RagAnswerCard answer={answer} />}
    </div>
  );
}
