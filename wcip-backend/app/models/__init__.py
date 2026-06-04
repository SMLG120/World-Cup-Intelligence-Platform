"""Import all models so they register on Base.metadata."""
from app.models.simulation import (SavedScenario, SimKind, Simulation,  # noqa: F401
                                   SimStatus, SimulationRun)
from app.models.team import EloHistory, Team  # noqa: F401
from app.models.user import AuditLog, User, UserRole  # noqa: F401

__all__ = [
    "User", "UserRole", "AuditLog",
    "Team", "EloHistory",
    "Simulation", "SimulationRun", "SavedScenario", "SimStatus", "SimKind",
]
