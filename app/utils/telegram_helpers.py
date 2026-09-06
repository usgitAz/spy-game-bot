"""Safe Telegram Bot API helpers with light retry."""

from __future__ import annotations

import asyncio
from typing import Any

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import InlineKeyboardMarkup, Message

from app.utils.logging import get_logger

logger = get_logger(__name__)

_MAX_ATTEMPTS = 3
_TRANSIENT = (TelegramNetworkError, TelegramServerError)


async def _retry(call_name: str, factory):
    """Run an async API call with retries on transient / flood errors."""
    last_exc: BaseException | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return await factory()
        except TelegramRetryAfter as exc:
            last_exc = exc
            delay = float(exc.retry_after) + 0.1
            logger.warning(
                "telegram_retry_after",
                call=call_name,
                attempt=attempt,
                retry_after=exc.retry_after,
            )
            await asyncio.sleep(delay)
        except _TRANSIENT as exc:
            last_exc = exc
            if attempt >= _MAX_ATTEMPTS:
                break
            delay = 0.4 * attempt
            logger.warning(
                "telegram_transient_retry",
                call=call_name,
                attempt=attempt,
                error=type(exc).__name__,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


async def safe_send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    **kwargs: Any,
) -> Message | None:
    """Send a message; retry on flood/network; return None on hard failure."""

    async def _call() -> Message:
        return await bot.send_message(
            chat_id, text, reply_markup=reply_markup, **kwargs
        )

    try:
        return await _retry("send_message", _call)
    except Exception:
        logger.exception("safe_send_message_failed", chat_id=chat_id)
        return None


async def safe_delete_message(bot: Bot, chat_id: int, message_id: int) -> bool:
    """Delete a message; ignore 'already gone'; retry transient errors."""

    async def _call() -> None:
        await bot.delete_message(chat_id, message_id)

    try:
        await _retry("delete_message", _call)
        return True
    except TelegramBadRequest as exc:
        # Message missing / not found / can't delete — not actionable.
        logger.debug(
            "safe_delete_message_ignored",
            chat_id=chat_id,
            message_id=message_id,
            error=str(exc),
        )
        return False
    except Exception:
        logger.exception(
            "safe_delete_message_failed",
            chat_id=chat_id,
            message_id=message_id,
        )
        return False


async def safe_edit_text(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """Edit message text; ignore 'not modified'; retry transient errors."""

    async def _call() -> None:
        await message.edit_text(text, reply_markup=reply_markup)

    try:
        await _retry("edit_text", _call)
        return True
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return True
        logger.debug("safe_edit_text_ignored", error=str(exc))
        return False
    except Exception:
        logger.exception("safe_edit_text_failed", chat_id=message.chat.id)
        return False


async def safe_edit_message_text(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """Edit by chat/message id (when we only stored ids in Redis)."""

    async def _call() -> None:
        await bot.edit_message_text(
            text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )

    try:
        await _retry("edit_message_text", _call)
        return True
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return True
        logger.debug(
            "safe_edit_message_text_ignored",
            chat_id=chat_id,
            message_id=message_id,
            error=str(exc),
        )
        return False
    except Exception:
        logger.exception(
            "safe_edit_message_text_failed",
            chat_id=chat_id,
            message_id=message_id,
        )
        return False
