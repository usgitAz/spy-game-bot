"""Bot and Dispatcher construction.

The FSM storage is backed by Redis so that game state, lobby membership,
timers, and votes survive bot restarts and can be shared safely across
concurrent updates for multiple groups.
"""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from app.config.settings import Settings


def create_bot(settings: Settings) -> Bot:
    """Create the aiogram `Bot` instance with sane default properties."""
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(settings: Settings) -> Dispatcher:
    """Create the aiogram `Dispatcher` with Redis-backed FSM storage."""
    storage = RedisStorage.from_url(settings.redis_dsn)
    return Dispatcher(storage=storage)
