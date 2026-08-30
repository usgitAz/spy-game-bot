"""Application entrypoint: wires everything together and starts polling."""

import asyncio

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.bot.bootstrap import create_bot, create_dispatcher
from app.config.settings import get_settings
from app.handlers.create_game import router as create_game_router
from app.repositories.game_state_repository import GameStateRepository
from app.utils.db import dispose_engine, get_engine
from app.utils.logging import configure_logging, get_logger
from app.utils.redis_client import close_redis, get_redis

logger = get_logger(__name__)

root_router = Router(name="root")


@root_router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """Basic health-check handler, confirming the bot is wired up correctly."""
    await message.answer(
        "ربات جاسوس آماده است ✅\n"
        "برای ساخت بازی جدید در یک گروه، دستور /newgame را بزنید."
    )


async def on_startup() -> None:
    """Verify external dependencies (Postgres, Redis) are reachable."""
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.run_sync(lambda _: None)
    logger.info("postgres_connection_ok")

    redis = get_redis()
    await redis.ping()
    logger.info("redis_connection_ok")

    logger.info("startup_complete")


async def on_shutdown() -> None:
    """Gracefully release external resources."""
    await close_redis()
    await dispose_engine()
    logger.info("shutdown_complete")


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    bot = create_bot(settings)
    dispatcher = create_dispatcher(settings)

    # Shared, process-wide repository instance injected into every handler
    # that declares a repo: GameStateRepository parameter.
    dispatcher["repo"] = GameStateRepository(get_redis())

    dispatcher.include_router(root_router)
    dispatcher.include_router(create_game_router)

    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)

    logger.info("bot_starting")
    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
