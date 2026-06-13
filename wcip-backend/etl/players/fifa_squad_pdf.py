"""Build player-rating CSV input from the official FIFA WC2026 squad PDF.

The FIFA squad list contains roster facts, not scouting ratings. This module
derives conservative proxy ratings from the factual roster fields so the
existing player-rating importer can feed Player Lab and ML features without
pretending the values are official FIFA ratings.
"""
from __future__ import annotations

import argparse
import csv
import logging
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

FIFA_SQUAD_PDF_URL = "https://fdp.fifa.org/assetspublic/ce281/pdf/SquadLists-English.pdf"
SOURCE_VERSION = "2026-06-12_v1"
TOURNAMENT_START = date(2026, 6, 11)

BACKEND_ROOT = Path(__file__).parents[2]
DEFAULT_PDF_PATH = BACKEND_ROOT / "data" / "external" / "fifa_wc2026_squad_lists_english.pdf"
DEFAULT_CSV_PATH = BACKEND_ROOT / "data" / "external" / "fifa_wc2026_squad_players.csv"

POSITION_MAP = {
    "GK": "GK",
    "DF": "DEF",
    "MF": "MID",
    "FW": "FWD",
}

CSV_FIELDS = [
    "player_name",
    "team_name",
    "position",
    "club",
    "age",
    "international_caps",
    "international_goals",
    "recent_form_score",
    "injured",
    "suspended",
    "minutes_played",
    "goals",
    "assists",
    "xg",
    "xag",
    "market_value_eur",
    "player_rating",
    "ea_fc_rating",
    "source_player_name",
    "dob",
    "height_cm",
    "fifa_team_code",
    "rating_method",
    "source_url",
    "source_version",
]


@dataclass(frozen=True)
class FifaSquadPlayer:
    player_name: str
    team_name: str
    position: str
    club: str
    age: int | None
    international_caps: int
    international_goals: int
    recent_form_score: float
    player_rating: float
    source_player_name: str
    dob: str
    height_cm: int | None
    fifa_team_code: str
    source_url: str
    source_version: str

    def to_import_row(self) -> dict[str, Any]:
        return {
            "player_name": self.player_name,
            "team_name": self.team_name,
            "position": self.position,
            "club": self.club,
            "age": self.age or "",
            "international_caps": self.international_caps,
            "international_goals": self.international_goals,
            "recent_form_score": round(self.recent_form_score, 4),
            "injured": "false",
            "suspended": "false",
            "minutes_played": 0,
            "goals": self.international_goals,
            "assists": 0,
            "xg": 0,
            "xag": 0,
            "market_value_eur": "",
            "player_rating": round(self.player_rating, 2),
            "ea_fc_rating": "",
            "source_player_name": self.source_player_name,
            "dob": self.dob,
            "height_cm": self.height_cm or "",
            "fifa_team_code": self.fifa_team_code,
            "rating_method": "fifa_roster_proxy_v1",
            "source_url": self.source_url,
            "source_version": self.source_version,
        }


def download_fifa_squad_pdf(
    output_path: str | Path = DEFAULT_PDF_PATH,
    *,
    source_url: str = FIFA_SQUAD_PDF_URL,
) -> Path:
    """Download the FIFA squad PDF to a local file."""
    import httpx

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", source_url, follow_redirects=True, timeout=60) as response:
        response.raise_for_status()
        with path.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
    return path


def extract_text_from_pdf(source_path: str | Path) -> str:
    """Extract text from a PDF using pypdf.

    `pypdf` is optional at import time so tests and text-file parsing do not
    require it. Install project requirements before using PDF extraction.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF extraction requires pypdf. Run `pip install -r requirements.txt` "
            "or pass --source-text with text extracted from the PDF."
        ) from exc

    reader = PdfReader(str(source_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def build_csv_from_source(
    *,
    source_pdf: str | Path | None = None,
    source_text: str | Path | None = None,
    output_path: str | Path = DEFAULT_CSV_PATH,
    source_url: str = FIFA_SQUAD_PDF_URL,
    source_version: str = SOURCE_VERSION,
    download: bool = False,
) -> dict[str, Any]:
    """Parse FIFA squad source data and write importer-ready CSV."""
    if source_text:
        text = Path(source_text).read_text(encoding="utf-8")
    else:
        pdf_path = Path(source_pdf) if source_pdf else DEFAULT_PDF_PATH
        if download and not pdf_path.exists():
            download_fifa_squad_pdf(pdf_path, source_url=source_url)
        if not pdf_path.exists():
            raise FileNotFoundError(
                f"FIFA squad PDF not found at {pdf_path}. Download it from {source_url} "
                "or rerun with --download."
            )
        text = extract_text_from_pdf(pdf_path)

    players = parse_squad_text(
        text,
        source_url=source_url,
        source_version=source_version,
    )
    csv_path = write_players_csv(players, output_path)
    return {
        "source_url": source_url,
        "source_version": source_version,
        "output_path": str(csv_path),
        "players": len(players),
        "teams": len({player.team_name for player in players}),
    }


def parse_squad_text(
    text: str,
    *,
    source_url: str = FIFA_SQUAD_PDF_URL,
    source_version: str = SOURCE_VERSION,
) -> list[FifaSquadPlayer]:
    """Parse text extracted from the FIFA squad PDF."""
    players: list[FifaSquadPlayer] = []
    current_team = ""
    current_code = ""

    for raw_line in _iter_clean_lines(text):
        maybe_team = _parse_team_header(raw_line)
        if maybe_team:
            current_team, current_code = maybe_team
            continue

        if not current_team or not _looks_like_player_row(raw_line):
            continue

        try:
            players.append(
                _parse_player_line(
                    raw_line,
                    team_name=current_team,
                    fifa_team_code=current_code,
                    source_url=source_url,
                    source_version=source_version,
                )
            )
        except ValueError as exc:
            logger.debug("Skipping unparseable FIFA squad row %r: %s", raw_line, exc)

    return players


def write_players_csv(
    players: Iterable[FifaSquadPlayer],
    output_path: str | Path = DEFAULT_CSV_PATH,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [player.to_import_row() for player in players]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _iter_clean_lines(text: str) -> Iterable[str]:
    for line in text.replace("\xa0", " ").splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip()
        if not cleaned:
            continue
        if cleaned.isdigit():
            continue
        if cleaned.startswith(("# POS", "ROLE COACH", "DOB Date", "FIFA World Cup")):
            continue
        if cleaned.startswith("11 June 2026"):
            continue
        if cleaned.startswith("Friday,"):
            continue
        yield cleaned


def _parse_team_header(line: str) -> tuple[str, str] | None:
    text = line.replace("SQUAD LIST", "").strip()
    match = re.match(r"^(?P<team>.+?)\s+\((?P<code>[A-Z]{3})\)$", text)
    if not match:
        return None
    team = match.group("team").strip()
    if not team or team in {"CLUB", "POSITION"}:
        return None
    return team, match.group("code")


def _looks_like_player_row(line: str) -> bool:
    return bool(re.match(r"^(GK|DF|MF|FW)\s+", line))


def _parse_player_line(
    line: str,
    *,
    team_name: str,
    fifa_team_code: str,
    source_url: str,
    source_version: str,
) -> FifaSquadPlayer:
    match = re.match(
        r"^(?P<pos>GK|DF|MF|FW)\s+"
        r"(?P<head>.+?)\s+"
        r"(?P<dob>\d{2}/\d{2}/\d{4})\s+"
        r"(?P<club>.+?)\s+"
        r"(?P<height>\d{3})\s+"
        r"(?P<caps>\d+)\s+"
        r"(?P<goals>\d+)$",
        line,
    )
    if not match:
        raise ValueError("row does not match FIFA squad format")

    position = POSITION_MAP[match.group("pos")]
    caps = int(match.group("caps"))
    goals = int(match.group("goals"))
    height = int(match.group("height"))
    dob = match.group("dob")
    age = _age_on(dob, TOURNAMENT_START)
    source_name, player_name = _extract_player_names(match.group("head"))

    return FifaSquadPlayer(
        player_name=player_name,
        team_name=team_name,
        position=position,
        club=match.group("club").strip(),
        age=age,
        international_caps=caps,
        international_goals=goals,
        recent_form_score=_derive_form_proxy(caps, goals),
        player_rating=_derive_player_rating(position, caps, goals, age, height),
        source_player_name=source_name,
        dob=dob,
        height_cm=height,
        fifa_team_code=fifa_team_code,
        source_url=source_url,
        source_version=source_version,
    )


def _extract_player_names(head: str) -> tuple[str, str]:
    tokens = head.split()
    if len(tokens) < 2:
        return head, head.title()

    surname_tokens: list[str] = []
    while tokens and _is_upper_name_token(tokens[0]):
        surname_tokens.append(tokens.pop(0))
    if not surname_tokens or not tokens:
        source = head
        return source, _smart_title(source)

    given_tokens = _detect_given_name_tokens(tokens)
    source = f"{' '.join(surname_tokens)} {' '.join(given_tokens)}"
    display = f"{' '.join(_smart_title(t) for t in given_tokens)} {' '.join(_smart_title(t) for t in surname_tokens)}"
    return source, display.strip()


def _detect_given_name_tokens(tokens: list[str]) -> list[str]:
    max_len = min(4, len(tokens))
    norm_tokens = [_normalise_name_token(token) for token in tokens]
    for size in range(1, max_len + 1):
        if len(tokens) >= size * 2 and norm_tokens[:size] == norm_tokens[size:size * 2]:
            return tokens[:size]
    return tokens[:1]


def _is_upper_name_token(token: str) -> bool:
    letters = [char for char in token if char.isalpha()]
    return bool(letters) and token.upper() == token


def _smart_title(token: str) -> str:
    return "-".join(part.capitalize() for part in token.split("-"))


def _normalise_name_token(token: str) -> str:
    normalised = unicodedata.normalize("NFKD", token)
    ascii_text = "".join(char for char in normalised if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", ascii_text.lower())


def _age_on(dob: str, on_date: date) -> int | None:
    try:
        born = datetime.strptime(dob, "%d/%m/%Y").date()
    except ValueError:
        return None
    return on_date.year - born.year - ((on_date.month, on_date.day) < (born.month, born.day))


def _derive_form_proxy(caps: int, goals: int) -> float:
    experience = min(0.25, math.log1p(max(caps, 0)) / 20.0)
    scoring = min(0.20, (goals / max(caps, 1)) * 0.35)
    return min(0.95, max(0.35, 0.45 + experience + scoring))


def _derive_player_rating(
    position: str,
    caps: int,
    goals: int,
    age: int | None,
    height_cm: int | None,
) -> float:
    caps_score = min(22.0, math.log1p(max(caps, 0)) * 4.2)
    goal_weight = {"GK": 2.0, "DEF": 5.0, "MID": 8.0, "FWD": 13.0}.get(position, 6.0)
    goal_score = min(goal_weight, goals * 0.16 + (goals / max(caps, 1)) * goal_weight)
    if age is None:
        age_score = 0.0
    else:
        age_score = max(-5.0, min(4.0, 4.0 - abs(age - 28) * 0.65))

    height_score = 0.0
    if height_cm:
        if position == "GK":
            height_score = min(2.0, max(0.0, (height_cm - 185) / 8.0))
        elif position == "DEF":
            height_score = min(1.0, max(0.0, (height_cm - 183) / 10.0))

    rating = 55.0 + caps_score + goal_score + age_score + height_score
    return min(92.0, max(45.0, rating))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build/import FIFA WC2026 squad CSV")
    parser.add_argument("--source-pdf", default=str(DEFAULT_PDF_PATH))
    parser.add_argument("--source-text")
    parser.add_argument("--output", default=str(DEFAULT_CSV_PATH))
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--import-db", action="store_true")
    parser.add_argument("--source-url", default=FIFA_SQUAD_PDF_URL)
    parser.add_argument("--source-version", default=SOURCE_VERSION)
    args = parser.parse_args(argv)

    result = build_csv_from_source(
        source_pdf=args.source_pdf,
        source_text=args.source_text,
        output_path=args.output,
        source_url=args.source_url,
        source_version=args.source_version,
        download=args.download,
    )
    print(result)

    if args.import_db:
        from etl.player_ratings import import_player_ratings_csv

        import_result = import_player_ratings_csv(
            args.output,
            source_name="fifa_wc2026_squad_pdf",
            source_version=args.source_version,
            source_url=args.source_url,
            notes="Official FIFA squad-list facts with conservative fifa_roster_proxy_v1 ratings.",
        )
        print(import_result)


if __name__ == "__main__":
    main()
