"""Background timer that auto-deletes a lobby that never got started.

Implemented as a plain asyncio task (not persisted), scheduled once when
a game is created. If the bot restarts mid-countdown, the generous Redis
safety-net TTL (`settings.redis_game_ttl_seconds`) still guarantees the
underlying keys eventually disappear -- this task only adds the polished
UX (a notice message, then its own cleanup) on top of that guarantee.
"""

import asyncio

from aiogram import Bot

from app.domain.game_state import GameStatus
from app.repositories.game_state_repository import GameStateRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Keep strong references to scheduled tasks so they aren't garbage
# collected mid-flight (a well-known asyncio footgun with fire-and-forget
# tasks).
_background_tasks: set[asyncio.Task] = set()

NOTICE_TEXT = "⏰ بازی به علت شروع نشدن پس از دو دقیقه، به‌صورت خودکار حذف شد."
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
            # Already started, deleted, or otherwise moved on -- nothing to do.
            return

        if game.lobby_message_id is not None:
            try:
                await bot.delete_message(chat_id, game.lobby_message_id)
            except Exception:  # noqa: BLE001 -- message may already be gone
                pass

        await repo.force_delete_game(chat_id)
        logger.info("lobby_auto_deleted", chat_id=chat_id)

        notice = await bot.send_message(chat_id, NOTICE_TEXT)
        await asyncio.sleep(NOTICE_LIFETIME_SECONDS)
        try:
            await bot.delete_message(chat_id, notice.message_id)
        except Exception:  # noqa: BLE001 -- message may already be gone
            pass
    except Exception:
        logger.exception("lobby_timeout_task_failed", chat_id=chat_id)
