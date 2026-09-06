"""Background timer that auto-deletes a lobby that never got started."""

from __future__ import annotations

import asyncio

from aiogram import Bot

from app.domain.game_state import GameStatus
from app.repositories.game_state_repository import GameStateRepository
from app.utils.logging import get_logger
from app.utils.telegram_helpers import safe_delete_message, safe_send_message

logger = get_logger(__name__)

_background_tasks: set[asyncio.Task] = set()

NOTICE_TEXT = "⏰ بازی به علت شروع نشدن پس از پنج دقیقه، به‌صورت خودکار حذف شد."
NOTICE_LIFETIME_SECONDS = 60


def start_lobby_timeout(
    bot: Bot, repo: GameStateRepository, chat_id: int, timeout_seconds: int
) -> None:
    """Fire-and-forget: schedule the lobby-expiry check for this chat."""
    task = asyncio.create_task(
        _lobby_timeout_worker(bot, repo, chat_id, timeout_seconds)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _lobby_timeout_worker(
    bot: Bot, repo: GameStateRepository, chat_id: int, timeout_seconds: int
) -> None:
    try:
        await asyncio.sleep(timeout_seconds)

        game = await repo.get_game(chat_id)
        if game is None or game.status != GameStatus.LOBBY:
            return

        if game.lobby_message_id is not None:
            await safe_delete_message(bot, chat_id, game.lobby_message_id)

        await repo.force_delete_game(chat_id)
        logger.info("lobby_auto_deleted", chat_id=chat_id)

        notice = await safe_send_message(bot, chat_id, NOTICE_TEXT)
        if notice is None:
            return
        await asyncio.sleep(NOTICE_LIFETIME_SECONDS)
        await safe_delete_message(bot, chat_id, notice.message_id)
    except Exception:
        logger.exception("lobby_timeout_task_failed", chat_id=chat_id)
