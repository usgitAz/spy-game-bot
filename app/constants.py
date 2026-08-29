"""Shared constants used across keyboards, handlers, and services."""

# (label, seconds) pairs shown as the round-duration buttons in the
# pre-game settings panel: 3 / 5 / 7 / 10 minutes.
ROUND_TIME_OPTIONS: list[tuple[str, int]] = [
    ("۳ دقیقه", 3 * 60),
    ("۵ دقیقه", 5 * 60),
    ("۷ دقیقه", 7 * 60),
    ("۱۰ دقیقه", 10 * 60),
]

DEFAULT_ROUND_SECONDS = ROUND_TIME_OPTIONS[0][1]
DEFAULT_ALLOW_TWO_SPIES = False

# Placeholder — the user said they'll provide the final rules text later.
# Shown in a popup (callback.answer(show_alert=True)) when the "قوانین بازی"
# button is pressed.
GAME_RULES_TEXT = (
    "قوانین بازی جاسوس:\n\n"
    "این متن به‌زودی تکمیل می‌شود."
)
