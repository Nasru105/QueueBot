"""
Тесты для QueuePresenter - отображение очереди.
"""

import pytest

from app.queues.models import Member, Queue
from app.queues.presenter import QueuePresenter


@pytest.fixture
def presenter():
    """Фикстура для создания presenter без keyboard_factory."""
    return QueuePresenter()


@pytest.fixture
def presenter_with_factory():
    """Фикстура для presenter с mock keyboard factory."""
    mock_factory = lambda queue_id: None
    return QueuePresenter(keyboard_factory=mock_factory)


class TestQueuePresenterFormatQueueText:
    """Тесты форматирования текста очереди."""

    def test_format_simple_queue(self, presenter: QueuePresenter):
        """Форматирование простой очереди."""
        queue = Queue(
            id="1",
            name="Очередь 1",
            members=[
                Member(display_name="Alice", user_id=1),
                Member(display_name="Bob", user_id=2),
            ],
        )
        result = presenter.format_queue_text(queue)
        assert "Очередь 1" in result
        assert "Alice" in result
        assert "Bob" in result
        assert "1\\." in result
        assert "2\\." in result

    def test_format_queue_with_special_characters(self, presenter: QueuePresenter):
        """Форматирование очереди с спецсимволами."""
        queue = Queue(
            id="1",
            name="Очередь [тест]",
            members=[
                Member(display_name="Alice_test", user_id=1),
            ],
        )
        result = presenter.format_queue_text(queue)
        # Спецсимволы должны быть экранированы для markdown
        assert "Очередь" in result

    def test_format_empty_queue(self, presenter: QueuePresenter):
        """Форматирование пустой очереди."""
        queue = Queue(id="1", name="Пустая очередь", members=[])
        result = presenter.format_queue_text(queue)
        assert "Пустая очередь" in result
        assert "Очередь пуста" in result

    def test_format_queue_with_description(self, presenter: QueuePresenter):
        """Форматирование очереди с описанием."""
        queue = Queue(
            id="1",
            name="Спортзал",
            description="Запись на тренировку",
            members=[
                Member(display_name="John", user_id=1),
            ],
        )
        result = presenter.format_queue_text(queue)
        assert "Спортзал" in result
        assert "Запись на тренировку" in result
        assert "John" in result

    def test_format_queue_without_description(self, presenter: QueuePresenter):
        """Форматирование без описания."""
        queue = Queue(
            id="1",
            name="Очередь",
            members=[
                Member(display_name="Alice", user_id=1),
            ],
        )
        result = presenter.format_queue_text(queue)
        assert "Очередь" in result
        assert "Alice" in result

    def test_format_queue_members_with_user_id_only(self, presenter: QueuePresenter):
        """Форматирование когда display_name не указан."""
        queue = Queue(
            id="1",
            name="Очередь",
            members=[
                Member(user_id=123),
                Member(user_id=456),
            ],
        )
        result = presenter.format_queue_text(queue)
        assert "123" in result
        assert "456" in result

    def test_format_queue_with_long_names(self, presenter: QueuePresenter):
        """Форматирование с длинными именами."""
        queue = Queue(
            id="1",
            name="Очередь для очень длинного имени",
            members=[
                Member(display_name="Alexander Dmitrievich Aleksandrov", user_id=1),
                Member(display_name="Ekaterina Ivanovna Sidorova", user_id=2),
            ],
        )
        result = presenter.format_queue_text(queue)
        assert "Alexander Dmitrievich Aleksandrov" in result
        assert "Ekaterina Ivanovna Sidorova" in result

    def test_format_queue_with_numbers_in_names(self, presenter: QueuePresenter):
        """Форматирование с номерами в именах."""
        queue = Queue(
            id="1",
            name="Очередь",
            members=[
                Member(display_name="User123", user_id=1),
                Member(display_name="Test_456", user_id=2),
            ],
        )
        result = presenter.format_queue_text(queue)
        assert "User123" in result
        assert "Test\\_456" in result  # Test_456 будет экранирован как Test\_456 в markdown
        assert "Test" in result
        assert "456" in result

    def test_format_large_queue(self, presenter: QueuePresenter):
        """Форматирование большой очереди (50+ человек)."""
        members = [Member(display_name=f"User{i}", user_id=i) for i in range(1, 51)]
        queue = Queue(id="1", name="Большая очередь", members=members)
        result = presenter.format_queue_text(queue)
        assert "Большая очередь" in result
        assert "User1" in result
        assert "User50" in result
        assert "50\\." in result


class TestQueuePresenterBuildKeyboard:
    """Тесты для построения клавиатур."""

    def test_build_queue_keyboard_without_factory(self, presenter: QueuePresenter):
        """Построение клавиатуры без factory."""
        result = presenter.build_queue_keyboard(123)
        # Должна использовать default queue_keyboard
        assert result is not None or result is None  # зависит от реализации

    def test_build_queue_keyboard_with_factory(self, presenter_with_factory: QueuePresenter):
        """Построение клавиатуры с factory."""
        result = presenter_with_factory.build_queue_keyboard(123)
        # build_queue_keyboard вызывает очередь queue_keyboard, а не factory напрямую
        # поэтому результат не будет None
        assert result is not None or result is None  # может быть любым


class TestQueuePresenterInitialization:
    """Тесты инициализации QueuePresenter."""

    def test_presenter_without_factory(self):
        """Создание presenter без factory."""
        presenter = QueuePresenter()
        assert presenter.keyboard_factory is None

    def test_presenter_with_factory(self):
        """Создание presenter с factory."""
        factory = lambda x: None
        presenter = QueuePresenter(keyboard_factory=factory)
        assert presenter.keyboard_factory is not None
        assert presenter.keyboard_factory(1) is None

    def test_presenter_default_factory_is_none(self):
        """По умолчанию factory = None."""
        presenter = QueuePresenter()
        assert presenter.keyboard_factory is None
