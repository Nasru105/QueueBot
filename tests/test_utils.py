"""
Тесты для утилит-функций.
"""

from app.utils.utils import parse_queue_args, parse_users_names


class TestParseQueueArgs:
    """Тесты парсинга аргументов команды."""

    def test_empty_args(self):
        """Пустые аргументы."""
        queue_name, remaining = parse_queue_args([], ["Queue 1"])
        assert queue_name is None
        assert remaining == []

    def test_single_queue_match(self):
        """Одно слово совпадает с именем очереди."""
        queue_name, remaining = parse_queue_args(["Queue"], ["Queue", "Queue 2"])
        assert queue_name == "Queue"
        assert remaining == []

    def test_two_word_queue_match(self):
        """Два слова совпадают с именем очереди."""
        queue_name, remaining = parse_queue_args(["Queue", "1"], ["Queue 1", "Queue 2"])
        assert queue_name == "Queue 1"
        assert remaining == []

    def test_longest_match(self):
        """Ищется самое длинное совпадение."""
        queue_name, remaining = parse_queue_args(["Queue", "1", "extra"], ["Queue", "Queue 1"])
        assert queue_name == "Queue 1"
        assert remaining == ["extra"]

    def test_no_match(self):
        """Нет совпадений с именами очередей."""
        queue_name, remaining = parse_queue_args(["Unknown"], ["Queue 1"])
        assert queue_name is None
        assert remaining == []

    def test_queue_with_args(self):
        """Очередь найдена, есть дополнительные аргументы."""
        queue_name, remaining = parse_queue_args(["Queue", "1", "Alice", "Bob"], ["Queue 1"])
        assert queue_name == "Queue 1"
        assert remaining == ["Alice", "Bob"]

    def test_prefer_longer_match(self):
        """Предпочитается более длинное совпадение."""
        queue_name, remaining = parse_queue_args(
            ["My", "Important", "Queue", "extra"], ["My", "My Important", "My Important Queue"]
        )
        assert queue_name == "My Important Queue"
        assert remaining == ["extra"]


class TestParseUsersNames:
    """Тесты парсинга имён пользователей."""

    def test_empty_args(self):
        """Пустые аргументы."""
        name1, name2 = parse_users_names([], ["Alice", "Bob"])
        assert name1 is None
        assert name2 is None

    def test_single_arg(self):
        """Один аргумент."""
        name1, name2 = parse_users_names(["Alice"], ["Alice", "Bob"])
        assert name1 is None
        assert name2 is None

    def test_two_single_word_names(self):
        """Два простых имени."""
        name1, name2 = parse_users_names(["Alice", "Bob"], ["Alice", "Bob", "Charlie"])
        assert name1 == "Alice"
        assert name2 == "Bob"

    def test_multi_word_names(self):
        """Имена из нескольких слов."""
        queue = ["Alice Smith", "Bob Johnson", "Charlie Brown"]
        name1, name2 = parse_users_names(["Alice", "Smith", "Bob", "Johnson"], queue)
        assert name1 == "Alice Smith"
        assert name2 == "Bob Johnson"

    def test_names_not_in_queue(self):
        """Имена не найдены в очереди."""
        queue = ["Alice", "Bob"]
        name1, name2 = parse_users_names(["Charlie", "David"], queue)
        assert name1 is None
        assert name2 is None

    def test_one_name_not_in_queue(self):
        """Одно имя есть, другого нет."""
        queue = ["Alice", "Bob"]
        name1, name2 = parse_users_names(["Alice", "Charlie"], queue)
        assert name1 is None
        assert name2 is None

    def test_same_name_twice(self):
        """Одно и то же имя дважды."""
        queue = ["Alice", "Bob"]
        name1, name2 = parse_users_names(["Alice", "Alice"], queue)
        assert name1 is None
        assert name2 is None

    def test_first_split_matches(self):
        """Первый вариант разбиения совпадает."""
        queue = ["Alice", "Bob Johnson"]
        name1, name2 = parse_users_names(["Alice", "Bob", "Johnson"], queue)
        assert name1 == "Alice"
        assert name2 == "Bob Johnson"

    def test_multiple_spaces_in_names(self):
        """Имена с пробелами."""
        queue = ["Alice M Smith", "Bob Johnson Jr"]
        name1, name2 = parse_users_names(["Alice", "M", "Smith", "Bob", "Johnson", "Jr"], queue)
        assert name1 == "Alice M Smith"
        assert name2 == "Bob Johnson Jr"
