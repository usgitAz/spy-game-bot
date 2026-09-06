"""Bot and Dispatcher construction.

FSM storage uses the same Redis instance style as game state. Live game
data is managed via ``GameStateRepository``; FSM storage is only what
aiogram needs for its dispatcher plumbing.
"""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from app.config.settings import Settings
from app.utils.redis_client import build_redis


def create_bot(settings: Settings) -> Bot:
    proxy = settings.telegram_proxy or None
    session = AiohttpSession(proxy=proxy)

    return Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(settings: Settings) -> Dispatcher:
    # Do not use RedisStorage.from_url alone — that connection would still
    # try MAINT_NOTIFICATIONS on older Redis and spam the logs.
    redis = build_redis(settings.redis_dsn, decode_responses=True)
    storage = RedisStorage(redis=redis)
    return Dispatcher(storage=storage)
