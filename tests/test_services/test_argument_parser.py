import pytest

from app.queues.models import Member, Queue
from app.services.argument_parser import ArgumentParser


@pytest.mark.parametrize(
    "arg, expected", [("123", True), ("-5", True), ("0", True), ("abc", False), ("1.5", False), ("", False)]
)
def test_is_integer(arg, expected):
    assert ArgumentParser.is_integer(arg) == expected


@pytest.fixture
def sample_queues():
    return {
        "id1": Queue(id="id1", name="queue"),
        "id2": Queue(id="id2", name="my queue"),
        "id3": Queue(id="id3", name="my queue long name"),
    }


@pytest.fixture
def sample_members():
    return [
        Member(user_id=None, display_name="Alice"),
        Member(user_id=None, display_name="Bob"),
        Member(user_id=None, display_name="Charlie Chaplin"),
    ]


@pytest.mark.parametrize(
    "args, expected",
    [
        (["queue", "arg1"], ("id1", "queue", ["arg1"])),
        (["my", "queue", "arg2"], ("id2", "my queue", ["arg2"])),
        (["my", "queue", "long", "name", "arg3"], ("id3", "my queue long name", ["arg3"])),
        (["unknown", "queue_names"], (None, None, ["unknown", "queue_names"])),
        ([], (None, None, [])),
    ],
)
def test_parse_queue_name(sample_queues, args, expected):
    assert ArgumentParser.parse_queue_name(args, sample_queues) == expected


@pytest.mark.parametrize(
    "args, expected",
    [
        (["Alice", "Bob"], ("Alice", "Bob")),
        (["Charlie", "Chaplin", "Alice"], ("Charlie Chaplin", "Alice")),
        (["Bob", "Charlie", "Chaplin"], ("Bob", "Charlie Chaplin")),
        (["Unknown", "Alice"], (None, None)),
        (["Alice"], (None, None)),
        (["Alice", "Alice"], (None, None)),
    ],
)
def test_parse_users_names(sample_members, args, expected):
    assert ArgumentParser.parse_users_names(args, sample_members) == expected


@pytest.mark.parametrize(
    "args, expected",
    [
        (["user1", "2"], ("user1", 1)),
        (["multi", "word", "user", "1"], ("multi word user", 0)),
        (["user2"], ("user2", None)),
        ([], ("", None)),
        (["user", "with", "no", "pos"], ("user with no pos", None)),
    ],
)
def test_parse_insert_args(args, expected):
    assert ArgumentParser.parse_insert_args(args) == expected


@pytest.mark.parametrize(
    "args, expected",
    [
        (["-10"], (-10, None)),
        (["3"], (3, None)),
        (["user1"], (None, "user1")),
        (["multi", "word", "user"], (None, "multi word user")),
        ([], (None, None)),
    ],
)
def test_parse_remove_args(args, expected):
    assert ArgumentParser.parse_remove_args(args) == expected


@pytest.mark.parametrize(
    "args, members, expected",
    [
        (["user1", "user2"], [Member(None, "user1"), Member(None, "user2")], (None, None, "user1", "user2")),
        (
            ["First", "User", "Second", "User"],
            [Member(None, "First User"), Member(None, "Second User")],
            (None, None, "First User", "Second User"),
        ),
        (
            ["First", "User", "Second", "User", "1", "2"],
            [Member(None, "First User"), Member(None, "Second User 1 2")],
            (None, None, "First User", "Second User 1 2"),
        ),
        (["5", "2"], [], (5, 2, None, None)),
        (["5", "6", "2"], [], (None, None, None, None)),
        (["arg1"], ["arg1"], (None, None, None, None)),
        (["user", "not", "in", "list"], [Member(None, "some"), Member(None, "other")], (None, None, None, None)),
    ],
)
def test_parse_replace_args(args, members, expected):
    # Корректировка для последнего теста, чтобы он соответствовал логике
    assert ArgumentParser.parse_replace_args(args, members) == expected


@pytest.mark.parametrize(
    "args, target_flags, expected",
    [
        (["test", "queue", "-h", "24"], {"-h": None}, (["test", "queue"], {"-h": "24"})),
        (["test", "queue", "-h", "24"], {"-h": None, "-f": None}, (["test", "queue"], {"-h": "24", "-f": None})),
        (
            ["test", "-f", "f_val", "queue", "-h", "24"],
            {"-h": None, "-f": None},
            (["test", "queue"], {"-h": "24", "-f": "f_val"}),
        ),
        (
            ["test", "queue", "-f", "flag_value"],
            {"-h": None, "-f": None},
            (["test", "queue"], {"-h": None, "-f": "flag_value"}),
        ),
        (["test", "queue"], {"-h": None}, (["test", "queue"], {"-h": None})),
        (["-h", "24"], {"-h": None}, ([], {"-h": "24"})),
    ],
)
def test_parse_flags_args(args, target_flags, expected):
    assert ArgumentParser.parse_flags_args(args, target_flags) == expected
