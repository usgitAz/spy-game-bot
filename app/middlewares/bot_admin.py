"""Block group usage until the bot is promoted to administrator."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.utils.bot_permissions import BOT_NOT_ADMIN_TEXT, bot_is_group_admin
from app.utils.formatting import force_rtl
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Avoid spamming the same warning into a chat more than once per window.
_WARN_COOLDOWN_SECONDS = 30
_last_warn_at: dict[int, float] = {}


def _is_group(chat_type: str | None) -> bool:
    return chat_type in (ChatType.GROUP, ChatType.SUPERGROUP, "group", "supergroup")


async def _maybe_warn(bot: Bot, chat_id: int) -> None:
    now = time.time()
    last = _last_warn_at.get(chat_id, 0.0)
    if now - last < _WARN_COOLDOWN_SECONDS:
        return
    _last_warn_at[chat_id] = now
    try:
        await bot.send_message(chat_id, force_rtl(BOT_NOT_ADMIN_TEXT))
    except Exception:  # noqa: BLE001
        logger.exception("bot_not_admin_warn_failed", chat_id=chat_id)


class BotAdminMiddleware(BaseMiddleware):
    """For group messages & callbacks: require the bot to be an admin."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        bot: Bot = data["bot"]
        redis = data["redis"]
        chat = None
        is_callback = False

        if isinstance(event, Message):
            chat = event.chat
        elif isinstance(event, CallbackQuery):
            is_callback = True
            if event.message is not None:
                chat = event.message.chat

        if chat is None or not _is_group(chat.type):
            return await handler(event, data)

        if await bot_is_group_admin(bot, redis, chat.id):
            return await handler(event, data)

        logger.info("blocked_not_admin", chat_id=chat.id)

        if is_callback and isinstance(event, CallbackQuery):
            try:
                await event.answer(
                    "ربات باید ادمین گروه باشد.",
                    show_alert=True,
                )
            except Exception:  # noqa: BLE001
                pass

        await _maybe_warn(bot, chat.id)
        return None
