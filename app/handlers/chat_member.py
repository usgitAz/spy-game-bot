"""Telegram chat_member / my_chat_member updates for leave & bot-removal."""

from aiogram import F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.types import ChatMemberUpdated

from app.repositories.game_state_repository import GameStateRepository
from app.services.player_leave_service import handle_bot_removed, handle_member_left
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = Router(name="chat_member")

_LEFT = {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}
_WAS_IN = {
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.RESTRICTED,
}


def _is_leave_transition(event: ChatMemberUpdated) -> bool:
    old = event.old_chat_member.status
    new = event.new_chat_member.status
    return old in _WAS_IN and new in _LEFT


@router.chat_member(
    F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),
)
async def on_chat_member(event: ChatMemberUpdated, repo: GameStateRepository) -> None:
    """A human left or was kicked from a group that may have a live game."""
    if not _is_leave_transition(event):
        return

    user = event.new_chat_member.user
    if user.is_bot:
        return

    display = user.full_name or (user.username or str(user.id))
    logger.info(
        "chat_member_left",
        chat_id=event.chat.id,
        user_id=user.id,
        old_status=str(event.old_chat_member.status),
        new_status=str(event.new_chat_member.status),
    )
    await handle_member_left(
        event.bot,
        repo,
        chat_id=event.chat.id,
        user_id=user.id,
        display_name=display,
    )


@router.my_chat_member(
    F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),
)
async def on_my_chat_member(
    event: ChatMemberUpdated, repo: GameStateRepository
) -> None:
    """Bot added/removed or rights changed in a group."""
    from app.utils.bot_permissions import BOT_NOT_ADMIN_TEXT
    from app.utils.formatting import force_rtl

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    # Bot left / kicked → clear live game state.
    if _is_leave_transition(event):
        logger.info(
            "bot_removed_from_chat",
            chat_id=event.chat.id,
            new_status=str(new_status),
        )
        await handle_bot_removed(event.bot, repo, chat_id=event.chat.id)
        return

    # Bot joined as a normal member (not admin) → explain the requirement.
    joined_as_member = (
        old_status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}
        or str(old_status) in ("left", "kicked")
    ) and new_status in {
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.RESTRICTED,
        "member",
        "restricted",
    }
    if joined_as_member:
        try:
            await event.bot.send_message(event.chat.id, force_rtl(BOT_NOT_ADMIN_TEXT))
        except Exception:  # noqa: BLE001
            logger.exception("bot_join_not_admin_warn_failed", chat_id=event.chat.id)
        return

    # Promoted to admin — short confirmation.
    became_admin = new_status in {
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR,
        "administrator",
        "creator",
    } and old_status not in {
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR,
        "administrator",
        "creator",
    }
    if became_admin:
        try:
            await event.bot.send_message(
                event.chat.id,
                force_rtl(
                    "✅ ربات ادمین شد و آماده استفاده است.\n"
                    "با دستور /newgame بازی جدید بسازید."
                ),
            )
        except Exception:  # noqa: BLE001
            pass
