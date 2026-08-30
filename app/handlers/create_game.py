"""Handlers for creating a new game: the /newgame command and the.

pre-game settings panel (round time + two-spy toggle + confirm/cancel).
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.config.settings import get_settings
from app.constants import DEFAULT_ALLOW_TWO_SPIES, DEFAULT_ROUND_SECONDS
from app.domain.game_state import GameSettings
from app.keyboards import (
    NewGameSettingsCallback,
    SettingsAction,
    build_lobby_keyboard,
    build_settings_keyboard,
)
from app.repositories.game_state_repository import (
    GameAlreadyExistsError,
    GameStateRepository,
)
from app.services.game_creation_service import create_new_game
from app.utils.formatting import build_lobby_message_text
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = Router(name="create_game")

# Base spy count before any start-time auto-upgrade; the two-spy rule
# (7+ players -> 2 spies, gated by the allow_two_spies toggle) is applied
# by the game-start service in a later step, not here.
BASE_SPIES_COUNT = 1


@router.message(Command("newgame"))
async def cmd_new_game(message: Message, repo: GameStateRepository) -> None:
    """Entry point: show the pre-game settings panel."""
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("این ربات فقط داخل گروه‌ها قابل استفاده است.")
        return

    if await repo.game_exists(message.chat.id):
        await message.answer(
            "⚠️ در حال حاضر یک بازی در این گروه در جریان است.\n"
            "برای شروع بازی جدید، ابتدا باید بازی فعلی تمام یا حذف شود."
        )
        return

    creator = message.from_user
    if creator is None:  # defensive: anonymous-admin messages have no `from_user`
        await message.answer(
            "امکان شناسایی کاربر وجود ندارد؛ لطفاً به‌صورت عادی پیام بدهید."
        )
        return

    keyboard = build_settings_keyboard(
        creator_id=creator.id,
        round_seconds=DEFAULT_ROUND_SECONDS,
        allow_two_spies=DEFAULT_ALLOW_TWO_SPIES,
    )
    await message.answer(
        "⚙️ <b>تنظیمات بازی جاسوس</b>\n\n"
        "زمان هر دور و امکان دو جاسوس‌بودن (برای گروه‌های ۷ نفر و بیشتر) را "
        "انتخاب کنید، سپس روی «ساخت بازی» بزنید.",
        reply_markup=keyboard,
    )


@router.callback_query(NewGameSettingsCallback.filter())
async def handle_settings_callback(
    callback: CallbackQuery,
    callback_data: NewGameSettingsCallback,
    repo: GameStateRepository,
) -> None:
    """Handle every button press on the pre-game settings panel."""
    if callback.message is None:
        await callback.answer()
        return

    # Only the user who ran /newgame may touch this panel.
    if callback.from_user.id != callback_data.creator_id:
        await callback.answer(
            "این پنل فقط برای کسی است که بازی را می‌سازد.", show_alert=True
        )
        return

    if callback_data.action == SettingsAction.CANCEL:
        await callback.message.delete()
        await callback.answer("ساخت بازی لغو شد.")
        return

    if callback_data.action == SettingsAction.SET:
        keyboard = build_settings_keyboard(
            creator_id=callback_data.creator_id,
            round_seconds=callback_data.round_seconds,
            allow_two_spies=callback_data.allow_two_spies,
        )
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()
        return

    # action == CONFIRM: attempt to actually create the game.
    await _confirm_and_create_game(callback, callback_data, repo)


async def _confirm_and_create_game(
    callback: CallbackQuery,
    callback_data: NewGameSettingsCallback,
    repo: GameStateRepository,
) -> None:
    assert callback.message is not None  # narrowed by the caller
    chat_id = callback.message.chat.id
    creator_name = callback.from_user.full_name

    settings = get_settings()
    game_settings = GameSettings(
        spies_count=BASE_SPIES_COUNT,
        round_seconds=callback_data.round_seconds,
        allow_two_spies=callback_data.allow_two_spies,
    )

    try:
        game = await create_new_game(
            repo,
            chat_id=chat_id,
            creator_id=callback.from_user.id,
            creator_name=creator_name,
            settings=game_settings,
            ttl_seconds=settings.lobby_timeout_seconds,
        )
    except GameAlreadyExistsError:
        # Someone else's /newgame won the race between this panel opening
        # and the confirm click — exactly the scenario the atomic Lua
        # CREATE_GAME script (step 3) exists to protect against.
        logger.info(
            "create_game_race_lost", chat_id=chat_id, user_id=callback.from_user.id
        )
        await callback.answer(
            "⚠️ همزمان یک بازی دیگر در این گروه ساخته شد. شما دیرتر بودید.",
            show_alert=True,
        )
        await callback.message.delete()
        return

    logger.info(
        "game_created",
        chat_id=chat_id,
        creator_id=callback.from_user.id,
        round_seconds=game_settings.round_seconds,
        allow_two_spies=game_settings.allow_two_spies,
    )

    text = build_lobby_message_text(game)
    keyboard = build_lobby_keyboard(chat_id, show_start=False)
    sent = await callback.message.edit_text(text, reply_markup=keyboard)
    await repo.set_message_id(chat_id, lobby_message_id=sent.message_id)
    await callback.answer("✅ بازی ساخته شد!")
