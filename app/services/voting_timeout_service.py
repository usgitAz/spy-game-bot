"""1-minute timer that closes voting even if not everyone has voted."""

from __future__ import annotations

import asyncio

from aiogram import Bot

from app.config.settings import get_settings
from app.domain.game_state import GameStatus
from app.repositories.game_state_repository import GameStateRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)

_background_tasks: set[asyncio.Task] = set()


def start_voting_timeout(
    bot: Bot,
    repo: GameStateRepository,
    chat_id: int,
) -> None:
    """Arm the voting-phase deadline (default 60 seconds)."""
    seconds = get_settings().voting_timeout_seconds
    task = asyncio.create_task(_voting_timeout_worker(bot, repo, chat_id, seconds))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _voting_timeout_worker(
    bot: Bot,
    repo: GameStateRepository,
    chat_id: int,
    seconds: int,
) -> None:
    try:
        await asyncio.sleep(seconds)
        game = await repo.get_game(chat_id)
        if game is None or game.status != GameStatus.VOTING:
            return
        logger.info("voting_timeout_fired", chat_id=chat_id)
        # Lazy import to avoid a circular dependency with voting_service.
        from app.services.voting_service import resolve_voting

        await resolve_voting(bot, repo, chat_id)
    except Exception:
        logger.exception("voting_timeout_task_failed", chat_id=chat_id)
