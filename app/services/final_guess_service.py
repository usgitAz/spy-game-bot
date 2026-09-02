"""30-second final-guess window after a spy is voted out."""

from __future__ import annotations

import asyncio
import time

from aiogram import Bot

from app.config.settings import get_settings
from app.domain.game_state import GameStatus
from app.models.enums import GameEndReason, GameWinner
from app.repositories.game_state_repository import GameStateRepository
from app.services.game_end_service import end_game
from app.utils.logging import get_logger

logger = get_logger(__name__)

_background_tasks: set[asyncio.Task] = set()


def start_final_guess_window(
    bot: Bot,
    repo: GameStateRepository,
    chat_id: int,
    spy_user_id: int,
) -> None:
    """Persist deadline in Redis and schedule the in-process timeout."""
    seconds = get_settings().final_guess_seconds
    ends_at = time.time() + seconds

    async def _arm() -> None:
        await repo.set_final_guess_deadline(chat_id, ends_at)

    # Fire-and-forget the Redis write, then sleep.
    async def _run() -> None:
        try:
            await repo.set_final_guess_deadline(chat_id, ends_at)
            await asyncio.sleep(seconds)
            game = await repo.get_game(chat_id)
            if game is None or game.status != GameStatus.AWAITING_FINAL_GUESS:
                return
            await end_game(
                bot,
                repo,
                game,
                winner=GameWinner.CITIZENS,
                reason=GameEndReason.SPY_VOTED_OUT_WRONG_GUESS,
                announce=True,
            )
            logger.info("final_guess_timeout", chat_id=chat_id, spy_id=spy_user_id)
        except Exception:
            logger.exception("final_guess_task_failed", chat_id=chat_id)

    task = asyncio.create_task(_run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
