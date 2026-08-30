"""Service layer for creating a new game lobby.

Kept thin for now, but this is the seam where future business logic
(e.g. upserting the Group/User rows in Postgres on first contact) will
go without handlers needing to change.
"""

from app.domain.game_state import GameSettings, GameState
from app.repositories.game_state_repository import GameStateRepository


async def create_new_game(
    repo: GameStateRepository,
    *,
    chat_id: int,
    creator_id: int,
    creator_name: str,
    settings: GameSettings,
    ttl_seconds: int,
) -> GameState:
    """Create a new lobby and return its freshly read state.

    Raises `GameAlreadyExistsError` (propagated from the repository) if
    another game is already active in this chat.
    """
    await repo.create_game(
        chat_id=chat_id,
        creator_id=creator_id,
        creator_name=creator_name,
        settings=settings,
        ttl_seconds=ttl_seconds,
    )
    game = await repo.get_game(chat_id)
    assert game is not None, "game must exist immediately after create_game()"
    return game
