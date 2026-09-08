"""Helpers for checking (and caching) the bot's admin rights in a chat.

``bot_is_group_admin`` runs on essentially every group message and
callback (see ``app.middlewares.bot_admin``), so it must not hit the
Telegram API each time — that would burn rate limits under real chat
traffic and add latency even when no game is running.

The result is cached in Redis per ``chat_id`` and kept fresh two ways:

1. **Proactively:** ``app.handlers.chat_member`` calls ``set_admin_cache``
   from each ``my_chat_member`` update using the status Telegram already
   sent — no extra API call on the common path.
2. **Reactively:** a short TTL (``settings.bot_admin_cache_ttl_seconds``)
   is a safety net if an update was ever missed.

Redis (not an in-process dict) survives bot restarts, so a fresh process
does not re-verify every chat from scratch before normal operation.
"""

from __future__ import annotations

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from redis.asyncio import Redis

from app.config.settings import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

_ADMIN_STATUSES = {
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.CREATOR,
    "administrator",
    "creator",
}

_CACHE_PREFIX = "spy:botadmin"

BOT_NOT_ADMIN_TEXT = (
    "⚠️ برای کار کردن این ربات باید آن را <b>ادمین گروه</b> کنید.\n\n"
    "حداقل دسترسی لازم: فقط وضعیت ادمین "
    "(برای دیدن خروج اعضا و مدیریت پیام‌های بازی).\n\n"
    "بعد از ادمین کردن، دوباره دستور را بزنید."
)

# Bot numeric id never changes for the life of the process.
_bot_id_cache: int | None = None


def _cache_key(chat_id: int) -> str:
    return f"{_CACHE_PREFIX}:{chat_id}"


async def _get_bot_id(bot: Bot) -> int:
    global _bot_id_cache
    if _bot_id_cache is None:
        me = await bot.get_me()
        _bot_id_cache = me.id
    return _bot_id_cache


async def _fetch_bot_admin_status(bot: Bot, chat_id: int) -> bool:
    """Ask Telegram directly. Only called on a cache miss."""
    try:
        bot_id = await _get_bot_id(bot)
        member = await bot.get_chat_member(chat_id, bot_id)
    except Exception:
        logger.exception("bot_admin_check_failed", chat_id=chat_id)
        # Fail closed: treat as not-admin so we do not run game logic blindly.
        return False
    return member.status in _ADMIN_STATUSES


async def bot_is_group_admin(bot: Bot, redis: Redis, chat_id: int) -> bool:
    """Return True if the bot is administrator (or creator) in ``chat_id``.

    Reads Redis first; only calls Telegram on a cache miss (first message
    in a chat, TTL expiry, or after restart before any ``my_chat_member``).
    """
    key = _cache_key(chat_id)
    cached = await redis.get(key)
    if cached is not None:
        # redis client may return str or bytes depending on decode_responses
        value = cached.decode() if isinstance(cached, bytes) else cached
        return value == "1"

    is_admin = await _fetch_bot_admin_status(bot, chat_id)
    await set_admin_cache(redis, chat_id, is_admin)
    return is_admin


async def set_admin_cache(redis: Redis, chat_id: int, is_admin: bool) -> None:
    """Proactively write known status (from ``my_chat_member``)."""
    ttl = get_settings().bot_admin_cache_ttl_seconds
    await redis.set(_cache_key(chat_id), "1" if is_admin else "0", ex=ttl)


async def invalidate_admin_cache(redis: Redis, chat_id: int) -> None:
    """Drop cached value so the next check re-fetches from Telegram."""
    await redis.delete(_cache_key(chat_id))
