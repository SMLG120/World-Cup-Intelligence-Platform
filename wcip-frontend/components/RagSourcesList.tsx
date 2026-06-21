"use client";

import type { RagChunkRef } from "@/lib/types";

interface RagSourcesListProps {
  chunks: RagChunkRef[];
  maxVisible?: number;
}

const DOC_TYPE_LABELS: Record<string, string> = {
  team: "Team Profile",
  player: "Player Profile",
  coach: "Coach Profile",
  tournament: "Tournament Data",
  model: "Prediction Model",
  doc: "Documentation",
};

export function RagSourcesList({ chunks, maxVisible = 3 }: RagSourcesListProps) {
  if (!chunks || chunks.length === 0) return null;

  const visible = chunks.slice(0, maxVisible);

  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-muted uppercase tracking-wide">Sources</p>
      <ul className="space-y-1">
        {visible.map((chunk) => (
          <li key={chunk.chunk_id} className="flex items-start gap-2 text-xs text-muted">
            <span className="shrink-0 rounded bg-surface px-1.5 py-0.5 text-[10px] font-medium text-fg/60">
              {DOC_TYPE_LABELS[chunk.doc_type] ?? chunk.doc_type}
            </span>
            <span className="truncate">{chunk.title}</span>
            {chunk.score > 0 && (
              <span className="ml-auto shrink-0 tabular-nums text-[10px] text-muted/60">
                {chunk.score.toFixed(2)}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
