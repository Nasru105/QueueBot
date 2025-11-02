import pytest
from telegram import InlineKeyboardMarkup

from app.utils.InlineKeyboards import queue_keyboard, queues_keyboard


def test_queue_keyboard_markup():
    kb = queue_keyboard(0)
    assert isinstance(kb, InlineKeyboardMarkup)
    # Проверяем callback_data первой кнопки содержит 'queue|0|join'
    assert kb.inline_keyboard[0][0].callback_data == "queue|0|join"


@pytest.mark.asyncio
async def test_queues_keyboard_markup():
    kb = await queues_keyboard(["A", "B"])
    assert isinstance(kb, InlineKeyboardMarkup)
    # Должны быть кнопки для каждой очереди — проверяем первый ряд
    assert any(
        btn.callback_data.startswith("queues|0|") for btn in kb.inline_keyboard[0]
    )
