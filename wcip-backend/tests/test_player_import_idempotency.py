"""Player import idempotency and foreign-key safety regressions."""

from uuid import uuid4

from app.db.base import SessionLocal
from app.models.player import Player, PlayerRatingImport, PlayerRatingRecord
from etl.players.load_squad_pdf import _dedupe_players, _delete_placeholder_players


def test_placeholder_players_with_rating_records_are_retired_not_deleted():
    with SessionLocal() as db:
        player_name = f"Placeholder FK Safety {uuid4().hex}"
        batch = PlayerRatingImport(
            source_name="test",
            source_version="fk-safety",
            status="success",
            row_count=1,
            valid_rows=1,
        )
        placeholder = Player(
            name=player_name,
            team_name="Mexico",
            position="UNK",
            data_source="world_cup_2026_placeholder",
            is_active=True,
        )
        db.add_all([batch, placeholder])
        db.flush()
        record = PlayerRatingRecord(
            import_id=batch.id,
            player_id=placeholder.id,
            player_name=placeholder.name,
            team_name=placeholder.team_name,
            position=placeholder.position,
            rating=70.0,
            source_row_hash="fk-safety-placeholder",
        )
        db.add(record)
        db.commit()

        player_id = placeholder.id
        record_id = record.id
        _delete_placeholder_players(db, "Mexico")
        db.commit()
        db.expire_all()

        retired = db.get(Player, player_id)
        rating_record = db.get(PlayerRatingRecord, record_id)
        assert retired is not None
        assert retired.is_active is False
        assert rating_record is not None
        assert rating_record.player_id == player_id


def test_player_dedupe_repoints_rating_records_instead_of_deleting_players():
    with SessionLocal() as db:
        player_name = f"Dedupe Safety {uuid4().hex}"
        batch = PlayerRatingImport(
            source_name="test",
            source_version="dedupe-safety",
            status="success",
            row_count=1,
            valid_rows=1,
        )
        keep = Player(
            name=player_name,
            team_name="Mexico",
            position="MID",
            data_source="FIFA World Cup 2026 Squad PDF",
            is_active=True,
        )
        duplicate = Player(
            name=player_name,
            team_name="Mexico",
            position="UNK",
            data_source="world_cup_2026_placeholder",
            is_active=True,
        )
        db.add_all([batch, keep, duplicate])
        db.flush()
        record = PlayerRatingRecord(
            import_id=batch.id,
            player_id=duplicate.id,
            player_name=duplicate.name,
            team_name=duplicate.team_name,
            position=duplicate.position,
            rating=71.0,
            source_row_hash="fk-safety-dedupe",
        )
        db.add(record)
        db.commit()

        keep_id = keep.id
        duplicate_id = duplicate.id
        record_id = record.id
        _dedupe_players(db, {"Mexico"})
        db.commit()
        db.expire_all()

        deduped_record = db.get(PlayerRatingRecord, record_id)
        retired_duplicate = db.get(Player, duplicate_id)
        assert db.get(Player, keep_id) is not None
        assert retired_duplicate is not None
        assert retired_duplicate.is_active is False
        assert deduped_record is not None
        assert deduped_record.player_id == keep_id
