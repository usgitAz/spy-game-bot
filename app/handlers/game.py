"""Handlers for the in-progress game panel (see my role, early word guess later)."""

from aiogram import Router
from aiogram.types import CallbackQuery

from app.domain.game_state import GameStatus
from app.keyboards.callback_data import GameAction, GameCallback
from app.models.enums import PlayerRole
from app.repositories.game_state_repository import GameStateRepository
from app.utils.formatting import role_reveal_text
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = Router(name="game")


@router.callback_query(GameCallback.filter())
async def handle_game_callback(
    callback: CallbackQuery,
    callback_data: GameCallback,
    repo: GameStateRepository,
) -> None:
    if callback.message is None:
        await callback.answer()
        return

    if callback_data.action == GameAction.SEE_ROLE:
        await _handle_see_role(callback, callback_data, repo)
        return

    await callback.answer()


async def _handle_see_role(
    callback: CallbackQuery,
    callback_data: GameCallback,
    repo: GameStateRepository,
) -> None:
    game = await repo.get_game(callback_data.chat_id)
    if game is None or game.status not in (
        GameStatus.RUNNING,
        GameStatus.VOTING,
        GameStatus.AWAITING_FINAL_GUESS,
    ):
        await callback.answer("بازی در جریان نیست.", show_alert=True)
        return

    player = game.get_player(callback.from_user.id)
    if player is None:
        await callback.answer("شما عضو این بازی نیستید.", show_alert=True)
        return
    if player.role is None:
        await callback.answer("نقش شما هنوز مشخص نشده.", show_alert=True)
        return

    is_spy = player.role == PlayerRole.SPY
    text = role_reveal_text(is_spy=is_spy, word=game.word if not is_spy else None)
    # show_alert=True → private popup only the tapping user sees.
    await callback.answer(text, show_alert=True)
    logger.info(
        "role_revealed",
        chat_id=callback_data.chat_id,
        user_id=callback.from_user.id,
        is_spy=is_spy,
    )
