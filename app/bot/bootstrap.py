"""Bot and Dispatcher construction.

The FSM storage is backed by Redis so that game state, lobby membership,
timers, and votes survive bot restarts and can be shared safely across
concurrent updates for multiple groups.
"""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from app.config.settings import Settings


def create_bot(settings: Settings) -> Bot:
    proxy = settings.telegram_proxy or None
    session = AiohttpSession(proxy=proxy)

    return Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(settings: Settings) -> Dispatcher:
    storage = RedisStorage.from_url(settings.redis_dsn)
    return Dispatcher(storage=storage)
