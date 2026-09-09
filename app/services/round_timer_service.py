"""In-process timer that ends the discussion round and opens voting.

Armed when the game starts with the Redis discussion **deadline**
(``ends_at`` unix timestamp). Sleeps until that moment, then (if the
game is still RUNNING) hands off to ``open_voting_phase``, which
atomically transitions status and posts a single voting panel.

The recovery sweeper is a safety net if this task is lost after a
process restart; under normal operation this timer should fire first.
"""

from __future__ import annotations

import asyncio
import time

from aiogram import Bot

from app.domain.game_state import GameStatus
from app.repositories.game_state_repository import GameStateRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


def start_round_timer(
    bot: Bot,
    repo: GameStateRepository,
    chat_id: int,
    ends_at: float,
    game_message_id: int | None,
) -> asyncio.Task:
    """Schedule the discussion-end worker for absolute deadline ``ends_at``.

    ``ends_at`` is a Unix timestamp (same value stored in Redis meta),
    not a relative duration in seconds.
    """
    return asyncio.create_task(
        _round_timer_worker(bot, repo, chat_id, ends_at, game_message_id),
        name=f"round-timer-{chat_id}",
    )


async def _round_timer_worker(
    bot: Bot,
    repo: GameStateRepository,
    chat_id: int,
    ends_at: float,
    game_message_id: int | None,
) -> None:
    try:
        delay = max(0.0, ends_at - time.time())
        await asyncio.sleep(delay)

        game = await repo.get_game(chat_id)
        if game is None or game.status != GameStatus.RUNNING:
            # Already moved on (spy guessed early, game deleted, …).
            return

        from app.services.voting_service import open_voting_phase

        opened = await open_voting_phase(
            bot,
            repo,
            chat_id,
            fallback_message_id=game_message_id,
        )
        if opened:
            logger.info(
                "round_timer_fired",
                chat_id=chat_id,
                ends_at=ends_at,
                slept=delay,
            )
    except Exception:
        logger.exception("round_timer_task_failed", chat_id=chat_id)
