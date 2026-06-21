"""Import all models so they register on Base.metadata."""
from app.models.match_result import (MatchFeatures, MatchResult,  # noqa: F401
                                     MLModelRecord, QualifiedTeam)
from app.models.player import (Coach, Player, PlayerRatingImport,  # noqa: F401
                               PlayerRatingRecord)
from app.models.ranking import (FifaRankingEntry, FifaRankingSnapshot,  # noqa: F401
                                RankingSourceLog, TeamRanking)
from app.models.simulation import (SavedScenario, SimKind, Simulation,  # noqa: F401
                                   SimStatus, SimulationRun)
from app.models.team import (EloHistory, EloRatingSnapshot, EloSourceLog,  # noqa: F401
                             Team, TeamEloRating)
from app.models.user import AuditLog, User, UserRole  # noqa: F401
from app.models.rag import (RagDocument, RagChunk, RagEmbedding,  # noqa: F401
                             RagQuery, RagAnswer)

__all__ = [
    "User", "UserRole", "AuditLog",
    "Team", "EloHistory", "EloRatingSnapshot", "TeamEloRating", "EloSourceLog",
    "Simulation", "SimulationRun", "SavedScenario", "SimStatus", "SimKind",
    "Player", "Coach", "PlayerRatingImport", "PlayerRatingRecord",
    "FifaRankingSnapshot", "FifaRankingEntry", "TeamRanking", "RankingSourceLog",
    "MatchResult", "MatchFeatures", "MLModelRecord", "QualifiedTeam",
    "RagDocument", "RagChunk", "RagEmbedding", "RagQuery", "RagAnswer",
]
