"""Domain schemas: teams, predictions, simulations, scenarios."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


# ---- pagination ------------------------------------------------------------
class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int


# ---- teams -----------------------------------------------------------------
class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str
    confederation: str
    elo: float
    fifa_rank: int


class PlayerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    team_name: str
    position: str
    club: Optional[str]
    age: Optional[int]
    nationality: Optional[str]
    minutes_played: float
    goals: float
    assists: float
    xg: float
    xag: float
    market_value_eur: Optional[float]
    international_caps: int
    international_goals: int
    injured: bool
    suspended: bool
    profile_description: Optional[str]
    fitness_score: float
    recent_form_score: float
    data_source: Optional[str]


class EloPoint(BaseModel):
    rating: float
    opponent: Optional[str]
    recorded_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---- per-team match modifiers ----------------------------------------------
class TeamModifiers(BaseModel):
    """Optional scenario overrides applied to a team for one prediction."""
    attack: float = Field(default=1.0, ge=0.1, le=3.0)
    defence: float = Field(default=1.0, ge=0.1, le=3.0)
    injury: float = Field(default=1.0, ge=0.0, le=1.0)
    morale: float = Field(default=1.0, ge=0.5, le=1.5)
    fatigue: float = Field(default=1.0, ge=0.0, le=1.0)
    chemistry: float = Field(default=1.0, ge=0.5, le=1.5)
    coaching: float = Field(default=1.0, ge=0.5, le=1.5)


# ---- match prediction ------------------------------------------------------
class MatchRequest(BaseModel):
    home: str
    away: str
    home_modifiers: TeamModifiers = Field(default_factory=TeamModifiers)
    away_modifiers: TeamModifiers = Field(default_factory=TeamModifiers)
    knockout: bool = False


class MatchProbabilities(BaseModel):
    home_win: float
    draw: float
    away_win: float


class MatchPrediction(BaseModel):
    home: str
    away: str
    probabilities: MatchProbabilities
    home_xg: float
    away_xg: float
    explanation: str
    factors: list[dict]


# ---- tournament & monte carlo ----------------------------------------------
class TournamentRequest(BaseModel):
    edition: str = "2022"
    runs: int = Field(default=10000, ge=1, le=50000)
    overrides: dict[str, TeamModifiers] = Field(default_factory=dict)
    name: str = "Tournament simulation"
    seed: Optional[int] = None
    deterministic: bool = False


class TeamProbabilityOut(BaseModel):
    team: str
    champion: float
    final: float
    semi: float
    quarter: float
    round_of_16: float
    expected_finish: float
    champion_ci_low: float
    champion_ci_high: float


# ---- scenario comparison ---------------------------------------------------
class ScenarioInput(BaseModel):
    label: str
    overrides: dict[str, TeamModifiers] = Field(default_factory=dict)


class ScenarioCompareRequest(BaseModel):
    edition: str = "2022"
    runs: int = Field(default=5000, ge=1, le=50000)
    scenarios: List[ScenarioInput] = Field(min_length=2, max_length=3)
    seed: Optional[int] = None
    deterministic: bool = False


# ---- saved simulations -----------------------------------------------------
class SimulationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    public_token: str
    name: str
    kind: str
    status: str
    params: dict
    result: Optional[dict]
    is_public: bool
    created_at: datetime
    completed_at: Optional[datetime]


class SimulationCreateResponse(BaseModel):
    id: int
    status: str
    task_id: Optional[str] = None
    result: Optional[dict] = None


class SimulationUpdate(BaseModel):
    name: Optional[str] = None
    is_public: Optional[bool] = None


class SimulationSaveRequest(BaseModel):
    """Flexible payload for saving an already-produced result."""

    name: str = "Saved simulation"
    simulation_type: str = "tournament"
    edition: Optional[str] = None
    runs: Optional[int] = Field(default=None, ge=1, le=50000)
    seed: Optional[int] = None
    deterministic: bool = False
    input_teams: Optional[list[str]] = None
    input_parameters: dict[str, Any] = Field(default_factory=dict)
    overrides: dict[str, Any] = Field(default_factory=dict)
    scenario_overrides: dict[str, Any] = Field(default_factory=dict)
    statistical_result: Optional[dict[str, Any]] = None
    ml_result: Optional[dict[str, Any]] = None
    ensemble_result: Optional[dict[str, Any]] = None
    tournament_result: Optional[dict[str, Any]] = None
    champion_probabilities: Optional[list[dict[str, Any]]] = None
    bracket_output: Optional[dict[str, Any]] = None
    result: Optional[dict[str, Any]] = None


class SimulationCompareRequest(BaseModel):
    simulation_ids: list[int] = Field(default_factory=list, max_length=5)
