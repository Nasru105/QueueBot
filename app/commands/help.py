from typing import Dict, Optional

from telegram import Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

from app.queues.models import ActionContext
from app.utils.utils import delete_message_later, split_text, with_ctx


class CommandHelp:
    """Класс для хранения информации о командах"""

    COMMANDS: Dict[str, Dict] = {
        "start": {
            "description": "Начало работы с ботом",
            "usage": "/start",
            "details": ("Показывает приветственное сообщение и краткую информацию о боте.",),
            "category": "Основные",
        },
        "help": {
            "description": "Справка по командам бота",
            "usage": "/help [команда]",
            "details": ("Показывает общую справку или подробную информацию по конкретной команде.",),
            "category": "Основные",
        },
        "commands": {
            "description": "Список всех доступных команд",
            "usage": "/commands",
            "details": ("Показывает краткий список всех команд с их кратким описанием.",),
            "category": "Основные",
        },
        "create": {
            "description": "Создание новой очереди",
            "usage": "/create [Имя очереди] [-h часы]",
            "details": (
                "Создаёт новую очередь с указанным именем и временем жизни.",
                "• Параметр -h задаёт срок жизни очереди в часах",
                "• Если не указать -h, очередь живёт 24 часа",
                "• Срок жизни продлевается на 1 час после последнего обновления очереди",
            ),
            "examples": ("/create Дежурство", "/create -h 3", "/create Дежурство -h 12"),
            "category": "Очереди",
        },
        "queues": {
            "description": "Меню взаимодействия с очередями",
            "usage": "/queues",
            "details": ("Открывает меню взаимодействия с очередями в текущем чате.",),
            "category": "Очереди",
        },
        "nickname_global": {
            "description": "Установка глобального отображаемого имени",
            "usage": "/nickname_global [имя]",
            "details": (
                "Задаёт имя, которое будет отображаться во всех чатах.",
                "• Используется, если не задано локальное имя",
                "• Без параметров — сброс к стандартному имени",
            ),
            "category": "Профиль",
        },
        "nickname": {
            "description": "Установка отображаемого имени в текущем чате",
            "usage": "/nickname [имя]",
            "details": (
                "Задаёт имя, которое будет отображаться в текущем чате.",
                "• Имеет приоритет над глобальным именем",
                "• Без параметров — сброс к глобальному имени",
            ),
            "category": "Профиль",
        },
        "delete": {
            "description": "Удаление очереди",
            "usage": "/delete <Имя очереди>",
            "details": ("Удаляет указанную очередь (только для администраторов).",),
            "admin": True,
            "category": "Администрирование",
        },
        "delete_all": {
            "description": "Удаление всех очередей",
            "usage": "/delete_all",
            "details": ("Удаляет все очереди в текущем чате (только для администраторов).",),
            "admin": True,
            "category": "Администрирование",
        },
        "insert": {
            "description": "Вставка пользователя в очередь",
            "usage": "/insert <Очередь> <Пользователь> [Позиция]",
            "details": (
                "Вставляет пользователя в указанную очередь на заданную позицию.",
                "• Если позиция не указана, добавляет в конец",
                "• Позиция считается с 1",
            ),
            "examples": ("/insert Дежурство Иван Иванов", "/insert Дежурство Иван Иванов 3"),
            "admin": True,
            "category": "Администрирование",
        },
        "remove": {
            "description": "Удаление пользователя из очереди",
            "usage": "/remove <Очередь> <Пользователь или Позиция>",
            "details": (
                "Удаляет пользователя или позицию из очереди.",
                "• Можно указать имя пользователя или номер позиции",
                "• Позиция считается с 1",
            ),
            "examples": ("/remove Дежурство Иван Иванов", "/remove Дежурство 3"),
            "admin": True,
            "category": "Администрирование",
        },
        "replace": {
            "description": "Замена позиций в очереди",
            "usage": "/replace <Очередь> <Позиция 1> <Позиция 2>\n/replace <Очередь> <Пользователь 1> <Пользователь 2>",
            "details": (
                "Меняет местами две позиции или двух пользователей в очереди.",
                "• Позиции считаются с 1",
                "• Можно использовать имена пользователей или номера позиций",
            ),
            "examples": ("/replace Дежурство 2 5", "/replace Дежурство Иван Иванов Петя Петров"),
            "admin": True,
            "category": "Администрирование",
        },
        "rename": {
            "description": "Переименование очереди",
            "usage": "/rename <Старое имя> <Новое имя>",
            "details": ("Изменяет название существующей очереди.",),
            "examples": ("/rename Отличники Список на отчисление",),
            "admin": True,
            "category": "Администрирование",
        },
        "set_description": {
            "description": "Изменение описания очереди",
            "usage": "/set_description <Очередь> [описание]",
            "details": (
                "Устанавливает описание очереди.",
                "Без параметра [описание] для сброса описания",
            ),
            "examples": (
                "/set_description Дежурство Очередь дежурства на этой неделе",
                "/set_description Дежурство",
            ),
            "admin": True,
            "category": "Администрирование",
        },
        "set_expire_time": {
            "description": "Изменение времени жизни очереди",
            "usage": "/set_expire_time <Очередь> <часы>",
            "details": ("Устанавливает новое время автоудаления очереди в часах.",),
            "admin": True,
            "category": "Администрирование",
        },
        "set_update_count": {
            "description": "Автоматическое обновление очереди",
            "usage": "/set_update_count [Очередь] [количество сообщений]",
            "details": (
                "Устанавливает автоматическое обновление очереди через указанное количество сообщений.",
                "Без параметра [Очередь] для установки для всех очередей",
                "Без параметра [количество сообщений] или со значением 0 для сброса автоматического обновления",
            ),
            "admin": True,
            "category": "Администрирование",
        },
    }

    @classmethod
    def get_command_info(cls, command: str) -> Optional[Dict]:
        """Получить информацию о конкретной команде"""
        return cls.COMMANDS.get(command.strip("/").lower())

    @classmethod
    def get_commands_by_category(cls) -> Dict[str, list]:
        """Сгруппировать команды по категориям"""
        categorized = {}
        for cmd, info in cls.COMMANDS.items():
            category = info.get("category", "Другие")
            if category not in categorized:
                categorized[category] = []
            categorized[category].append((cmd, info))
        return categorized

    @classmethod
    def format_command_help(cls, command: str, detailed: bool = True) -> str:
        """Форматировать справку по команде"""
        info = cls.get_command_info(command)
        if not info:
            return False

        lines = []

        # Заголовок
        lines.append(f"🔹 */{escape_markdown(command, version=2)}*")
        lines.append(f"_{info['description']}_")
        lines.append("")

        # Флаг администратора
        if info.get("admin"):
            lines.append("⚡ *Только для администраторов*")

        # Использование
        lines.append("📝 *Использование:*")
        lines.append(f"`{escape_markdown(info['usage'], version=2)}`")
        lines.append("")

        if detailed:
            # Подробное описание
            lines.append("📋 *Описание:*")
            for detail in info["details"]:
                lines.append(escape_markdown(detail, version=2))

            # Примеры
            if "examples" in info:
                lines.append("")
                lines.append("🎯 *Примеры:*")
                for example in info["examples"]:
                    lines.append(f"• `{escape_markdown(example, version=2)}`")

        return lines

    @classmethod
    def format_all_commands_help(cls):
        lines = ["🤖 *QueueBot \\- справка по командам*", ""]

        categorized = cls.get_commands_by_category()
        for category, commands in categorized.items():
            if category != "Основные":
                for cmd, info in commands:
                    text = cls.format_command_help(cmd)
                    for line in text:
                        lines.append(f">{line}")
                    lines.append("")
        return "\n".join(lines)

    @classmethod
    def format_all_commands(cls) -> str:
        """Форматировать список всех команд"""
        lines = ["🤖 *QueueBot \\- Список команд*", ""]

        categorized = cls.get_commands_by_category()
        for category, commands in categorized.items():
            lines.append(f"📌 *{escape_markdown(category, version=2)}:*")
            for cmd, info in commands:
                cmd_name = f"{escape_markdown(info['usage'], version=2)}"
                description = f"{escape_markdown(info['description'], version=2)}"

                lines.append(f"{cmd_name} — {description}")

            lines.append("")

        lines.append("ℹ️ Для подробной информации используйте /help \\[команда\\]")
        return "\n".join(lines)


@with_ctx()
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext) -> None:
    """
    Показывает приветственное сообщение.
    """
    text = (
        "👋 *Добро пожаловать в QueueBot\\!*\n\n"
        "Я помогаю создавать и управлять очередями в Telegram чатах\\.\n\n"
        "📚 *Основные возможности:*\n"
        "• Создание очередей с настраиваемым временем жизни\n"
        "• Автоматическое продление времени жизни\n"
        "• Настройка отображаемых имён\n"
        "• Управление очередями для администраторов\n\n"
        "📖 *Используйте команды:*\n"
        "/help — справка по командам\n"
        "/help \\[команда\\] — подробная справка по определенной команде\n"
        "/commands — список команд\n\n"
        "🚀 *Начните работу:*\n"
        "/create — создает очередь которая удалиться через 24 часа\n"
        "/queues — меню взаимодействия с очередями\n\n"
    )
    await context.bot.send_message(
        chat_id=ctx.chat_id,
        text=text,
        message_thread_id=ctx.thread_id,
        parse_mode="MarkdownV2",
        disable_notification=True,
    )


@with_ctx()
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext) -> None:
    """
    Показывает справку по командам.
    """
    args = context.args

    if args and len(args) > 0:
        command = args[0]
        text = "\n".join(CommandHelp.format_command_help(command))
        if not text:
            await delete_message_later(context, ctx, f"❌ Команда `{command}` не найдена.")
            return
    else:
        text = CommandHelp.format_all_commands_help()

    parts = split_text(text, "🔹")
    for part in parts:
        await context.bot.send_message(
            chat_id=ctx.chat_id,
            text=part,
            message_thread_id=ctx.thread_id,
            parse_mode="MarkdownV2",
            disable_notification=True,
        )


@with_ctx()
async def commands_list(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext) -> None:
    text = CommandHelp.format_all_commands()

    await context.bot.send_message(
        chat_id=ctx.chat_id,
        text=text,
        message_thread_id=ctx.thread_id,
        parse_mode="MarkdownV2",
        disable_notification=True,
    )


# async def get_command(command: Optional[str] = None) -> Dict:
#     """
#     Получить информацию о команде/командах.
#     """
#     if command:
#         info = CommandHelp.get_command_info(command)
#         if info:
#             return {command: info}
#         return {}

#     # Возвращаем все команды
#     commands_info = {}
#     for cmd_name in CommandHelp.COMMANDS:
#         cmd = CommandHelp.get_command_info(cmd_name)
#         if cmd:
#             # Упрощаем информацию для внешнего использования
#             commands_info[cmd_name] = {
#                 "description": cmd["description"],
#                 "usage": cmd["usage"],
#                 "category": cmd["category"],
#                 "admin": cmd.get("admin", False),
#             }

#     return commands_info
