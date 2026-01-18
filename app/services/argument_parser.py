"""
Модуль для унифицированной обработки аргументов команд очереди.
"""

from typing import Any, List, Optional, Tuple


class ArgumentParser:
    """Парсер аргументов для операций с очередью."""

    @staticmethod
    def is_integer(arg: str) -> bool:
        """Проверить, является ли аргумент числом."""
        try:
            int(arg)
            return True
        except ValueError:
            return False

    @staticmethod
    def parse_queue_name(args: list[str], queues: dict[str, dict[str, Any]]) -> tuple[str, str, list[str]]:
        """Ищет САМОЕ ДЛИННОЕ совпадение имени очереди.

        Returns: (queue_id, queue_name, rest_args)
        """
        if not args:
            return None, None, []

        best_match = None
        best_i = 0
        queue_names = {queue["name"]: queue["id"] for queue in queues.values()}
        for i in range(1, len(args) + 1):
            candidate = " ".join(args[:i])
            if candidate in queue_names:
                best_match = candidate
                best_i = i

        if best_match:
            return queue_names[best_match], best_match, args[best_i:]
        return None, None, args

    @staticmethod
    def parse_users_names(args: List[str], members: List[dict]) -> Tuple[Optional[str], Optional[str]]:
        """
        Ищет два имени в очереди из аргументов.
        Возвращает (имя1, имя2) или (None, None)
        """
        if len(args) < 2:
            return None, None

        # Извлекаем все имена из очереди
        queue_names = [user["display_name"] for user in members]

        # Пробуем найти два разных имени
        for i in range(len(args) - 1):
            name1 = " ".join(args[: i + 1])
            name2 = " ".join(args[i + 1 :])

            if name1 in queue_names and name2 in queue_names and name1 != name2:
                return name1, name2

        return None, None

    @staticmethod
    def parse_insert_args(args: List[str]) -> Tuple[str, Optional[int]]:
        """Парсер для insert операции."""
        if not args:
            return "", None

        # Попытка вынуть позицию из последнего аргумента
        try:
            desired_pos = int(args[-1]) - 1  # convert to 0-based
            user_name = " ".join(args[:-1]).strip()
            return user_name, desired_pos
        except (ValueError, IndexError):
            # Нет позиции в конце
            user_name = " ".join(args).strip()
            return user_name, None

    @staticmethod
    def parse_remove_args(args: List[str]) -> Tuple[Optional[int], Optional[str]]:
        """Парсер для remove операции.
        Если args[0] - число, вернуть его.
        Иначе объединить все args в одно имя.

        Returns:
            (position, user_name): одно из них будет None
        """
        if not args:
            return None, None
        if ArgumentParser.is_integer(args[0]):
            return int(args[0]), None
        return None, " ".join(args).strip()

    @staticmethod
    def parse_replace_args(args: List[str], members_names: List[str]):
        """
        Парсер для replace операции.
        Пытается вынуть две позиции: ["1", "2"]
        Иначе возвращает имена как есть.

        Returns:
            (pos1, pos2, name1, name2): где одна из пар None
            Пример: (1, 2, None, None) или (None, None "Alice", "Bob")
        """
        if len(args) < 2:
            return None, None, None, None

        # Попытка вынуть две позиции из конца
        try:
            if len(args) != 2:
                raise ValueError
            pos2 = int(args[-1])
            pos1 = int(args[-2])
            return pos1, pos2, None, None
        except (ValueError, IndexError):
            # Интерпретируем как имена
            first_name, second_name = ArgumentParser.parse_replace_names(args, members_names)
            return None, None, first_name, second_name

    @staticmethod
    def parse_replace_names(args: List[str], members_names: List[dict]) -> Tuple[str, str]:
        """Парсер для replace по именам.  Разбирает аргументы в два имени на основе членов очереди.

        Returns:
            (first_name, second_name)
        """
        if len(args) < 2:
            return None, None

        # Сложный случай: нужно понять где заканчивается первое имя и начинается второе
        # Используем существующие имена в очереди для определения границы

        # Пытаемся найти первое полное имя
        for i in range(1, len(args)):
            first_name = " ".join(args[:i]).strip()
            if first_name in members_names:
                second_name = " ".join(args[i:]).strip()
                if second_name in members_names:
                    return first_name, second_name

        # Fallback: первое слово vs остальное
        return None, None
