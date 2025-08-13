import asyncio
from telegram import User

from config import STUDENTS_USERNAMES
from services.queue_logger import QueueLogger


async def start_help(update, context):
    chat = update.effective_chat
    message_id = update.message.message_id
    message_thread_id = update.message.message_thread_id
    await safe_delete(context, chat, message_id)

    text = (
        "/create <Имя очереди> - создает очередь\n"
        "/queues - посмотреть активные очереди\n\n"
        "Команды для администраторов:\n"
        "/delete <Имя очереди> - удалить очередь\n"
        "/delete_all - удалить все очереди\n"
        "/insert <Имя очереди> <Имя пользователя> <Индекс> - вставить  <Имя пользователя> на <Индекс> место в очереди\n"
        "/remove <Имя очереди> <Имя пользователя> или <Индекс> - удалить <Имя пользователя> или <Индекс> из очереди\n"
        "/replace <Имя очереди> <Индекс1> <Индекс2> - поменять местами <Индекс1> и <Индекс2> в очереди\n"
    )

    await context.bot.send_message(
        chat_id=chat.id,
        text=text,
        message_thread_id=message_thread_id
    )


# Безопасное удаление сообщения.
async def safe_delete(context, chat, message_id):
    try:
        await context.bot.delete_message(chat_id=chat.id, message_id=message_id)
    except Exception as e:
        QueueLogger.log(chat.title or chat.username, action=f"Не удалось удалить сообщение {message_id}: {e}")


def get_user_name(user: User):
    if user.username in STUDENTS_USERNAMES:
        name = STUDENTS_USERNAMES[user.username][0]
    else:
        name = f"{user.first_name} {user.last_name or ''}".strip()
    return name


async def delete_later(context, chat, message_id, time=5):
    await asyncio.sleep(time)
    await safe_delete(context, chat, message_id)
