"""Admin-only maintenance commands."""

from aiogram import Router
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command
from aiogram.types import Message

from app.repositories.game_state_repository import GameStateRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = Router(name="admin")

# Telegram may return enum members or plain strings depending on version.
_ADMIN_STATUSES = {
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.CREATOR,
    "administrator",
    "creator",
}


@router.message(Command("deletecurrentgame"))
async def cmd_delete_current_game(message: Message, repo: GameStateRepository) -> None:
    """Force-delete the live game in this chat (group admins / owner only).

    Clears Redis state for this chat so a new game can be created after a
    stuck timer or partial failure.
    """
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("این دستور فقط داخل گروه قابل استفاده است.")
        return

    if message.from_user is None:
        await message.answer(
            "امکان شناسایی کاربر وجود ندارد؛ لطفاً به‌صورت عادی پیام بدهید."
        )
        return

    try:
        member = await message.bot.get_chat_member(
            message.chat.id, message.from_user.id
        )
        status = member.status
    except Exception:
        logger.exception(
            "deletecurrentgame_get_member_failed",
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )
        await message.answer(
            "نتوانستم وضعیت ادمین شما را از تلگرام بگیرم. کمی بعد دوباره تلاش کنید."
        )
        return

    if status not in _ADMIN_STATUSES:
        await message.answer("فقط ادمین یا مالک گروه می‌تواند بازی فعلی را حذف کند.")
        return

    chat_id = message.chat.id
    game = await repo.get_game(chat_id)
    if game is None:
        await message.answer("بازی فعالی در این گروه وجود ندارد.")
        return

    for msg_id in (game.game_message_id, game.lobby_message_id):
        if msg_id is None:
            continue
        try:
            await message.bot.delete_message(chat_id, msg_id)
        except Exception:  # noqa: BLE001
            pass

    await repo.force_delete_game(chat_id)
    logger.info(
        "game_force_deleted",
        chat_id=chat_id,
        by_user=message.from_user.id,
        previous_status=game.status.value,
    )
    await message.answer(
        "🗑 بازی فعلی حذف شد.\nبرای ساخت بازی جدید می‌توانید /newgame بزنید."
    )
