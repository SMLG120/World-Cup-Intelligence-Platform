"""Text chunking for RAG indexing."""
from __future__ import annotations

import re

_SENTENCE_SEP = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str, max_tokens: int = 200, overlap: int = 20) -> list[str]:
    """Split text into overlapping chunks by approximate token count.

    Splits on newlines first, then on sentence boundaries, respecting max_tokens.
    A token is approximated as ~4 characters.
    """
    chars_per_token = 4
    max_chars = max_tokens * chars_per_token
    overlap_chars = overlap * chars_per_token

    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 1 <= max_chars:
            current = (current + "\n" + para).strip() if current else para
        else:
            if current:
                chunks.append(current)
                tail = current[-overlap_chars:] if len(current) > overlap_chars else current
                current = (tail + "\n" + para).strip()
            else:
                # paragraph itself too long — split by sentences
                sentences = _SENTENCE_SEP.split(para)
                for sent in sentences:
                    if len(current) + len(sent) + 1 <= max_chars:
                        current = (current + " " + sent).strip() if current else sent
                    else:
                        if current:
                            chunks.append(current)
                        current = sent

    if current:
        chunks.append(current)

    return chunks or [text]


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
