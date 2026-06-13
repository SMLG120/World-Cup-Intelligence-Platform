"""Tests for FIFA squad PDF text conversion into player import CSV."""
from __future__ import annotations

import csv

from sqlalchemy import select

from app.db.base import SessionLocal
from app.models.player import Player
from etl.player_ratings import import_player_ratings_csv
from etl.players.fifa_squad_pdf import parse_squad_text, write_players_csv


SAMPLE_TEXT = """
SQUAD LISTArgentina (ARG)
# POS PLAYER NAME FIRST NAME(S) LAST NAME(S) NAME ON SHIRT DOB CLUB HEIGHT (CM) CAPS GOALS
GK MUSSO Juan Juan Agustín MUSSO MUSSO 06/05/1994 Atlético De Madrid (ESP) 193 4 0
FW MESSI Lionel Lionel Andrés MESSI MESSI 24/06/1987 Inter Miami CF (USA) 170 199 117
ROLE COACH NAME FIRST NAME(S) LAST NAME(S) NATIONALITY
Head coach SCALONI Lionel Lionel Sebastián SCALONI Argentina
SQUAD LISTAlgeria (ALG)
# POS PLAYER NAME FIRST NAME(S) LAST NAME(S) NAME ON SHIRT DOB CLUB HEIGHT (CM) CAPS GOALS
MF AOUAR Houssem Houssem-Eddine Chaabane AOUAR AOUAR 30/06/1998 Al Ittihad (KSA) 175 23 6
DF AIT-NOURI Rayan Rayan AÏT-NOURI AIT NOURI 06/06/2001 Manchester City FC (ENG) 180 30 0
"""


def test_parse_fifa_squad_text_to_import_rows(tmp_path):
    players = parse_squad_text(SAMPLE_TEXT)

    assert len(players) == 4
    assert players[0].team_name == "Argentina"
    assert players[0].player_name == "Juan Musso"
    assert players[0].position == "GK"
    assert players[0].age == 32
    assert players[1].player_name == "Lionel Messi"
    assert players[1].international_caps == 199
    assert players[1].player_rating > players[0].player_rating
    assert players[3].player_name == "Rayan Ait-Nouri"

    output = write_players_csv(players, tmp_path / "fifa_players.csv")
    with output.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["player_name"] == "Juan Musso"
    assert rows[0]["team_name"] == "Argentina"
    assert rows[0]["rating_method"] == "fifa_roster_proxy_v1"
    assert rows[1]["player_rating"]


def test_fifa_squad_csv_imports_into_player_table(client, tmp_path):
    players = parse_squad_text(SAMPLE_TEXT)
    output = write_players_csv(players, tmp_path / "fifa_players.csv")

    result = import_player_ratings_csv(
        output,
        source_name="fifa_wc2026_squad_pdf",
        source_version="test_v1",
        source_url="https://fdp.fifa.org/assetspublic/ce281/pdf/SquadLists-English.pdf",
    )

    assert result["valid_rows"] == 4
    assert result["teams_updated"] == 2

    db = SessionLocal()
    try:
        messi = db.scalar(
            select(Player).where(Player.team_name == "Argentina", Player.name == "Lionel Messi")
        )
        assert messi is not None
        assert messi.position == "FWD"
        assert messi.international_caps == 199
        assert messi.international_goals == 117
        assert messi.player_rating is not None
        assert messi.player_rating_source == "fifa_wc2026_squad_pdf"
    finally:
        db.close()
