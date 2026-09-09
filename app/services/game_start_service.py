"""Orchestrate the transition from LOBBY → RUNNING.

Steps:
1. Validate the lobby is still startable (read).
2. Atomically claim LOBBY → STARTING (only one concurrent Start wins).
3. Pick a random word and assign spy/citizen roles.
4. Persist roles, then STARTING → RUNNING with word + deadline.
5. Return the updated GameState so the handler can render the panel.
"""

from __future__ import annotations

from app.domain.game_state import GameState, GameStatus
from app.models.enums import PlayerRole
from app.repositories.game_state_repository import GameStateRepository
from app.services.role_assignment import assign_roles
from app.services.word_bank import pick_word
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GameStartError(Exception):
    """Base class for start-time validation failures."""


class NotInLobbyError(GameStartError):
    pass


class AlreadyStartingError(GameStartError):
    """Another concurrent start already claimed this lobby."""


class NotEnoughPlayersError(GameStartError):
    def __init__(self, current: int, required: int) -> None:
        self.current = current
        self.required = required
        super().__init__(f"need {required}, have {current}")


class NotCreatorError(GameStartError):
    pass


async def start_game(
    repo: GameStateRepository,
    *,
    chat_id: int,
    requester_id: int,
    min_players: int,
) -> GameState:
    """Validate, claim start, assign roles/word, and flip the game to RUNNING.

    Raises one of the ``GameStartError`` subclasses on validation failure.
    """
    game = await repo.get_game(chat_id)
    if game is None or game.status != GameStatus.LOBBY:
        raise NotInLobbyError(chat_id)
    if requester_id != game.creator_id:
        raise NotCreatorError(requester_id)
    if game.player_count < min_players:
        raise NotEnoughPlayersError(game.player_count, min_players)

    # Atomic claim: second concurrent Start sees status != lobby and loses.
    if not await repo.try_claim_start(chat_id):
        raise AlreadyStartingError(chat_id)

    word = pick_word()
    roles = assign_roles(game.players, game.settings)
    actual_spies = sum(1 for p in roles.values() if p.role == PlayerRole.SPY)

    await repo.set_player_roles(chat_id, roles)
    ends_at = await repo.complete_start(
        chat_id,
        word=word,
        round_seconds=game.settings.round_seconds,
        spies_count=actual_spies,
    )

    # Re-read so the caller gets a fully consistent snapshot.
    updated = await repo.get_game(chat_id)
    assert updated is not None
    assert updated.status == GameStatus.RUNNING
    assert updated.word == word
    assert updated.ends_at == ends_at

    spy_ids = [p.user_id for p in updated.spies]
    logger.info(
        "game_started",
        chat_id=chat_id,
        player_count=updated.player_count,
        spies_count=len(spy_ids),
        spy_ids=spy_ids,
        round_seconds=game.settings.round_seconds,
        ends_at=ends_at,
        # Never log the actual word — it must stay secret.
    )
    return updated
