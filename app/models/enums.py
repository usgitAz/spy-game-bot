"""Shared enum types used across the persistence layer."""

import enum


class PlayerRole(enum.StrEnum):
    """Role assigned to a player for a single finished game."""

    CITIZEN = "citizen"
    SPY = "spy"


class GameWinner(enum.StrEnum):
    """Which side won a finished game."""

    CITIZENS = "citizens"
    SPY = "spy"


class GameEndReason(enum.StrEnum):
    """How a finished game concluded — kept for stats/analytics."""

    SPY_GUESSED_WORD = "spy_guessed_word"
    """The spy sent the correct word mid-game and won instantly."""
    SPY_VOTED_OUT_WRONG_GUESS = "spy_voted_out_wrong_guess"
    """The spy was voted out and failed to guess the word."""
    SPY_VOTED_OUT_CORRECT_GUESS = "spy_voted_out_correct_guess"
    """The spy was voted out but still guessed the word correctly and won."""
    CITIZEN_VOTED_OUT = "citizen_voted_out"
    """A citizen was voted out instead of the spy; the spy wins."""
    CANCELLED = "cancelled"
    """The game was deleted/aborted before completion (e.g. lobby timeout)."""