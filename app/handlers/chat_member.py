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
    """Bot itself was removed/kicked — wipe live Redis state for that chat."""
    if not _is_leave_transition(event):
        return

    logger.info(
        "bot_removed_from_chat",
        chat_id=event.chat.id,
        new_status=str(event.new_chat_member.status),
    )
    await handle_bot_removed(event.bot, repo, chat_id=event.chat.id)
