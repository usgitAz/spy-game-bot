"""Handlers for the lobby panel: join, leave, delete, rules, and start."""

from collections.abc import Awaitable, Callable

from aiogram import Router
from aiogram.types import CallbackQuery

from app.config.settings import get_settings
from app.constants import GAME_RULES_TEXT
from app.keyboards import (
    LobbyAction,
    LobbyCallback,
    build_game_keyboard,
    build_lobby_keyboard,
)
from app.repositories.game_state_repository import (
    AlreadyJoinedError,
    CreatorCannotLeaveError,
    GameNotFoundError,
    GameStateRepository,
    LobbyFullError,
    NotAParticipantError,
    NotAuthorizedError,
    NotInLobbyError,
)
from app.services.game_start_service import (
    NotCreatorError,
    NotEnoughPlayersError,
    NotInLobbyError as GameStartNotInLobbyError,
    start_game,
)
from app.services.round_timer_service import start_round_timer
from app.utils.formatting import build_game_message_text, build_lobby_message_text
from app.utils.logging import get_logger
from app.utils.telegram_helpers import safe_edit_text

logger = get_logger(__name__)
router = Router(name="lobby")

ADMIN_STATUSES = {"administrator", "creator"}


async def _is_group_admin(callback: CallbackQuery, chat_id: int) -> bool:
    member = await callback.bot.get_chat_member(chat_id, callback.from_user.id)
    return member.status in ADMIN_STATUSES


async def _refresh_lobby_panel(
    callback: CallbackQuery, repo: GameStateRepository, chat_id: int
) -> None:
    """Re-render the lobby message with the current member list."""
    assert callback.message is not None
    game = await repo.get_game(chat_id)
    if game is None:
        return
    await safe_edit_text(
        callback.message, build_lobby_message_text(game), build_lobby_keyboard(chat_id)
    )


async def _handle_join(
    callback: CallbackQuery, callback_data: LobbyCallback, repo: GameStateRepository
) -> None:
    settings = get_settings()
    user = callback.from_user
    try:
        await repo.join_game(
            callback_data.chat_id,
            user.id,
            user.full_name,
            max_players=settings.max_players,
            ttl_seconds=settings.redis_game_ttl_seconds,
        )
    except NotInLobbyError:
        await callback.answer("این بازی دیگر در مرحله‌ی پیوستن نیست.", show_alert=True)
        return
    except AlreadyJoinedError:
        await callback.answer("شما از قبل به این بازی پیوسته‌اید.", show_alert=True)
        return
    except LobbyFullError:
        await callback.answer(
            f"ظرفیت بازی تکمیل شده است (حداکثر {settings.max_players} نفر).",
            show_alert=True,
        )
        return

    await _refresh_lobby_panel(callback, repo, callback_data.chat_id)
    await callback.answer("✅ به بازی پیوستید.")


async def _handle_leave(
    callback: CallbackQuery, callback_data: LobbyCallback, repo: GameStateRepository
) -> None:
    try:
        await repo.leave_game(callback_data.chat_id, callback.from_user.id)
    except NotInLobbyError:
        await callback.answer("این بازی دیگر در مرحله‌ی پیوستن نیست.", show_alert=True)
        return
    except NotAParticipantError:
        await callback.answer("شما عضو این بازی نیستید.", show_alert=True)
        return
    except CreatorCannotLeaveError:
        await callback.answer(
            "شما سازنده‌ی بازی هستید؛ برای پایان دادن باید بازی را حذف کنید.",
            show_alert=True,
        )
        return

    await _refresh_lobby_panel(callback, repo, callback_data.chat_id)
    await callback.answer("خارج شدید.")


async def _handle_delete(
    callback: CallbackQuery, callback_data: LobbyCallback, repo: GameStateRepository
) -> None:
    is_admin = await _is_group_admin(callback, callback_data.chat_id)
    try:
        await repo.delete_game(callback_data.chat_id, callback.from_user.id, is_admin)
    except GameNotFoundError:
        await callback.answer("بازی‌ای برای حذف وجود ندارد.", show_alert=True)
        return
    except NotAuthorizedError:
        await callback.answer(
            "فقط سازنده‌ی بازی یا ادمین گروه می‌تواند بازی را حذف کند.", show_alert=True
        )
        return

    assert callback.message is not None
    await safe_edit_text(callback.message, "🗑 بازی حذف شد.")
    await callback.answer()
    logger.info(
        "game_deleted",
        chat_id=callback_data.chat_id,
        by_user=callback.from_user.id,
        by_admin=is_admin,
    )


async def _handle_rules(
    callback: CallbackQuery, callback_data: LobbyCallback, repo: GameStateRepository
) -> None:
    # NOTE: Telegram limits alert popups to 200 characters. The final
    # rules text (still a placeholder per the user's request) must stay
    # under that limit, or this needs to switch to a regular message reply.
    await callback.answer(GAME_RULES_TEXT, show_alert=True)


async def _handle_start(
    callback: CallbackQuery, callback_data: LobbyCallback, repo: GameStateRepository
) -> None:
    settings = get_settings()
    try:
        game = await start_game(
            repo,
            chat_id=callback_data.chat_id,
            requester_id=callback.from_user.id,
            min_players=settings.min_players,
        )
    except GameStartNotInLobbyError:
        await callback.answer("این بازی دیگر در مرحله‌ی لابی نیست.", show_alert=True)
        return
    except NotCreatorError:
        await callback.answer(
            "فقط سازنده‌ی بازی می‌تواند بازی را شروع کند.", show_alert=True
        )
        return
    except NotEnoughPlayersError as exc:
        await callback.answer(
            f"برای شروع بازی حداقل {exc.required} نفر لازم است "
            f"(در حال حاضر {exc.current} نفر).",
            show_alert=True,
        )
        return

    assert callback.message is not None
    text = build_game_message_text(game)
    keyboard = build_game_keyboard(callback_data.chat_id)
    await safe_edit_text(callback.message, text, keyboard)
    await repo.set_message_id(
        callback_data.chat_id, game_message_id=callback.message.message_id
    )
    await callback.answer("🚀 بازی شروع شد!")

    # Arm the round timer so voting starts automatically when time is up.
    if game.ends_at is not None:
        start_round_timer(
            callback.bot,
            repo,
            callback_data.chat_id,
            game.ends_at,
            callback.message.message_id,
        )


_ActionHandler = Callable[
    [CallbackQuery, LobbyCallback, GameStateRepository], Awaitable[None]
]

_ACTION_HANDLERS: dict[LobbyAction, _ActionHandler] = {
    LobbyAction.JOIN: _handle_join,
    LobbyAction.LEAVE: _handle_leave,
    LobbyAction.DELETE: _handle_delete,
    LobbyAction.RULES: _handle_rules,
    LobbyAction.START: _handle_start,
}


@router.callback_query(LobbyCallback.filter())
async def handle_lobby_callback(
    callback: CallbackQuery, callback_data: LobbyCallback, repo: GameStateRepository
) -> None:
    if callback.message is None:
        await callback.answer()
        return

    handler = _ACTION_HANDLERS.get(callback_data.action)
    if handler is None:
        await callback.answer()
        return
    await handler(callback, callback_data, repo)
