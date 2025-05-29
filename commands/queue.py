# Импорт необходимых типов из библиотеки telegram.ext
from telegram.ext import ContextTypes, CallbackQueryHandler
# Импорт функций работы с очередью
from services.queue_service import (
    add_to_queue, remove_from_queue, get_queue, get_last_message_id,
    set_last_message_id, get_queue_message
)
# Импорт утилит: удаление сообщений и клавиатура с кнопками
from utils.utils import safe_delete, get_queue_keyboard
# Импорт основного объекта Update
from telegram import Update


# Команда /join — добавляет пользователя в очередь
async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # Получаем имя пользователя
    user = f"{update.effective_user.first_name} {update.effective_user.last_name}"
    # Добавляем пользователя в очередь
    add_to_queue(chat_id, user)
    # Обновляем сообщение с очередью
    await queue(update, context)


# Команда /leave — удаляет пользователя из очереди
async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # Получаем имя пользователя
    user = f"{update.effective_user.first_name} {update.effective_user.last_name}"
    # Удаляем пользователя из очереди
    remove_from_queue(chat_id, user)
    # Обновляем сообщение с очередью
    await queue(update, context)


# Команда /queue — выводит текущее состояние очереди
async def queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    message_id = update.message.message_id  # ID команды вызова
    message_thread_id = update.message.message_thread_id  # Тема сообщений в супергруппе

    # Удаляем сообщение с командой /queue
    await safe_delete(context, chat_id, message_id)

    # Удаляем предыдущее сообщение с очередью, если оно существует
    last_id = get_last_message_id(chat_id)
    await safe_delete(context, chat_id, last_id)

    # Отправляем новое сообщение с обновлённой очередью
    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=get_queue_message(chat_id),          # Получаем текст очереди
        reply_markup=get_queue_keyboard(),        # Добавляем inline-кнопки
        message_thread_id=message_thread_id       # Указываем тему, если это супергруппа
    )
    # Сохраняем ID нового сообщения с очередью, чтобы позже можно было удалить
    set_last_message_id(chat_id, sent.message_id)
