# queue/service.py
import logging
from typing import Optional

from services.logger import QueueLogger  # если logger в services
from telegram import Chat
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown
from utils.InlineKeyboards import queue_keyboard
from utils.utils import safe_delete

from .queue_repository import QueueRepository


class QueueService:
    """Бизнес-логика: чистые методы, логирование, валидация"""

    def __init__(self, repo: QueueRepository):
        self.repo = repo

    async def create_queue(self, chat_id: int, queue_name: str, chat_title: str):
        await self.repo.create_queue(chat_id, chat_title, queue_name)
        QueueLogger.log(chat_title, queue_name, "create queue")

    async def delete_queue(self, chat_id: int, queue_name: str, chat_title: str):
        deleted = await self.repo.delete_queue(chat_id, queue_name)
        if deleted:
            QueueLogger.log(chat_title, queue_name, "delete queue")
        else:
            QueueLogger.log(chat_title, queue_name, "queue not found", level=logging.WARNING)

    async def add_to_queue(self, chat_id: int, queue_name: str, user_name: str, chat_title: str):
        position = await self.repo.add_to_queue(chat_id, queue_name, user_name)
        if position:
            QueueLogger.joined(chat_title, queue_name, user_name, position)

    async def remove_from_queue(self, chat_id: int, queue_name: str, user_name: str, chat_title: str):
        position = await self.repo.remove_from_queue(chat_id, queue_name, user_name)
        if position:
            QueueLogger.leaved(chat_title, queue_name, user_name, position)

    async def get_queue_text(self, chat_id: int, queue_name: str) -> str:
        queue = await self.repo.get_queue(chat_id, queue_name)
        escaped = escape_markdown(queue_name, version=2)
        text = f"*`{escaped}`*\n\n"
        if not queue:
            text += "Очередь пуста\\."
        else:
            text += "\n".join(f"{i + 1}\\. {escape_markdown(u, version=2)}" for i, u in enumerate(queue))
        return text

    async def get_queue_index(self, chat_id: int, queue_name: str) -> int:
        queues = await self.repo.get_all_queues(chat_id)
        return list(queues.keys()).index(queue_name)

    async def send_queue_message(
        self, chat: Chat, thread_id: Optional[int], context: ContextTypes.DEFAULT_TYPE, queue_name: str
    ):
        last_id = await self.repo.get_queue_message_id(chat.id, queue_name)
        if last_id:
            await safe_delete(context, chat, last_id)

        text = await self.get_queue_text(chat.id, queue_name)
        keyboard = queue_keyboard(await self.get_queue_index(chat.id, queue_name))

        sent = await context.bot.send_message(
            chat_id=chat.id,
            text=text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
            message_thread_id=thread_id,
        )
        await self.repo.set_queue_message_id(chat.id, queue_name, sent.message_id)

    async def update_queue_message(
        self,
        chat_id: int,
        queue_name: str,
        query_or_update,
        context: Optional[ContextTypes.DEFAULT_TYPE] = None,
        chat_title: str = "Unknown",
    ):
        text = await self.get_queue_text(chat_id, queue_name)
        keyboard = queue_keyboard(await self.get_queue_index(chat_id, queue_name))

        try:
            if hasattr(query_or_update, "edit_message_text"):
                await query_or_update.edit_message_text(text=text, parse_mode="MarkdownV2", reply_markup=keyboard)
                msg_id = query_or_update.message.message_id
            else:
                last_id = await self.repo.get_queue_message_id(chat_id, queue_name)
                if last_id and context:
                    await context.bot.edit_message_text(
                        chat_id=chat_id, message_id=last_id, text=text, parse_mode="MarkdownV2", reply_markup=keyboard
                    )
                    msg_id = last_id
                else:
                    raise RuntimeError("no message")
        except BadRequest as e:
            if "Message is not modified" in str(e):
                # Ничего не делаем — сообщение не изменилось
                return
            else:
                QueueLogger.log(chat_title, queue_name, f"edit failed (BadRequest): {e}", level=logging.ERROR)
                raise  # пробрасываем другие BadRequest

        except Exception as e:
            QueueLogger.log(chat_title, queue_name, f"edit failed: {e}", level=logging.ERROR)
            if context:
                sent = await context.bot.send_message(
                    chat_id=chat_id, text=text, parse_mode="MarkdownV2", reply_markup=keyboard
                )
                await self.repo.set_queue_message_id(chat_id, queue_name, sent.message_id)
            return

        await self.repo.set_queue_message_id(chat_id, queue_name, msg_id)

    async def rename_queue(self, chat_id: int, old_name: str, new_name: str, chat_title: str):
        await self.repo.rename_queue(chat_id, old_name, new_name)
        QueueLogger.log(chat_title, f"{old_name} → {new_name}", "rename queue")

    async def generate_queue_name(self, chat_id: int) -> str:
        i = 1
        while await self.repo.get_queue(chat_id, f"Очередь {i}"):
            i += 1
        return f"Очередь {i}"

    async def get_count_queues(self, chat_id: int) -> int:
        queues = await self.repo.get_all_queues(chat_id)
        return len(queues)

    async def update_existing_queues_info(self, bot, chat: Chat, chat_title: str):
        """
        Обновляет все сообщения с очередями в чате.
        """
        queues = await self.repo.get_all_queues(chat.id)
        if not queues:
            return

        for queue_index, (queue_name, queue_data) in enumerate(queues.items()):
            message_id = queue_data.get("last_queue_message_id")
            if not message_id:
                continue

            try:
                await bot.edit_message_text(
                    chat_id=chat.id,
                    message_id=message_id,
                    text=await self.get_queue_text(chat.id, queue_name),
                    parse_mode="MarkdownV2",
                    reply_markup=queue_keyboard(queue_index),
                )
            except BadRequest as e:
                if "Message is not modified" in e.message:
                    continue
                else:
                    raise
            except Exception as ex:
                error_type = type(ex).__name__
                error_message = str(ex)
                QueueLogger.log(
                    chat_title,
                    queue_name,
                    f"{error_type}: {error_message}",
                    level=logging.ERROR,
                )
