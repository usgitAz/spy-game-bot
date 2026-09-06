"""Simple per-user rate limiting for callbacks and bot commands.

Protects the process and the Telegram API from button-mashing / command spam
without blocking ordinary group chat (spy-guess messages are not throttled).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config.settings import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

# In-process buckets: key -> monotonic timestamp of last accepted event.
_last_hit: dict[str, float] = {}
# Soft cap so a long-running process does not grow without bound.
_MAX_BUCKETS = 20_000


def _prune_if_needed(now: float, window: float) -> None:
    if len(_last_hit) < _MAX_BUCKETS:
        return
    cutoff = now - max(window * 4, 30.0)
    stale = [k for k, ts in _last_hit.items() if ts < cutoff]
    for k in stale:
        _last_hit.pop(k, None)
    # Absolute safety: if still huge, drop oldest half.
    if len(_last_hit) >= _MAX_BUCKETS:
        ordered = sorted(_last_hit.items(), key=lambda kv: kv[1])
        for k, _ in ordered[: len(ordered) // 2]:
            _last_hit.pop(k, None)


def _is_rate_limited(key: str, min_interval: float) -> bool:
    """Return True if this key must be rejected (too soon after last hit)."""
    now = time.monotonic()
    _prune_if_needed(now, min_interval)
    last = _last_hit.get(key)
    if last is not None and (now - last) < min_interval:
        return True
    _last_hit[key] = now
    return False


class ThrottleMiddleware(BaseMiddleware):
    """Drop rapid repeat taps on the same user for buttons and commands."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        settings = get_settings()

        if isinstance(event, CallbackQuery):
            user = event.from_user
            if user is None:
                return await handler(event, data)

            # Per-user across all chats: one button family at a time.
            key = f"cb:{user.id}"
            if _is_rate_limited(key, settings.throttle_callback_seconds):
                logger.debug("throttled_callback", user_id=user.id)
                try:
                    await event.answer("⏳ کمی صبر کنید…", show_alert=False)
                except Exception:  # noqa: BLE001
                    pass
                return None
            return await handler(event, data)

        if isinstance(event, Message):
            user = event.from_user
            text = (event.text or "").strip()
            # Only throttle slash-commands; normal chat must stay free for guesses.
            if user is None or not text.startswith("/"):
                return await handler(event, data)

            cmd = text.split()[0].split("@", 1)[0].lower()
            # Hot commands that hit Redis / create state.
            heavy = {
                "/newgame",
                "/deletecurrentgame",
                "/start",
            }
            interval = (
                settings.throttle_command_seconds
                if cmd in heavy
                else settings.throttle_callback_seconds
            )
            key = f"cmd:{user.id}:{cmd}"
            if _is_rate_limited(key, interval):
                logger.debug("throttled_command", user_id=user.id, cmd=cmd)
                # Silent drop — avoids flooding the group with "wait" replies.
                return None
            return await handler(event, data)

        return await handler(event, data)
