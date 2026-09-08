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
from app.utils.logging import get_logger
from app.utils.redis_client import build_redis

logger = get_logger(__name__)


class TelegramProxyNotAllowedInProduction(RuntimeError):
    """Raised when TELEGRAM_PROXY is set while APP_ENV is production."""


def resolve_telegram_proxy(settings: Settings) -> str | None:
    """Return a proxy URL for non-production only.

    - Empty / missing ``TELEGRAM_PROXY`` → no proxy.
    - Production + proxy set → fail fast with a clear error (do not start).
    - development / local + proxy set → use the proxy.
    """
    proxy = (settings.telegram_proxy or "").strip() or None
    if not proxy:
        return None

    env = (getattr(settings, "app_env", None) or "production").strip().lower()
    if env in {"production", "prod"}:
        raise TelegramProxyNotAllowedInProduction(
            "TELEGRAM_PROXY is set but APP_ENV is production. "
            "Proxy is not allowed in production — unset TELEGRAM_PROXY "
            "in your .env (or set APP_ENV=development only for local use). "
            f"Current proxy value: {proxy!r}"
        )

    logger.info("telegram_proxy_enabled", proxy=proxy, app_env=env)
    return proxy


def create_bot(settings: Settings) -> Bot:
    proxy = resolve_telegram_proxy(settings)
    session = AiohttpSession(proxy=proxy) if proxy else AiohttpSession()

    return Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(settings: Settings) -> Dispatcher:
    redis = build_redis(settings.redis_dsn, decode_responses=True)
    storage = RedisStorage(redis=redis)
    return Dispatcher(storage=storage)
