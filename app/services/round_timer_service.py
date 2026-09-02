"""Background timer that fires when a running round's time is up.

Mirrors ``lobby_timeout_service``: a fire-and-forget asyncio task scheduled
at game start.  If the bot restarts mid-round the Redis ``ends_at`` field
still lets a future recovery path re-arm the timer; this task only covers
the happy path while the process stays up.

When the timer fires it transitions RUNNING → VOTING, **deletes** the old
in-progress game panel (so it does not stay buried under chat messages),
and posts a fresh voting panel at the bottom of the chat.
"""

from __future__ import annotations

import asyncio
import time

from aiogram import Bot

from app.config.settings import get_settings
from app.domain.game_state import GameStatus
from app.keyboards import build_voting_keyboard
from app.repositories.game_state_repository import GameStateRepository
from app.services.voting_timeout_service import start_voting_timeout
from app.utils.formatting import build_voting_message_text
from app.utils.logging import get_logger

logger = get_logger(__name__)

_background_tasks: set[asyncio.Task] = set()


def start_round_timer(
    bot: Bot,
    repo: GameStateRepository,
    chat_id: int,
    ends_at: float,
    game_message_id: int,
) -> None:
    """Schedule the round-expiry worker for this chat."""
    delay = max(0.0, ends_at - time.time())
    task = asyncio.create_task(
        _round_timer_worker(bot, repo, chat_id, delay, game_message_id)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _round_timer_worker(
    bot: Bot,
    repo: GameStateRepository,
    chat_id: int,
    delay: float,
    game_message_id: int,
) -> None:
    try:
        await asyncio.sleep(delay)

        game = await repo.get_game(chat_id)
        if game is None or game.status != GameStatus.RUNNING:
            # Already moved on (spy guessed early, game deleted, …).
            return

        voting_ends = time.time() + get_settings().voting_timeout_seconds
        await repo.set_voting_deadline(chat_id, voting_ends)
        game = await repo.get_game(chat_id)
        assert game is not None

        # Prefer the message id stored on the game state (may have been
        # refreshed); fall back to the one captured when the timer was armed.
        old_message_id = game.game_message_id or game_message_id

        # Remove the old "see my role" panel so it is not left buried
        # under the discussion messages.
        if old_message_id is not None:
            try:
                await bot.delete_message(chat_id, old_message_id)
            except Exception:  # noqa: BLE001 — already gone / no permission
                pass

        active = [p for p in game.players if not p.eliminated and not p.left_mid_game]
        text = build_voting_message_text(game)
        keyboard = build_voting_keyboard(chat_id, active)

        sent = await bot.send_message(chat_id, text, reply_markup=keyboard)
        await repo.set_message_id(chat_id, game_message_id=sent.message_id)

        # 1-minute deadline: resolve even if some players never vote.
        start_voting_timeout(bot, repo, chat_id)

        logger.info(
            "round_timer_fired",
            chat_id=chat_id,
            active_players=len(active),
            voting_message_id=sent.message_id,
        )
    except Exception:
        logger.exception("round_timer_task_failed", chat_id=chat_id)
