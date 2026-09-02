"""Handlers for the voting panel callbacks."""

from aiogram import Router
from aiogram.types import CallbackQuery

from app.domain.game_state import GameStatus
from app.keyboards.callback_data import VoteCallback
from app.repositories.game_state_repository import (
    AlreadyVotedError,
    GameStateRepository,
    NotInVotingPhaseError,
)
from app.services.voting_service import resolve_voting
from app.utils.formatting import user_mention
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = Router(name="voting")


@router.callback_query(VoteCallback.filter())
async def handle_vote(
    callback: CallbackQuery,
    callback_data: VoteCallback,
    repo: GameStateRepository,
) -> None:
    chat_id = callback_data.chat_id
    voter_id = callback.from_user.id
    target_id = callback_data.target_user_id

    game = await repo.get_game(chat_id)
    if game is None or game.status != GameStatus.VOTING:
        await callback.answer("الان زمان رای‌گیری نیست.", show_alert=True)
        return

    voter = game.get_player(voter_id)
    if voter is None or voter.eliminated or voter.left_mid_game:
        await callback.answer(
            "فقط بازیکنان این بازی می‌توانند رای بدهند.", show_alert=True
        )
        return

    target = game.get_player(target_id)
    if target is None or target.eliminated or target.left_mid_game:
        await callback.answer("این بازیکن دیگر هدف معتبری نیست.", show_alert=True)
        return

    # Runoff: only the tied candidates are valid targets.
    if game.vote_candidate_ids is not None and target_id not in game.vote_candidate_ids:
        await callback.answer(
            "در دور دوم فقط می‌توانید به نفرات مساوی رای بدهید.",
            show_alert=True,
        )
        return

    try:
        await repo.record_vote(chat_id, voter_id, target_id)
    except NotInVotingPhaseError:
        await callback.answer("الان زمان رای‌گیری نیست.", show_alert=True)
        return
    except AlreadyVotedError:
        await callback.answer("شما قبلاً رای داده‌اید.", show_alert=True)
        return

    await callback.answer("✅ رای شما ثبت شد.")

    voter_name = user_mention(voter_id, voter.display_name)
    target_name = user_mention(target_id, target.display_name)
    try:
        await callback.bot.send_message(
            chat_id,
            f"🗳 {voter_name} به {target_name} رای داد.",
        )
    except Exception:  # noqa: BLE001
        logger.exception("vote_announce_failed", chat_id=chat_id)

    # Resolve early when every active player has voted.
    active_ids = {
        p.user_id for p in game.players if not p.eliminated and not p.left_mid_game
    }
    votes = await repo.get_votes(chat_id)
    if active_ids.issubset(votes.keys()):
        logger.info("all_players_voted", chat_id=chat_id, round=game.voting_round)
        await resolve_voting(callback.bot, repo, chat_id)
