"""Application entrypoint: wires everything together and starts polling."""

import asyncio
from pathlib import Path

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.bot.bootstrap import create_bot, create_dispatcher
from app.config.settings import BASE_DIR, get_settings
from app.handlers.admin import router as admin_router
from app.handlers.chat_member import router as chat_member_router
from app.handlers.create_game import router as create_game_router
from app.handlers.game import router as game_router
from app.handlers.lobby import router as lobby_router
from app.handlers.spy_guess import router as spy_guess_router
from app.handlers.voting import router as voting_router
from app.middlewares.bot_admin import BotAdminMiddleware
from app.middlewares.throttle import ThrottleMiddleware
from app.repositories.game_state_repository import GameStateRepository
from app.services.game_recovery_service import start_game_recovery_sweeper
from app.utils.logging import configure_logging, get_logger
from app.utils.redis_client import close_redis, get_redis

root_router = Router(name="root")


@root_router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """Basic health-check handler, confirming the bot is wired up correctly."""
    await message.answer(
        "ربات جاسوس آماده است ✅\n"
        "برای ساخت بازی جدید در یک گروه، دستور /newgame را بزنید."
    )


async def on_startup() -> None:
    """Verify external dependencies required at runtime (Redis only for now)."""
    log = get_logger(__name__)
    # TODO: re-enable Postgres connectivity check when game archival
    # and user stats are implemented.
    redis = get_redis()
    await redis.ping()
    log.info("redis_connection_ok")
    log.info("startup_complete")


async def on_shutdown() -> None:
    """Gracefully release external resources."""
    log = get_logger(__name__)
    await close_redis()
    # TODO: dispose SQLAlchemy engine when Postgres is re-enabled.
    log.info("shutdown_complete")


async def main() -> None:
    settings = get_settings()

    log_path = Path(settings.log_dir)
    if not log_path.is_absolute():
        log_path = BASE_DIR / log_path

    configure_logging(
        settings.log_level,
        logs_dir=log_path,
        max_bytes=settings.log_max_bytes,
        backup_count=settings.log_backup_count,
    )
    log = get_logger(__name__)

    bot = create_bot(settings)
    dispatcher = create_dispatcher(settings)

    # Shared, process-wide repository instance injected into every handler
    # that declares a `repo: GameStateRepository` parameter.
    dispatcher["repo"] = GameStateRepository(get_redis())

    # Rate-limit first (cheap), then require bot admin in groups.
    dispatcher.message.middleware(ThrottleMiddleware())
    dispatcher.callback_query.middleware(ThrottleMiddleware())
    dispatcher.message.middleware(BotAdminMiddleware())
    dispatcher.callback_query.middleware(BotAdminMiddleware())

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

    log.info("bot_starting", logs_dir=str(log_path))
    await bot.delete_webhook(drop_pending_updates=True)
    # Ensure chat_member updates are received (leave / kick / bot removed).
    await dispatcher.start_polling(
        bot, allowed_updates=dispatcher.resolve_used_update_types()
    )


if __name__ == "__main__":
    asyncio.run(main())
