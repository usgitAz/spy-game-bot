"""ORM models for **future** Postgres archival (TODO).

These models are kept in the repo so schema design is not lost, but the
running bot does **not** open a database connection and does not write rows.

Live gameplay state lives in Redis (`app.domain` / `GameStateRepository`).
"""

from app.models.base import Base
from app.models.enums import GameEndReason, GameWinner, PlayerRole
from app.models.game import Game
from app.models.game_player import GamePlayer
from app.models.group import Group
from app.models.user import User

__all__ = [
    "Base",
    "GameEndReason",
    "GameWinner",
    "PlayerRole",
    "Game",
    "GamePlayer",
    "Group",
    "User",
]
