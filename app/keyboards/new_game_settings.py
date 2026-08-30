"""Keyboard for the pre-game settings panel (round time + two-spy toggle)."""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.constants import ROUND_TIME_OPTIONS
from app.keyboards.callback_data import NewGameSettingsCallback, SettingsAction


def build_settings_keyboard(
    creator_id: int, round_seconds: int, allow_two_spies: bool
) -> InlineKeyboardMarkup:
    """Render the settings panel reflecting the currently selected values.

    Every button's callback_data carries the *complete* resulting state,
    so the panel can always be redrawn from the callback alone -- no FSM
    or Redis lookup needed while the game hasn't been created yet.

    Args:
        creator_id: Telegram user id of whoever ran the create-game command;
            only this user is allowed to interact with the panel.
        round_seconds: Currently selected round duration.
        allow_two_spies: Currently selected two-spy toggle state.

    """
    builder = InlineKeyboardBuilder()

    # Row 1: time options (3 / 5 / 7 / 10 minutes), selected one checked.
    for label, seconds in ROUND_TIME_OPTIONS:
        text = f"✅ {label}" if seconds == round_seconds else label
        builder.button(
            text=text,
            callback_data=NewGameSettingsCallback(
                creator_id=creator_id,
                round_seconds=seconds,
                allow_two_spies=allow_two_spies,
                action=SettingsAction.SET,
            ),
        )

    # Row 2: two-spy toggle.
    toggle_label = (
        "☑️ امکان دو جاسوس (۷+ نفر)" if allow_two_spies else "⬜️ امکان دو جاسوس (۷+ نفر)"
    )
    builder.button(
        text=toggle_label,
        callback_data=NewGameSettingsCallback(
            creator_id=creator_id,
            round_seconds=round_seconds,
            allow_two_spies=not allow_two_spies,
            action=SettingsAction.SET,
        ),
    )

    # Row 3: confirm / cancel.
    builder.button(
        text="✅ ساخت بازی",
        callback_data=NewGameSettingsCallback(
            creator_id=creator_id,
            round_seconds=round_seconds,
            allow_two_spies=allow_two_spies,
            action=SettingsAction.CONFIRM,
        ),
    )
    builder.button(
        text="❌ انصراف",
        callback_data=NewGameSettingsCallback(
            creator_id=creator_id,
            round_seconds=round_seconds,
            allow_two_spies=allow_two_spies,
            action=SettingsAction.CANCEL,
        ),
    )

    # 4 time buttons on row 1, 1 toggle button on row 2, 2 buttons on row 3.
    builder.adjust(4, 1, 2)
    return builder.as_markup()
