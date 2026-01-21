import pytest
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.queues.models import Member
from app.queues.services.swap_service.inline_keyboards import queue_swap_keyboard, swap_confirmation_keyboard


@pytest.mark.asyncio
class TestQueueSwapKeyboard:
    async def test_queue_swap_keyboard_basic(self):
        """Тест создания клавиатуры выбора членов для обмена."""
        members = [
            Member(user_id=123, display_name="Alice"),
            Member(user_id=456, display_name="Bob"),
            Member(user_id=789, display_name="Charlie"),
        ]
        queue_id = "q1"

        keyboard = await queue_swap_keyboard(members, queue_id)

        assert isinstance(keyboard, InlineKeyboardMarkup)
        # Должно быть 3 кнопки для членов + 1 ряд с кнопками "Назад" и "Скрыть"
        assert len(keyboard.inline_keyboard) == 4

        # Проверяем кнопки членов
        for i, member in enumerate(members):
            button = keyboard.inline_keyboard[i][0]
            assert isinstance(button, InlineKeyboardButton)
            assert button.text == member.display_name
            assert button.callback_data == f"queue|{queue_id}|swap|request|{member.user_id}"

        # Проверяем нижние кнопки
        last_row = keyboard.inline_keyboard[-1]
        assert len(last_row) == 2
        assert last_row[0].text == "⬅️ Назад"
        assert last_row[0].callback_data == f"menu|queues|{queue_id}|get"
        assert last_row[1].text == "⏸️ Скрыть"
        assert last_row[1].callback_data == "menu|queues|all|hide"

    async def test_queue_swap_keyboard_single_member(self):
        """Тест с одним членом."""
        members = [
            Member(user_id=123, display_name="Alice"),
        ]
        queue_id = "q1"

        keyboard = await queue_swap_keyboard(members, queue_id)

        assert len(keyboard.inline_keyboard) == 2  # 1 член + 1 ряд кнопок

    async def test_queue_swap_keyboard_empty_members(self):
        """Тест с пустым списком членов."""
        members = []
        queue_id = "q1"

        keyboard = await queue_swap_keyboard(members, queue_id)

        # Должна быть только одна строка с кнопками навигации
        assert len(keyboard.inline_keyboard) == 1
        assert len(keyboard.inline_keyboard[0]) == 2

    async def test_queue_swap_keyboard_member_without_user_id(self):
        """Тест пропуска членов без user_id."""
        members = [
            Member(display_name="Unknown"),  # Нет user_id
            Member(user_id=123, display_name="Alice"),
        ]
        queue_id = "q1"

        keyboard = await queue_swap_keyboard(members, queue_id)

        # Должно быть только 2 строки (1 валидный член + 1 ряд кнопок)
        assert len(keyboard.inline_keyboard) == 2

    async def test_queue_swap_keyboard_member_without_display_name(self):
        """Тест использования user_id как имени если display_name отсутствует."""
        members = [
            Member(user_id=123),  # Нет display_name
        ]
        queue_id = "q1"

        keyboard = await queue_swap_keyboard(members, queue_id)

        button = keyboard.inline_keyboard[0][0]
        assert button.text == "123"  # Используется user_id

    async def test_queue_swap_keyboard_special_queue_id(self):
        """Тест с специальными символами в queue_id."""
        members = [
            Member(user_id=123, display_name="Alice"),
        ]
        queue_id = "q-1_special.id"

        keyboard = await queue_swap_keyboard(members, queue_id)

        button = keyboard.inline_keyboard[0][0]
        assert button.callback_data == f"queue|{queue_id}|swap|request|123"

    async def test_queue_swap_keyboard_large_number_of_members(self):
        """Тест с большим количеством членов."""
        members = [
            Member(user_id=i, display_name=f"User{i}")
            for i in range(1, 51)  # 50 членов
        ]
        queue_id = "q1"

        keyboard = await queue_swap_keyboard(members, queue_id)

        # Каждый член на отдельной строке + 1 ряд кнопок
        assert len(keyboard.inline_keyboard) == 51

    async def test_queue_swap_keyboard_preserves_order(self):
        """Тест что порядок членов сохраняется."""
        members = [
            Member(user_id=789, display_name="Charlie"),
            Member(user_id=123, display_name="Alice"),
            Member(user_id=456, display_name="Bob"),
        ]
        queue_id = "q1"

        keyboard = await queue_swap_keyboard(members, queue_id)

        # Проверяем порядок
        assert keyboard.inline_keyboard[0][0].text == "Charlie"
        assert keyboard.inline_keyboard[1][0].text == "Alice"
        assert keyboard.inline_keyboard[2][0].text == "Bob"

    async def test_queue_swap_keyboard_user_id_zero(self):
        """Тест с user_id=0 (валидное значение)."""
        members = [
            Member(user_id=0, display_name="SystemUser"),
        ]
        queue_id = "q1"

        keyboard = await queue_swap_keyboard(members, queue_id)

        button = keyboard.inline_keyboard[0][0]
        assert button.callback_data == "queue|q1|swap|request|0"


class TestSwapConfirmationKeyboard:
    def test_swap_confirmation_keyboard_basic(self):
        """Тест создания клавиатуры подтверждения обмена."""
        queue_id = "q1"
        swap_id = "swap_123"

        keyboard = swap_confirmation_keyboard(queue_id, swap_id)

        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) == 1
        assert len(keyboard.inline_keyboard[0]) == 2

        # Проверяем кнопку "Да"
        yes_button = keyboard.inline_keyboard[0][0]
        assert yes_button.text == "Да"
        assert yes_button.callback_data == f"queue|{queue_id}|swap|accept|{swap_id}"

        # Проверяем кнопку "Нет"
        no_button = keyboard.inline_keyboard[0][1]
        assert no_button.text == "Нет"
        assert no_button.callback_data == f"queue|{queue_id}|swap|decline|{swap_id}"

    def test_swap_confirmation_keyboard_special_ids(self):
        """Тест с специальными символами в ID."""
        queue_id = "q-1_special.id"
        swap_id = "swap-123_special.id"

        keyboard = swap_confirmation_keyboard(queue_id, swap_id)

        yes_button = keyboard.inline_keyboard[0][0]
        no_button = keyboard.inline_keyboard[0][1]

        assert yes_button.callback_data == f"queue|{queue_id}|swap|accept|{swap_id}"
        assert no_button.callback_data == f"queue|{queue_id}|swap|decline|{swap_id}"

    def test_swap_confirmation_keyboard_empty_ids(self):
        """Тест с пустыми ID."""
        queue_id = ""
        swap_id = ""

        keyboard = swap_confirmation_keyboard(queue_id, swap_id)

        yes_button = keyboard.inline_keyboard[0][0]
        assert yes_button.callback_data == "queue||swap|accept|"

    def test_swap_confirmation_keyboard_numeric_ids(self):
        """Тест с числовыми ID."""
        queue_id = "123"
        swap_id = "456"

        keyboard = swap_confirmation_keyboard(queue_id, swap_id)

        yes_button = keyboard.inline_keyboard[0][0]
        assert yes_button.callback_data == "queue|123|swap|accept|456"

    def test_swap_confirmation_keyboard_button_order(self):
        """Тест что кнопки в правильном порядке (Да, потом Нет)."""
        keyboard = swap_confirmation_keyboard("q1", "swap_1")

        buttons = keyboard.inline_keyboard[0]
        assert buttons[0].text == "Да"
        assert buttons[1].text == "Нет"

    def test_swap_confirmation_keyboard_single_row(self):
        """Тест что клавиатура содержит одну строку."""
        keyboard = swap_confirmation_keyboard("q1", "swap_1")

        assert len(keyboard.inline_keyboard) == 1
        assert len(keyboard.inline_keyboard[0]) == 2

    def test_swap_confirmation_keyboard_long_ids(self):
        """Тест с очень длинными ID."""
        queue_id = "q" + "1" * 100
        swap_id = "swap" + "1" * 100

        keyboard = swap_confirmation_keyboard(queue_id, swap_id)

        yes_button = keyboard.inline_keyboard[0][0]
        assert yes_button.callback_data == f"queue|{queue_id}|swap|accept|{swap_id}"

    def test_swap_confirmation_keyboard_pipe_character_in_id(self):
        """Тест с символом | в ID (может вызвать проблемы в callback_data)."""
        # Примечание: это тест граничного случая - в реальности такое не должно быть
        queue_id = "q|1"
        swap_id = "swap|1"

        keyboard = swap_confirmation_keyboard(queue_id, swap_id)

        yes_button = keyboard.inline_keyboard[0][0]
        # Проверяем что символы передаются как есть
        assert yes_button.callback_data == f"queue|{queue_id}|swap|accept|{swap_id}"

    def test_swap_confirmation_keyboard_returns_inline_keyboard_markup(self):
        """Тест что возвращается именно InlineKeyboardMarkup."""
        result = swap_confirmation_keyboard("q1", "swap_1")

        assert isinstance(result, InlineKeyboardMarkup)
        assert hasattr(result, "inline_keyboard")
        assert isinstance(result.inline_keyboard, tuple)
