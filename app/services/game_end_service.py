"""End a live game: announce the result and clear Redis state.

Live-side cleanup only (Redis). Persistent archival into Postgres is
deferred — see TODO.md (stage 10).
"""

from __future__ import annotations

from aiogram import Bot

from app.domain.game_state import GameState
from app.models.enums import GameEndReason, GameWinner
from app.repositories.game_state_repository import GameStateRepository
from app.utils.formatting import build_game_over_text
from app.utils.logging import get_logger
from app.utils.telegram_helpers import safe_delete_message, safe_send_message

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
        await safe_delete_message(bot, chat_id, msg_id)

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
        await safe_send_message(bot, chat_id, text)

    logger.info(
        "game_ended",
        chat_id=chat_id,
        winner=winner.value,
        reason=reason.value,
        player_count=game.player_count,
        deleted_keys=deleted,
    )
    return True
