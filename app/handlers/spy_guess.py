"""Listen for an exact mid-round (or final) word guess from a spy."""

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import Message

from app.domain.game_state import GameStatus
from app.models.enums import GameEndReason, GameWinner, PlayerRole
from app.repositories.game_state_repository import GameStateRepository
from app.services.game_end_service import end_game
from app.services.spy_guess_service import is_exact_word_guess, player_may_guess
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = Router(name="spy_guess")


@router.message(
    F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),
    F.text,
    ~F.text.startswith("/"),
)
async def handle_possible_spy_guess(
    message: Message, repo: GameStateRepository
) -> None:
    """Handle exact word guesses during RUNNING or AWAITING_FINAL_GUESS.

    Commands (messages starting with ``/``) are intentionally ignored so
    they can be handled by dedicated command routers (e.g. admin).
    """
    if message.from_user is None or not message.text:
        return

    chat_id = message.chat.id
    game = await repo.get_game(chat_id)
    if game is None:
        return

    # --- Mid-round guess (RUNNING) ---
    if game.status == GameStatus.RUNNING:
        if not player_may_guess(game, message.from_user.id):
            return
        if not is_exact_word_guess(message.text, game.word or ""):
            return

        logger.info(
            "spy_guessed_word_mid_round",
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
        return

    # --- Final guess after spy was voted out ---
    if game.status == GameStatus.AWAITING_FINAL_GUESS:
        player = game.get_player(message.from_user.id)
        if player is None or player.role != PlayerRole.SPY:
            return
        # Only the eliminated spy may attempt the final guess.
        if not player.eliminated:
            return
        if not is_exact_word_guess(message.text, game.word or ""):
            return

        logger.info(
            "spy_final_guess_correct",
            chat_id=chat_id,
            user_id=message.from_user.id,
        )
        await end_game(
            message.bot,
            repo,
            game,
            winner=GameWinner.SPY,
            reason=GameEndReason.SPY_VOTED_OUT_CORRECT_GUESS,
            announce=True,
        )
