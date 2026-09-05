"""Application entrypoint: wires everything together and starts polling."""

import asyncio

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.bot.bootstrap import create_bot, create_dispatcher
from app.config.settings import get_settings
from app.handlers.admin import router as admin_router
from app.handlers.chat_member import router as chat_member_router
from app.handlers.create_game import router as create_game_router
from app.handlers.game import router as game_router
from app.handlers.lobby import router as lobby_router
from app.handlers.spy_guess import router as spy_guess_router
from app.handlers.voting import router as voting_router
from app.repositories.game_state_repository import GameStateRepository
from app.services.game_recovery_service import start_game_recovery_sweeper
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
    # that declares a `repo: GameStateRepository` parameter.
    dispatcher["repo"] = GameStateRepository(get_redis())

    dispatcher.include_router(root_router)
    dispatcher.include_router(create_game_router)
    dispatcher.include_router(lobby_router)
    dispatcher.include_router(game_router)
    dispatcher.include_router(
        admin_router
    )  # before spy_guess so /commands are not swallowed
    dispatcher.include_router(voting_router)
    dispatcher.include_router(spy_guess_router)
    dispatcher.include_router(chat_member_router)

    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)

    # Redis-backed timer recovery (survives process restarts).
    start_game_recovery_sweeper(bot, GameStateRepository(get_redis()))

    logger.info("bot_starting")
    await bot.delete_webhook(drop_pending_updates=True)
    # Ensure chat_member updates are received (leave / kick / bot removed).
    await dispatcher.start_polling(
        bot, allowed_updates=dispatcher.resolve_used_update_types()
    )


if __name__ == "__main__":
    asyncio.run(main())
