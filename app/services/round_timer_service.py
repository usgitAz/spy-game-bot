"""In-process timer that ends the discussion round and opens voting.

Armed when the game starts. Sleeps for ``round_seconds``, then (if the
game is still RUNNING) hands off to ``open_voting_phase``, which
atomically transitions status and posts a single voting panel.

When the timer fires it transitions RUNNING → VOTING, **deletes** the old
role panel, and posts a **new** voting message so players see it at the
bottom of the chat without scrolling.
"""

from __future__ import annotations

import asyncio

from aiogram import Bot

from app.domain.game_state import GameStatus
from app.repositories.game_state_repository import GameStateRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


def start_round_timer(
    bot: Bot,
    repo: GameStateRepository,
    chat_id: int,
    delay: float,
    game_message_id: int | None,
) -> asyncio.Task:
    """Schedule the discussion-end worker; returns the background task."""
    return asyncio.create_task(
        _round_timer_worker(bot, repo, chat_id, delay, game_message_id),
        name=f"round-timer-{chat_id}",
    )


async def _round_timer_worker(
    bot: Bot,
    repo: GameStateRepository,
    chat_id: int,
    delay: float,
    game_message_id: int | None,
) -> None:
    try:
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
            logger.info("round_timer_fired", chat_id=chat_id)
    except Exception:
        logger.exception("round_timer_task_failed", chat_id=chat_id)
