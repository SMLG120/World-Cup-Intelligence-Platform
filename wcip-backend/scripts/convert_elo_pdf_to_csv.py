#!/usr/bin/env python3
"""Convert the static World Football Elo Ratings PDF into a validated CSV."""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pypdf import PdfReader

from scripts.validate_elo_csv import CSV_COLUMNS, validate_csv

SOURCE_NAME = "World Football Elo Ratings PDF"
SOURCE_DATE = "2026-06-21"
DEFAULT_OUTPUT = Path("data/processed/world_football_elo_ratings_2026_06_21.csv")
DEFAULT_INPUTS = [
    Path("/Users/smlgmac/Downloads/World Football Elo Ratings.pdf"),
    Path("/Users/smlgmac/Downloads/World Football Elo Ratings(1).pdf"),
]
OFFICIAL_WORLD_TSV_URL = "https://www.eloratings.net/World.tsv"
OFFICIAL_TEAMS_TSV_URL = "https://www.eloratings.net/en.teams.tsv"


@dataclass(frozen=True)
class EloPdfRow:
    rank: int
    team: str
    rating: int
    average_rank: int
    average_rating: int
    one_year_change_rank: int
    one_year_change_rating: int
    matches_total: int
    matches_home: int
    matches_away: int
    matches_neutral: int
    wins: int
    losses: int
    draws: int
    goals_for: int
    goals_against: int

    def as_csv_row(self) -> dict[str, str | int]:
        return {
            "rank": self.rank,
            "team": self.team,
            "rating": self.rating,
            "average_rank": self.average_rank,
            "average_rating": self.average_rating,
            "one_year_change_rank": self.one_year_change_rank,
            "one_year_change_rating": self.one_year_change_rating,
            "matches_total": self.matches_total,
            "matches_home": self.matches_home,
            "matches_away": self.matches_away,
            "matches_neutral": self.matches_neutral,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "goals_for": self.goals_for,
            "goals_against": self.goals_against,
            "source_name": SOURCE_NAME,
            "source_date": SOURCE_DATE,
        }


SWIFT_VISION_OCR = r'''
import Foundation
import Vision
import AppKit

func escape(_ value: String) -> String {
    return value.replacingOccurrences(of: "\t", with: " ").replacingOccurrences(of: "\n", with: " ")
}

for rawPath in CommandLine.arguments.dropFirst() {
    let url = URL(fileURLWithPath: rawPath)
    var recognized: [VNRecognizedTextObservation] = []
    let request = VNRecognizeTextRequest { request, error in
        if let error = error {
            fputs("OCR request failed for \(rawPath): \(error)\n", stderr)
            return
        }
        recognized = (request.results as? [VNRecognizedTextObservation]) ?? []
    }
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.minimumTextHeight = 0.006
    if #available(macOS 13.0, *) {
        request.revision = VNRecognizeTextRequestRevision3
    }

    let handler = VNImageRequestHandler(url: url, options: [:])
    do {
        try handler.perform([request])
    } catch {
        fputs("OCR failed for \(rawPath): \(error)\n", stderr)
        continue
    }

    for observation in recognized {
        guard let candidate = observation.topCandidates(1).first else { continue }
        let box = observation.boundingBox
        print("\(rawPath)\t\(box.minX)\t\(box.minY)\t\(box.width)\t\(box.height)\t\(escape(candidate.string))")
    }
}
'''


def _resolve_input(input_path: str | None) -> Path:
    candidates = [Path(input_path)] if input_path else DEFAULT_INPUTS
    for candidate in candidates:
        if candidate.exists():
            return candidate
    tried = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"Elo PDF was not found. Tried: {tried}")


def _extract_text(pdf_path: Path) -> list[str]:
    reader = PdfReader(str(pdf_path))
    chunks: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            chunks.append(text)
    return chunks


def _extract_unique_images(pdf_path: Path, output_dir: Path) -> list[Path]:
    reader = PdfReader(str(pdf_path))
    image_paths: list[Path] = []
    seen_hashes: set[str] = set()

    for page_index, page in enumerate(reader.pages, start=1):
        for image_index, image in enumerate(page.images, start=1):
            digest = hashlib.sha256(image.data).hexdigest()
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)
            suffix = Path(image.name).suffix or ".jpg"
            path = output_dir / f"page_{page_index:02d}_image_{image_index:02d}{suffix}"
            path.write_bytes(image.data)
            image_paths.append(path)
    return image_paths


def _ocr_images_with_vision(image_paths: list[Path], tmp_dir: Path) -> list[str]:
    swift = shutil.which("swift")
    if not swift:
        return []
    script_path = tmp_dir / "vision_ocr.swift"
    script_path.write_text(SWIFT_VISION_OCR, encoding="utf-8")
    module_cache = tmp_dir / "swift-module-cache"
    module_cache.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["CLANG_MODULE_CACHE_PATH"] = str(module_cache)
    command = [swift, str(script_path), *[str(path) for path in image_paths]]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=240,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "macOS Vision OCR failed: "
            f"exit={completed.returncode} stderr={completed.stderr.strip()}"
        )
    return _vision_lines_to_text(completed.stdout)


def _vision_lines_to_text(stdout: str) -> list[str]:
    observations: list[tuple[str, float, float, float, str]] = []
    for raw in stdout.splitlines():
        parts = raw.split("\t", 5)
        if len(parts) != 6:
            continue
        path, x, y, width, _height, text = parts
        try:
            observations.append((path, float(y), float(x), float(width), text.strip()))
        except ValueError:
            continue

    grouped: dict[str, list[tuple[float, float, float, str]]] = {}
    for path, y, x, width, text in observations:
        if text:
            grouped.setdefault(path, []).append((y, x, width, text))

    lines: list[str] = []
    for path in sorted(grouped):
        rows: list[list[tuple[float, float, float, str]]] = []
        for observation in sorted(grouped[path], key=lambda item: (-item[0], item[1])):
            y, _x, _width, _text = observation
            for row in rows:
                if abs(row[0][0] - y) <= 0.006:
                    row.append(observation)
                    break
            else:
                rows.append([observation])
        for row in rows:
            ordered = sorted(row, key=lambda item: item[1])
            line = " ".join(item[3] for item in ordered)
            lines.append(line)
    return lines


def _parse_rows(lines: list[str]) -> list[EloPdfRow]:
    rows: list[EloPdfRow] = []
    seen: set[str] = set()
    for line in lines:
        row = _parse_line(line)
        if row is None:
            continue
        key = f"{row.rank}:{row.team.lower()}"
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    rows.sort(key=lambda row: (row.rank, row.rating * -1, row.team))
    return rows


def _parse_official_tsv(world_tsv: str, teams_tsv: str) -> list[EloPdfRow]:
    team_names = _parse_team_dictionary(teams_tsv)
    rows: list[EloPdfRow] = []
    for line in world_tsv.splitlines():
        fields = line.strip().split("\t")
        if len(fields) < 31:
            continue
        code = fields[2]
        team = team_names.get(code)
        if not team:
            continue
        values = [_clean_int(value) for value in fields]
        if values[0] is None or values[1] is None:
            continue
        rows.append(
            EloPdfRow(
                rank=int(values[1]),
                team=team,
                rating=_field_int(fields, 3),
                average_rank=_field_int(fields, 6),
                average_rating=_field_int(fields, 7),
                one_year_change_rank=_field_int(fields, 14),
                one_year_change_rating=_field_int(fields, 15),
                matches_total=_field_int(fields, 22),
                matches_home=_field_int(fields, 23),
                matches_away=_field_int(fields, 24),
                matches_neutral=_field_int(fields, 25),
                wins=_field_int(fields, 26),
                losses=_field_int(fields, 27),
                draws=_field_int(fields, 28),
                goals_for=_field_int(fields, 29),
                goals_against=_field_int(fields, 30),
            )
        )
    rows.sort(key=lambda row: (row.rank, row.rating * -1, row.team))
    return rows


def _parse_team_dictionary(teams_tsv: str) -> dict[str, str]:
    team_names: dict[str, str] = {}
    for line in teams_tsv.splitlines():
        fields = line.strip().split("\t")
        if len(fields) >= 2 and not fields[0].endswith("_loc"):
            team_names[fields[0]] = _clean_team_name(fields[1])
    return team_names


def _fetch_official_rows() -> list[EloPdfRow]:
    world_tsv = _fetch_text(OFFICIAL_WORLD_TSV_URL)
    teams_tsv = _fetch_text(OFFICIAL_TEAMS_TSV_URL)
    return _parse_official_tsv(world_tsv, teams_tsv)


def _fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "WCIP Elo CSV converter"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _parse_line(raw_line: str) -> EloPdfRow | None:
    line = (
        raw_line.replace("−", "-")
        .replace("–", "-")
        .replace("—", "-")
        .replace("'", "")
        .strip()
    )
    if not re.match(r"^\d{1,3}\s+", line):
        return None
    tokens = line.split()
    if len(tokens) < 17:
        return None
    try:
        rank = int(tokens[0])
    except ValueError:
        return None

    rating_index = None
    for idx in range(2, min(len(tokens), 12)):
        if re.fullmatch(r"\d{3,4}", tokens[idx]):
            rating_index = idx
            break
    if rating_index is None:
        return None

    team = _clean_team_name(" ".join(tokens[1:rating_index]))
    numeric_tokens = tokens[rating_index:]
    if len(numeric_tokens) < 14 or not team:
        return None

    numbers = [_clean_int(token) for token in numeric_tokens[:14]]
    if any(value is None for value in numbers):
        return None
    values = [int(value) for value in numbers if value is not None]

    return EloPdfRow(
        rank=rank,
        team=team,
        rating=values[0],
        average_rank=values[1],
        average_rating=values[2],
        one_year_change_rank=values[3],
        one_year_change_rating=values[4],
        matches_total=values[5],
        matches_home=values[6],
        matches_away=values[7],
        matches_neutral=values[8],
        wins=values[9],
        losses=values[10],
        draws=values[11],
        goals_for=values[12],
        goals_against=values[13],
    )


def _clean_team_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    fixes = {
        "Czechia": "Czechia",
        "Ivory Coast": "Ivory Coast",
        "DR Congo": "DR Congo",
        "Cape Verde": "Cape Verde",
        "Curacao": "Curacao",
        "Trinidad and Tobago": "Trinidad and Tobago",
        "Bosnia and Herzegovina": "Bosnia and Herzegovina",
        "United Arab Emirates": "United Arab Emirates",
        "United States": "United States",
        "North Macedonia": "North Macedonia",
        "Northern Ireland": "Northern Ireland",
        "North Korea": "North Korea",
        "South Korea": "South Korea",
    }
    return fixes.get(value, value)


def _clean_int(value: str) -> int | None:
    cleaned = (
        value.replace(",", "")
        .replace("+", "")
        .replace("−", "-")
        .replace("–", "-")
        .replace("—", "-")
        .strip()
    )
    if cleaned in {"-", "_", ""}:
        return 0
    if not re.fullmatch(r"-?\d+", cleaned):
        return None
    return int(cleaned)


def _field_int(fields: list[str], index: int) -> int:
    value = _clean_int(fields[index])
    return 0 if value is None else value


def convert_pdf_to_csv(pdf_path: Path, output_path: Path) -> dict[str, int | str]:
    text_lines = []
    for chunk in _extract_text(pdf_path):
        text_lines.extend(chunk.splitlines())

    rows = _parse_rows(text_lines)
    ocr_lines = 0
    with tempfile.TemporaryDirectory(prefix="elo_pdf_ocr_") as tmp:
        tmp_dir = Path(tmp)
        if len(rows) <= 200:
            image_dir = tmp_dir / "images"
            image_dir.mkdir(exist_ok=True)
            images = _extract_unique_images(pdf_path, image_dir)
            if not images:
                raise RuntimeError("No embedded images were found in the PDF for OCR fallback.")
            lines = _ocr_images_with_vision(images, tmp_dir)
            ocr_lines = len(lines)
            rows = _parse_rows(lines)

    source_mode = "pdf_text" if text_lines else "pdf_ocr"
    if len(rows) <= 200:
        rows = _fetch_official_rows()
        source_mode = "official_world_tsv_fallback"
        if len(rows) <= 200:
            raise RuntimeError(
                f"Only {len(rows)} Elo rows were extracted. "
                "Install/enable OCR support or inspect the PDF images before ingestion."
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.as_csv_row())

    validation = validate_csv(output_path, require_full_extract=True, check_db_teams=False)
    return {
        "rows": int(validation["rows"]),
        "unique_teams": int(validation["unique_teams"]),
        "ocr_lines": ocr_lines,
        "output": str(output_path),
        "source_mode": source_mode,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", nargs="?", help="Path to World Football Elo Ratings PDF.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="CSV output path.")
    args = parser.parse_args(argv)

    try:
        pdf_path = _resolve_input(args.pdf_path)
        result = convert_pdf_to_csv(pdf_path, Path(args.output))
    except Exception as exc:
        print(f"Elo PDF conversion failed: {exc}", file=sys.stderr)
        return 1

    print(
        "Elo PDF conversion complete: "
        f"rows={result['rows']} unique_teams={result['unique_teams']} "
        f"ocr_lines={result['ocr_lines']} source_mode={result['source_mode']} output={result['output']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
