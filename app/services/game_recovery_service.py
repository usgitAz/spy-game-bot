"""Recover games whose in-process timers were lost (bot restart, network blip).

All deadlines live in Redis (``ends_at``, ``voting_ends_at``,
``final_guess_ends_at``).  A lightweight sweeper runs on startup and on a
short interval so a stuck game is advanced even if the original asyncio
task is gone.
"""

from __future__ import annotations

import asyncio
import time

from aiogram import Bot

from app.config.settings import get_settings
from app.domain.game_state import GameStatus
from app.keyboards import build_voting_keyboard
from app.models.enums import GameEndReason, GameWinner
from app.repositories.game_state_repository import GameStateRepository
from app.utils.formatting import build_voting_message_text
from app.utils.logging import get_logger

logger = get_logger(__name__)

_background_tasks: set[asyncio.Task] = set()
_SWEEP_INTERVAL_SECONDS = 15


def start_game_recovery_sweeper(bot: Bot, repo: GameStateRepository) -> None:
    """Launch the background sweeper (call once from on_startup)."""
    task = asyncio.create_task(_sweep_loop(bot, repo))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def recover_all_games(bot: Bot, repo: GameStateRepository) -> int:
    """Run one recovery pass over every live game. Returns number of fixes."""
    fixed = 0
    try:
        chat_ids = await repo.list_active_chat_ids()
    except Exception:
        logger.exception("recovery_scan_failed")
        return 0

    for chat_id in chat_ids:
        try:
            if await _recover_one(bot, repo, chat_id):
                fixed += 1
        except Exception:
            logger.exception("recovery_one_failed", chat_id=chat_id)
    if fixed:
        logger.info("recovery_pass_done", fixed=fixed, scanned=len(chat_ids))
    return fixed


async def _sweep_loop(bot: Bot, repo: GameStateRepository) -> None:
    # Immediate pass on startup (covers bot restarts mid-game).
    await recover_all_games(bot, repo)
    while True:
        await asyncio.sleep(_SWEEP_INTERVAL_SECONDS)
        await recover_all_games(bot, repo)


async def _recover_one(bot: Bot, repo: GameStateRepository, chat_id: int) -> bool:
    game = await repo.get_game(chat_id)
    if game is None:
        return False

    now = time.time()
    settings = get_settings()

    # --- LOBBY past lobby timeout ---
    if game.status == GameStatus.LOBBY:
        deadline = game.created_at + settings.lobby_timeout_seconds
        if now >= deadline:
            if game.lobby_message_id is not None:
                try:
                    await bot.delete_message(chat_id, game.lobby_message_id)
                except Exception:  # noqa: BLE001
                    pass
            await repo.force_delete_game(chat_id)
            try:
                await bot.send_message(
                    chat_id,
                    "⏰ بازی به علت شروع نشدن به‌صورت خودکار حذف شد.",
                )
            except Exception:  # noqa: BLE001
                pass
            logger.info("recovery_lobby_expired", chat_id=chat_id)
            return True
        return False

    # --- RUNNING past discussion deadline ---
    if game.status == GameStatus.RUNNING:
        if game.ends_at is None or now < game.ends_at:
            return False
        await _open_voting(bot, repo, chat_id)
        logger.info("recovery_opened_voting", chat_id=chat_id)
        return True

    # --- VOTING past voting deadline ---
    if game.status == GameStatus.VOTING:
        deadline = game.voting_ends_at
        if deadline is None:
            # Legacy / partial state: allow a grace window after ends_at.
            deadline = (game.ends_at or now) + settings.voting_timeout_seconds
        if now < deadline:
            return False
        from app.services.voting_service import resolve_voting

        await resolve_voting(bot, repo, chat_id)
        logger.info("recovery_resolved_voting", chat_id=chat_id)
        return True

    # --- FINAL GUESS past deadline ---
    if game.status == GameStatus.AWAITING_FINAL_GUESS:
        deadline = game.final_guess_ends_at
        # Only recover when a real deadline was persisted. Missing value
        # means mid-transition — do not invent a citizen win.
        if deadline is None or now < deadline:
            return False
        from app.services.game_end_service import end_game

        await end_game(
            bot,
            repo,
            game,
            winner=GameWinner.CITIZENS,
            reason=GameEndReason.SPY_VOTED_OUT_WRONG_GUESS,
            announce=True,
        )
        logger.info("recovery_final_guess_expired", chat_id=chat_id)
        return True

    return False


async def _open_voting(bot: Bot, repo: GameStateRepository, chat_id: int) -> None:
    """Same outcome as the round-timer worker: RUNNING → VOTING + panel."""
    from app.services.voting_timeout_service import start_voting_timeout

    settings = get_settings()
    voting_ends = time.time() + settings.voting_timeout_seconds
    await repo.set_voting_deadline(chat_id, voting_ends)

    game = await repo.get_game(chat_id)
    if game is None:
        return

    if game.game_message_id is not None:
        try:
            await bot.delete_message(chat_id, game.game_message_id)
        except Exception:  # noqa: BLE001
            pass

    active = [p for p in game.players if not p.eliminated and not p.left_mid_game]
    text = build_voting_message_text(game)
    keyboard = build_voting_keyboard(chat_id, active)
    try:
        sent = await bot.send_message(chat_id, text, reply_markup=keyboard)
        await repo.set_message_id(chat_id, game_message_id=sent.message_id)
    except Exception:
        logger.exception("recovery_voting_panel_failed", chat_id=chat_id)
        return

    start_voting_timeout(bot, repo, chat_id)
