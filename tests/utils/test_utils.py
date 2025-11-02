from types import SimpleNamespace

from app.config import STUDENTS_USERNAMES
from app.utils.utils import get_user_name, parse_queue_args


def test_parse_queue_args_exact_match():
    args = ["Очередь", "1", "foo"]
    queues = ["Очередь 1", "Другие"]
    qname, rest = parse_queue_args(args, queues)
    assert qname == "Очередь 1"
    assert rest == ["foo"]


def test_parse_queue_args_no_match():
    args = ["Неизвестно"]
    queues = ["A", "B"]
    qname, rest = parse_queue_args(args, queues)
    assert qname is None
    assert rest == []


def test_get_user_name_from_students():
    # Берём первый ключ из STUDENTS_USERNAMES
    username, (name, grp) = next(iter(STUDENTS_USERNAMES.items()))
    user = SimpleNamespace(username=username, first_name="X", last_name=None)
    assert get_user_name(user) == name


def test_get_user_name_fallback():
    user = SimpleNamespace(username="no_such", first_name="Ivan", last_name="Petrov")
    assert get_user_name(user) == "Ivan Petrov"
