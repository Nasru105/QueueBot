"""
Тесты для QueuePresenter — форматирования текста и клавиатур.
"""

from app.queues.presenter import QueuePresenter


class TestFormatQueueText:
    """Тесты форматирования текста очереди."""

    def test_empty_queue(self):
        """Форматирование пустой очереди."""
        text = QueuePresenter.format_queue_text("Встреча", [])
        assert "`Встреча`" in text
        assert "пуста" in text
        assert "\\." in text  # Экранированная точка

    def test_single_user(self):
        """Форматирование очереди с одним пользователем."""
        text = QueuePresenter.format_queue_text("Встреча", ["Alice"])
        assert "`Встреча`" in text
        assert "1\\. Alice" in text

    def test_multiple_users(self):
        """Форматирование очереди с несколькими пользователями."""
        queue = ["Alice", "Bob", "Charlie"]
        text = QueuePresenter.format_queue_text("Встреча", queue)
        assert "`Встреча`" in text
        assert "1\\. Alice" in text
        assert "2\\. Bob" in text
        assert "3\\. Charlie" in text

    def test_special_characters_escaped(self):
        """Специальные символы экранируются."""
        queue = ["Alice_Bold", "Bob*Italic"]
        text = QueuePresenter.format_queue_text("Queue[1]", queue)
        # Символы должны быть экранированы для Markdown v2
        assert "Queue" in text
        assert "Alice" in text

    def test_queue_name_with_special_chars(self):
        """Имя очереди со специальными символами."""
        text = QueuePresenter.format_queue_text("Встреча (важная)", [])
        assert "Встреча" in text
        assert "пуста" in text

    def test_long_user_names(self):
        """Длинные имена пользователей."""
        queue = ["Very Very Long User Name", "Another Long Long Name"]
        text = QueuePresenter.format_queue_text("Q", queue)
        assert "Very Very Long User Name" in text
        assert "Another Long Long Name" in text


class TestBuildKeyboard:
    """Тесты построения клавиатур."""

    def test_keyboard_factory_none(self):
        """Если keyboard_factory = None, возвращается None."""
        presenter = QueuePresenter(keyboard_factory=None)
        result = presenter.build_keyboard(0)
        assert result is None

    def test_keyboard_factory_called(self):
        """keyboard_factory вызывается с индексом."""
        called_with = []

        def mock_factory(index):
            called_with.append(index)
            return "mock_keyboard"

        presenter = QueuePresenter(keyboard_factory=mock_factory)
        result = presenter.build_keyboard(5)
        assert result == "mock_keyboard"
        assert called_with == [5]

    def test_keyboard_factory_different_indices(self):
        """keyboard_factory вызывается с разными индексами."""
        call_count = {"count": 0}

        def mock_factory(index):
            call_count["count"] += 1
            return f"keyboard_{index}"

        presenter = QueuePresenter(keyboard_factory=mock_factory)
        assert presenter.build_keyboard(0) == "keyboard_0"
        assert presenter.build_keyboard(1) == "keyboard_1"
        assert call_count["count"] == 2
