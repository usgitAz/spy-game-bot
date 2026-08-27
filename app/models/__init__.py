"""Import every model so `Base.metadata` is fully populated.

Alembic's `env.py` imports `Base` from `app.models.base`; importing this
package ensures every table is registered on that metadata before
autogenerate compares it against the database.
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
