import asyncio
from datetime import datetime
import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, User

from config import STUDENTS_USERNAMES


async def start_help(update, context):
    chat = update.effective_chat
    message_id = update.message.message_id
    message_thread_id = update.message.message_thread_id
    await safe_delete(context, chat, message_id)

    await context.bot.send_message(
        chat_id=chat.id,
        text="Этот бот позволяет вставать в очередь, выходить из неё, видеть текущую очередь. Используйте кнопки или команды:\n"
             "/join – встать в очередь\n"
             "/leave – выйти из очередь\n"
             "/queue – посмотреть очередь\n\n"
             "Команды для администраторов:\n"
             "/clear - очистить очередь\n"
             "/insert <Имя пользователя> <Индекс> - вставить  <Имя пользователя> на <Индекс> место в очереди\n"
             "/remove <Имя пользователя> или <Индекс> - удалить <Имя пользователя> или <Индекс> из очереди\n"
             "/replace <Индекс1> <Индекс2> - поменять местами <Индекс1> и <Индекс2> в очереди\n",
        message_thread_id=message_thread_id
    )


# Безопасное удаление сообщения.
async def safe_delete(context, chat, message_id):
    try:
        await context.bot.delete_message(chat_id=chat.id, message_id=message_id)
    except Exception as e:
        print(
            f"{chat.title if chat.title else chat.username}: {get_time()} Не удалось удалить сообщение {message_id}: {e}",
            flush=True)


def get_time():
    moscow_tz = pytz.timezone('Europe/Moscow')
    moscow_time = datetime.now(moscow_tz)
    return moscow_time.strftime("%D %H:%M:%S")


def get_name(user: User):
    if user.username in STUDENTS_USERNAMES:
        name = STUDENTS_USERNAMES[user.username][0]
    else:
        name = f"{user.first_name} {user.last_name or ''}".strip()
    return name


async def delete_later(context, chat, message_id, time=5):
    await asyncio.sleep(time)
    await safe_delete(context, chat, message_id)
