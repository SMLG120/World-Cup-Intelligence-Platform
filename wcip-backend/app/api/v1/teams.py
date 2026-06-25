"""Team endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.core.cache import cache
from app.core.deps import DbSession
from app.models.match_result import QualifiedTeam
from app.models.player import Coach, Player
from app.models.team import Team
from app.repositories.repos import TeamRepository
from app.schemas.domain import EloPoint, PlayerOut, TeamOut, TeamSquadOut
from ml.features import _get_player_strength_stats
from etl.transform.normalize import canonical

router = APIRouter(prefix="/teams", tags=["teams"])


def _team_metadata(db: DbSession) -> dict[str, dict]:
    """Collect WC-specific metadata keyed by canonical team name."""
    groups = {
        row.team_name: row
        for row in db.scalars(
            select(QualifiedTeam).where(QualifiedTeam.tournament_year == 2026)
        ).all()
    }
    coaches = {
        canonical(team_name): name
        for team_name, name in db.execute(select(Coach.team_name, Coach.name)).all()
    }
    counts: dict[str, int] = {}
    for team_name, count in db.execute(
        select(Player.team_name, func.count(Player.id))
        .where(Player.is_active.is_(True))
        .group_by(Player.team_name)
    ).all():
        canon = canonical(team_name)
        counts[canon] = counts.get(canon, 0) + int(count or 0)
    return {
        "groups": groups,
        "coaches": coaches,
        "counts": counts,
    }


def _team_to_payload(team: Team, metadata: dict[str, dict] | None = None) -> dict:
    metadata = metadata or {}
    groups = metadata.get("groups", {})
    coaches = metadata.get("coaches", {})
    counts = metadata.get("counts", {})
    qualified = groups.get(team.name)
    group_label = qualified.group_label if qualified else None
    code = qualified.team_code if qualified and qualified.team_code else team.code
    return {
        "id": team.id,
        "name": team.name,
        "code": code,
        "fifa_code": code,
        "confederation": qualified.confederation if qualified else team.confederation,
        "elo": team.elo,
        "elo_rating": team.elo,
        "fifa_rank": team.fifa_rank,
        "fifa_ranking": team.fifa_rank,
        "group": group_label,
        "group_label": group_label,
        "coach": coaches.get(team.name),
        "squad_count": int(counts.get(team.name, 0) or 0),
    }


def _player_to_payload(player: Player, team_id: int) -> dict:
    return {
        "id": player.id,
        "team_id": team_id,
        "name": player.name,
        "team_name": player.team_name,
        "position": player.position,
        "club": player.club,
        "age": player.age,
        "nationality": player.nationality,
        "shirt_number": player.shirt_number,
        "first_names": player.first_names,
        "last_names": player.last_names,
        "name_on_shirt": player.name_on_shirt,
        "date_of_birth": player.date_of_birth,
        "height_cm": player.height_cm,
        "minutes_played": player.minutes_played,
        "goals": player.goals,
        "assists": player.assists,
        "xg": player.xg,
        "xag": player.xag,
        "market_value_eur": player.market_value_eur,
        "international_caps": player.international_caps,
        "international_goals": player.international_goals,
        "player_rating": player.player_rating,
        "ea_fc_rating": player.ea_fc_rating,
        "player_rating_source": player.player_rating_source,
        "player_rating_version": player.player_rating_version,
        "injured": player.injured,
        "suspended": player.suspended,
        "profile_description": player.profile_description,
        "fitness_score": player.fitness_score,
        "recent_form_score": player.recent_form_score,
        "data_source": player.data_source,
    }


@router.get("", response_model=list[TeamOut])
def list_teams(
    db: DbSession,
    confederation: str | None = Query(default=None),
    world_cup_only: bool = Query(
        default=True,
        description="When true, return the WC2026 field instead of every historical team.",
    ),
):
    cache_key = f"teams:{confederation or 'all'}:{'wc2026' if world_cup_only else 'all'}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached
    teams = TeamRepository(db).list_all(confederation)
    metadata = _team_metadata(db)
    if world_cup_only:
        wc_names = set(metadata.get("groups", {}))
        teams = [team for team in teams if team.name in wc_names]
    payload = [_team_to_payload(t, metadata) for t in teams]
    cache.set_json(cache_key, payload)
    return payload


@router.get("/{team_id}", response_model=TeamOut)
def get_team(team_id: int, db: DbSession):
    team = TeamRepository(db).get(team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    return _team_to_payload(team, _team_metadata(db))


@router.get("/{team_id}/stats")
def team_stats(team_id: int, db: DbSession):
    team = TeamRepository(db).get(team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    return {
        "id": team.id,
        "name": team.name,
        "elo": team.elo,
        "fifa_rank": team.fifa_rank,
        "attack": team.attack,
        "defence": team.defence,
        "chemistry": team.chemistry,
        "coach_quality": team.coach_quality,
    }


@router.get("/{team_id}/elo-history", response_model=list[EloPoint])
def elo_history(team_id: int, db: DbSession):
    repo = TeamRepository(db)
    if not repo.get(team_id):
        raise HTTPException(404, "Team not found")
    return repo.elo_history(team_id)


@router.get("/{team_id}/players", response_model=list[PlayerOut])
def team_players(
    team_id: int,
    db: DbSession,
    position: str | None = Query(default=None, description="Filter by position: GK, DEF, MID, FWD"),
):
    return _team_player_rows(team_id, db, position)


@router.get("/{team_id}/squad", response_model=TeamSquadOut)
def team_squad(team_id: int, db: DbSession):
    team = TeamRepository(db).get(team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    metadata = _team_metadata(db)
    players = _team_player_rows(team_id, db, None)
    team_payload = _team_to_payload(team, metadata)
    return {
        "team": team_payload,
        "coach": team_payload.get("coach"),
        "squad_count": len(players),
        "squad": players,
    }


def _team_player_rows(
    team_id: int,
    db: DbSession,
    position: str | None = None,
) -> list[dict]:
    team = TeamRepository(db).get(team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    team_names = _team_name_variants(team.name)
    stmt = (
        select(Player)
        .where(
            Player.team_name.in_(team_names),
            Player.is_active.is_(True),
        )
        .order_by(Player.position, Player.name)
    )
    if position:
        stmt = stmt.where(Player.position.in_(_position_variants(position)))
    return [_player_to_payload(player, team.id) for player in db.scalars(stmt).all()]


def _team_name_variants(team_name: str) -> list[str]:
    canon = canonical(team_name)
    variants = {
        team_name,
        canon,
        canon.replace(" and ", " And "),
    }
    if canon == "Bosnia and Herzegovina":
        variants.update({
            "Bosnia And Herzegovina",
            "Bosnia & Herzegovina",
            "Bosnia-Herzegovina",
            "BIH",
        })
    return sorted(variants)


def _position_variants(position: str) -> list[str]:
    text = position.upper()
    aliases = {
        "DF": ["DF", "DEF"],
        "DEF": ["DF", "DEF"],
        "MF": ["MF", "MID"],
        "MID": ["MF", "MID"],
        "FW": ["FW", "FWD"],
        "FWD": ["FW", "FWD"],
        "GK": ["GK"],
    }
    return aliases.get(text, [text])


@router.get("/{team_id}/squad-strength")
def squad_strength(team_id: int, db: DbSession):
    team = TeamRepository(db).get(team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    strength = _get_player_strength_stats(team.name)
    player_count = db.scalar(
        select(func.count(Player.id)).where(
            Player.team_name == team.name,
            Player.is_active.is_(True),
        )
    ) or 0
    return {
        "team_id": team_id,
        "team_name": team.name,
        "player_count": player_count,
        **strength,
    }
