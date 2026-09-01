"""Listen for an exact mid-round word guess from a spy."""

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import Message

from app.models.enums import GameEndReason, GameWinner
from app.repositories.game_state_repository import GameStateRepository
from app.services.game_end_service import end_game
from app.services.spy_guess_service import is_exact_word_guess, player_may_guess
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = Router(name="spy_guess")


@router.message(
    F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),
    F.text,
)
async def handle_possible_spy_guess(
    message: Message, repo: GameStateRepository
) -> None:
    """If a spy sends exactly the secret word while RUNNING, they win."""
    if message.from_user is None or not message.text:
        return

    chat_id = message.chat.id
    game = await repo.get_game(chat_id)
    if game is None:
        return
    if not player_may_guess(game, message.from_user.id):
        return
    if not is_exact_word_guess(message.text, game.word or ""):
        return

    logger.info(
        "spy_guessed_word",
        chat_id=chat_id,
        user_id=message.from_user.id,
    )

    await end_game(
        message.bot,
        repo,
        game,
        winner=GameWinner.SPY,
        reason=GameEndReason.SPY_GUESSED_WORD,
        announce=True,
    )
