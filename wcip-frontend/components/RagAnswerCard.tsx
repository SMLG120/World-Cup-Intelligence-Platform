"use client";

import { useState } from "react";
import type { RagAnswer } from "@/lib/types";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { RagSourcesList } from "@/components/RagSourcesList";

interface RagAnswerCardProps {
  answer: RagAnswer;
  showSources?: boolean;
}

export function RagAnswerCard({ answer, showSources = true }: RagAnswerCardProps) {
  const [expanded, setExpanded] = useState(false);

  const confidencePct = Math.round(answer.confidence * 100);
  const confidenceColor =
    answer.confidence >= 0.75
      ? "text-emerald-400"
      : answer.confidence >= 0.5
      ? "text-amber-400"
      : "text-red-400";

  return (
    <Card className="border border-line/40">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-semibold text-fg/80 uppercase tracking-wide">
            Analyst Response
          </span>
          <span className={`text-xs tabular-nums ${confidenceColor}`}>
            {confidencePct}% confidence
          </span>
        </div>
      </CardHeader>
      <CardBody className="space-y-3 pt-0">
        {answer.warnings.length > 0 && (
          <div className="rounded bg-amber-500/10 border border-amber-500/20 px-3 py-2">
            {answer.warnings.map((w, i) => (
              <p key={i} className="text-xs text-amber-400">
                {w}
              </p>
            ))}
          </div>
        )}

        <div className="text-sm text-fg/90 leading-relaxed whitespace-pre-wrap">
          {expanded ? answer.answer : answer.answer.slice(0, 400)}
          {answer.answer.length > 400 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="ml-1 text-xs text-primary hover:underline"
            >
              {expanded ? "show less" : "show more"}
            </button>
          )}
        </div>

        {showSources && answer.chunks.length > 0 && (
          <RagSourcesList chunks={answer.chunks} maxVisible={3} />
        )}

        {answer.citations.length > 0 && (
          <div className="text-xs text-muted">
            <span className="font-medium">Cited: </span>
            {answer.citations.join(" · ")}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
