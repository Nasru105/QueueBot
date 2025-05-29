from telegram.ext import ContextTypes
from telegram import Update

# Импорт функций для работы с очередью и утилит
from services.queue_service import (
    add_to_queue, remove_from_queue,
    get_queue_message, set_last_message_id,
    get_last_message_id
)
from utils.utils import get_queue_keyboard, safe_delete

# Обработка нажатий на inline-кнопки
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query  # Получаем объект CallbackQuery
    await query.answer()  # Отвечаем на нажатие, чтобы убрать "часики" у кнопки

    # Формируем имя пользователя (с учётом возможности отсутствия фамилии)
    user = f"{query.from_user.first_name} {query.from_user.last_name or ''}".strip()
    chat_id = query.message.chat_id  # ID чата
    message_thread_id = query.message.message_thread_id  # ID темы (если супергруппа с топиками)
    data = query.data  # Получаем данные, переданные кнопкой (join/leave/...)

    # Обработка команд
    if data == "join":
        add_to_queue(chat_id, user)  # Добавляем пользователя в очередь
    elif data == "leave":
        remove_from_queue(chat_id, user)  # Удаляем пользователя из очереди

    # Отправляем обновлённое сообщение с очередью
    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=get_queue_message(chat_id),  # Текст очереди
        reply_markup=get_queue_keyboard(),  # Inline-кнопки
        message_thread_id=message_thread_id  # Отправка в ту же тему
    )

    # Удаляем предыдущее сообщение от бота, если было
    last_id = get_last_message_id(chat_id)
    if last_id:
        await safe_delete(context, chat_id, last_id)

    # Сохраняем ID нового сообщения
    set_last_message_id(chat_id, sent.message_id)
