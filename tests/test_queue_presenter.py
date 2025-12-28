from app.queues_menu.presenters.queue_presenter import (
    build_swap_confirmation_keyboard,
    build_queue_action_keyboard,
)


def test_build_swap_confirmation_keyboard():
    kb = build_swap_confirmation_keyboard("q1", "swap123")
    # InlineKeyboardMarkup -> .inline_keyboard is list of rows
    rows = kb.inline_keyboard
    assert len(rows) == 1
    row = rows[0]
    assert row[0].text == "Да"
    assert row[0].callback_data == "queue|q1|swap_accept|swap123"
    assert row[1].text == "Нет"
    assert row[1].callback_data == "queue|q1|swap_decline|swap123"


def test_build_queue_action_keyboard_default():
    kb = build_queue_action_keyboard("q2", include_swap=True)
    rows = kb.inline_keyboard
    # expected at least 3 rows: join/leave, swap, refresh
    assert any(btn.callback_data == "queue|q2|join" for row in rows for btn in row)
    assert any(btn.callback_data == "queue|q2|leave" for row in rows for btn in row)
    assert any(btn.callback_data == "queue|q2|swap" for row in rows for btn in row)
    assert any(btn.callback_data == "queue|q2|refresh" for row in rows for btn in row)


def test_build_queue_action_keyboard_no_swap():
    kb = build_queue_action_keyboard("q3", include_swap=False)
    rows = kb.inline_keyboard
    assert not any(btn.callback_data == "queue|q3|swap" for row in rows for btn in row)
    assert any(btn.callback_data == "queue|q3|join" for row in rows for btn in row)
