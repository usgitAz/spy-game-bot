"""End a live game: announce the result and clear Redis state.

Full archival into Postgres (Game / GamePlayer rows, user stats) lands in
stage 10.  This service only handles the live-side cleanup so the group
can start a new game immediately.
"""

from __future__ import annotations

from aiogram import Bot

from app.domain.game_state import GameState
from app.models.enums import GameEndReason, GameWinner
from app.repositories.game_state_repository import GameStateRepository
from app.utils.formatting import build_game_over_text
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def end_game(
    bot: Bot,
    repo: GameStateRepository,
    game: GameState,
    *,
    winner: GameWinner,
    reason: GameEndReason,
    announce: bool = True,
) -> bool:
    """Clear Redis, then announce at most once.

    Returns True if this call was the one that actually ended the game
    (deleted live keys). Concurrent callers (final-guess timer and the
    recovery sweeper often race) get False and must not announce again.
    """
    chat_id = game.chat_id

    for msg_id in (game.game_message_id, game.lobby_message_id):
        if msg_id is None:
            continue
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception:  # noqa: BLE001
            pass

    deleted = await repo.force_delete_game(chat_id)
    if deleted == 0:
        logger.info(
            "game_end_skipped_already_gone",
            chat_id=chat_id,
            winner=winner.value,
            reason=reason.value,
        )
        return False

    if announce:
        text = build_game_over_text(game, winner=winner, reason=reason)
        try:
            await bot.send_message(chat_id, text)
        except Exception:  # noqa: BLE001
            logger.exception("game_over_announce_failed", chat_id=chat_id)

    logger.info(
        "game_ended",
        chat_id=chat_id,
        winner=winner.value,
        reason=reason.value,
        player_count=game.player_count,
        deleted_keys=deleted,
    )
    return True
