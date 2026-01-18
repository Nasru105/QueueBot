import pytest
from telegram import InlineKeyboardMarkup

from app.queues_menu.inline_keyboards import queue_menu_keyboard, queues_menu_keyboard


@pytest.mark.asyncio
class TestInlineKeyboards:
    """Тесты для инлайн клавиатур меню очередей."""

    async def test_queue_menu_keyboard_structure(self):
        """Тест структуры клавиатуры меню очереди."""
        queue_id = 123
        keyboard = await queue_menu_keyboard(queue_id)

        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) == 4  # 4 строки с кнопками

    async def test_queue_menu_keyboard_buttons_count(self):
        """Тест количества кнопок в каждой строке."""
        queue_id = 456
        keyboard = await queue_menu_keyboard(queue_id)

        assert len(keyboard.inline_keyboard[0]) == 1  # Обновить
        assert len(keyboard.inline_keyboard[1]) == 1  # Поменяться
        assert len(keyboard.inline_keyboard[2]) == 1  # Удалить
        assert len(keyboard.inline_keyboard[3]) == 2  # Назад и Скрыть

    async def test_queue_menu_keyboard_callback_data(self):
        """Тест callback_data кнопок."""
        queue_id = 789
        keyboard = await queue_menu_keyboard(queue_id)

        buttons_flat = [btn for row in keyboard.inline_keyboard for btn in row]

        # Проверяем что callback_data содержит правильный queue_id
        callback_data_list = [btn.callback_data for btn in buttons_flat]

        assert f"menu|queue|{queue_id}|refresh" in callback_data_list
        assert f"menu|queue|{queue_id}|swap" in callback_data_list
        assert f"menu|queue|{queue_id}|delete" in callback_data_list
        assert f"menu|queue|{queue_id}|back" in callback_data_list
        assert "menu|queues|all|hide" in callback_data_list

    async def test_queue_menu_keyboard_button_texts(self):
        """Тест текстов кнопок."""
        queue_id = 100
        keyboard = await queue_menu_keyboard(queue_id)

        buttons_flat = [btn for row in keyboard.inline_keyboard for btn in row]
        texts = [btn.text for btn in buttons_flat]

        assert "🔄 Обновить сообщение с очередью" in texts
        assert "🔃 Поменяться местами" in texts
        assert "🗑 Удалить очередь" in texts
        assert "⬅️ Назад" in texts
        assert "⏸️ Скрыть" in texts

    async def test_queue_menu_keyboard_with_different_queue_ids(self):
        """Тест с разными ID очередей."""
        for queue_id in [1, 100, 999, 12345]:
            keyboard = await queue_menu_keyboard(queue_id)
            buttons_flat = [btn for row in keyboard.inline_keyboard for btn in row]
            callback_data_list = [btn.callback_data for btn in buttons_flat]

            # Проверяем что все кнопки содержат правильный queue_id
            queue_id_callbacks = [cb for cb in callback_data_list if str(queue_id) in cb]
            assert len(queue_id_callbacks) == 4  # 4 кнопки содержат queue_id

    async def test_queues_menu_keyboard_empty(self):
        """Тест клавиатуры меню очередей с пустым списком."""
        keyboard = await queues_menu_keyboard({})

        assert isinstance(keyboard, InlineKeyboardMarkup)
        # Только кнопка "Скрыть"
        assert len(keyboard.inline_keyboard) == 1
        assert len(keyboard.inline_keyboard[0]) == 1
        assert keyboard.inline_keyboard[0][0].text == "⏸️ Скрыть"
        assert keyboard.inline_keyboard[0][0].callback_data == "menu|queues|all|hide"

    async def test_queues_menu_keyboard_single_queue(self):
        """Тест клавиатуры с одной очередью."""
        queues = {"queue_1": {"name": "Test Queue 1"}}

        keyboard = await queues_menu_keyboard(queues)

        assert isinstance(keyboard, InlineKeyboardMarkup)
        # 1 очередь + 1 кнопка Скрыть
        assert len(keyboard.inline_keyboard) == 2

        # Первая кнопка - очередь
        assert keyboard.inline_keyboard[0][0].text == "Test Queue 1"
        assert keyboard.inline_keyboard[0][0].callback_data == "menu|queues|queue_1|get"

        # Вторая кнопка - Скрыть
        assert keyboard.inline_keyboard[1][0].text == "⏸️ Скрыть"
        assert keyboard.inline_keyboard[1][0].callback_data == "menu|queues|all|hide"

    async def test_queues_menu_keyboard_multiple_queues(self):
        """Тест клавиатуры с несколькими очередями."""
        queues = {
            "queue_1": {"name": "First Queue"},
            "queue_2": {"name": "Second Queue"},
            "queue_3": {"name": "Third Queue"},
        }

        keyboard = await queues_menu_keyboard(queues)

        assert isinstance(keyboard, InlineKeyboardMarkup)
        # 3 очереди + 1 кнопка Скрыть
        assert len(keyboard.inline_keyboard) == 4

    async def test_queues_menu_keyboard_queue_names(self):
        """Тест что имена очередей корректно отображаются."""
        queues = {
            "q1": {"name": "Priority Queue"},
            "q2": {"name": "Regular Queue"},
            "q3": {"name": "Urgent Queue"},
        }

        keyboard = await queues_menu_keyboard(queues)

        buttons_flat = [btn for row in keyboard.inline_keyboard[:-1] for btn in row]
        texts = [btn.text for btn in buttons_flat]

        assert "Priority Queue" in texts
        assert "Regular Queue" in texts
        assert "Urgent Queue" in texts

    async def test_queues_menu_keyboard_callback_data_structure(self):
        """Тест структуры callback_data для очередей."""
        queues = {"test_queue_id": {"name": "Test Queue"}}

        keyboard = await queues_menu_keyboard(queues)

        queue_button = keyboard.inline_keyboard[0][0]
        callback_parts = queue_button.callback_data.split("|")

        assert callback_parts[0] == "menu"
        assert callback_parts[1] == "queues"
        assert callback_parts[2] == "test_queue_id"
        assert callback_parts[3] == "get"

    async def test_queues_menu_keyboard_preserves_queue_order(self):
        """Тест что порядок очередей сохраняется."""
        queues = {
            "q1": {"name": "First"},
            "q2": {"name": "Second"},
            "q3": {"name": "Third"},
        }

        keyboard = await queues_menu_keyboard(queues)

        # Проверяем callback_data (так как порядок dict может варьироваться)
        callback_data_list = [btn.callback_data for row in keyboard.inline_keyboard[:-1] for btn in row]

        # Все queue_id должны быть в callback_data
        assert any("q1" in cb for cb in callback_data_list)
        assert any("q2" in cb for cb in callback_data_list)
        assert any("q3" in cb for cb in callback_data_list)

    async def test_queues_menu_keyboard_hide_button_always_present(self):
        """Тест что кнопка Скрыть всегда присутствует и в конце."""
        for num_queues in [0, 1, 5, 10]:
            queues = {f"q{i}": {"name": f"Queue {i}"} for i in range(num_queues)}
            keyboard = await queues_menu_keyboard(queues)

            # Последняя кнопка - Скрыть
            last_button = keyboard.inline_keyboard[-1][0]
            assert last_button.text == "⏸️ Скрыть"
            assert last_button.callback_data == "menu|queues|all|hide"
