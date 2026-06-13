"""Generated player profile text from supported fields only."""
from __future__ import annotations

from typing import Any


def build_player_profile(player: Any) -> str:
    """Return a short factual profile from fields present on ``player``.

    The text deliberately avoids unsupported scouting claims. Sparse rows are
    labelled incomplete so the frontend can show why a profile is generic.
    """

    parts: list[str] = []
    position = (getattr(player, "position", None) or "Player").upper()
    if position in {"GK", "GOALKEEPER"}:
        parts.append("Goalkeeper")
    elif position in {"DEF", "DF", "CB", "LB", "RB", "DEFENDER"}:
        parts.append("Defender")
    elif position in {"MID", "MF", "CM", "DM", "AM", "MIDFIELDER"}:
        parts.append("Midfielder")
    elif position in {"FWD", "FW", "ST", "LW", "RW", "FORWARD", "ATTACKER"}:
        parts.append("Forward")
    else:
        parts.append("Player")

    club = getattr(player, "club", None)
    if club:
        parts.append(f"at {club}")

    caps = int(getattr(player, "international_caps", 0) or 0)
    goals = int(getattr(player, "international_goals", 0) or 0)
    if caps:
        parts.append(f"with {caps} international caps")
    if goals:
        parts.append(f"and {goals} international goals")

    rating = getattr(player, "player_rating", None) or getattr(player, "ea_fc_rating", None)
    form = getattr(player, "recent_form_score", None)
    status: list[str] = []
    if rating is not None:
        status.append(f"rating {float(rating):.1f}")
    if form is not None:
        status.append(f"form {float(form):.2f}")
    if getattr(player, "injured", False):
        status.append("currently marked injured")
    if getattr(player, "suspended", False):
        status.append("currently marked suspended")

    text = " ".join(parts).strip()
    if status:
        text = f"{text}; " + ", ".join(status) + "."
    else:
        text = f"{text}. Data incomplete; profile is based only on available roster fields."
    return text
