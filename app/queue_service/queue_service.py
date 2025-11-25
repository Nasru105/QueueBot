import logging
from dataclasses import dataclass
from typing import Optional

from telegram import User
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

from app.services.logger import QueueLogger
from app.utils.InlineKeyboards import queue_keyboard
from app.utils.utils import safe_delete, strip_user_full_name

from .queue_repository import QueueRepository


@dataclass
class ActionContext:
    chat_id: int
    chat_title: str = ""
    queue_name: str = ""
    actor: str = ""
    thread_id: Optional[int] = None


class QueueService:
    def __init__(self, repo: QueueRepository):
        self.repo = repo

    async def create_queue(self, ctx: ActionContext):
        await self.repo.create_queue(ctx.chat_id, ctx.chat_title, ctx.queue_name)
        QueueLogger.log(ctx.chat_title, ctx.queue_name, ctx.actor, "create queue")

    async def delete_queue(self, ctx: ActionContext):
        deleted = await self.repo.delete_queue(ctx.chat_id, ctx.queue_name)
        if deleted:
            QueueLogger.log(ctx.chat_title, ctx.queue_name, ctx.actor, "delete queue")
        else:
            QueueLogger.log(ctx.chat_title, ctx.queue_name, ctx.actor, "queue not found", level=logging.WARNING)

    async def join_to_queue(self, ctx: ActionContext, user_name: str):
        position = await self.repo.add_to_queue(ctx.chat_id, ctx.queue_name, user_name)
        if position:
            QueueLogger.joined(ctx.chat_title, ctx.queue_name, ctx.actor, user_name, position)

    async def leave_from_queue(self, ctx: ActionContext, user_name: str):
        position = await self.repo.remove_from_queue(ctx.chat_id, ctx.queue_name, user_name)
        if position:
            QueueLogger.leaved(ctx.chat_title, ctx.queue_name, ctx.actor, user_name, position)

    async def remove_from_queue(self, ctx: ActionContext, args: list[str]):
        """
        Возвращает:
        - removed_name: str | None
        - position: int | None (1-based)
        - updated_queue: list[str] | None
        """

        queue = await self.repo.get_queue(ctx.chat_id, ctx.queue_name)
        if queue is None:
            return None, None, None

        removed_name = None
        position = None

        # Пробуем удалить по позиции
        try:
            pos = int(args[0]) - 1
            if 0 <= pos < len(queue):
                removed_name = queue.pop(pos)
                position = pos + 1
        except (ValueError, IndexError):
            # Удаление по имени
            user_name = " ".join(args).strip()
            if user_name in queue:
                pos = queue.index(user_name)
                removed_name = user_name
                position = pos + 1
                queue.remove(user_name)

        if removed_name:
            await self.repo.update_queue(ctx.chat_id, ctx.queue_name, queue)
            QueueLogger.removed(ctx.chat_title, ctx.queue_name, ctx.actor, removed_name, position)
        return removed_name, position, queue

    async def insert_into_queue(self, ctx: ActionContext, args: list[str]):
        """
        Логика вставки пользователя в очередь.

        args — остаток после имени очереди.
        Возвращает:
            user_name: str
            position: int (1-based)
            updated_queue: list[str]
            old_position: int | None
        """
        queue = await self.repo.get_queue(ctx.chat_id, ctx.queue_name)
        if queue is None:
            return None, None, None, None

        # Определяем, является ли последний аргумент позицией
        try:
            position = int(args[-1]) - 1
            user_name = " ".join(args[:-1]).strip()
        except (ValueError, IndexError):
            user_name = " ".join(args).strip()
            position = len(queue)

        # Ограничиваем позицию от 0 до len(queue)
        position = max(0, min(position, len(queue)))

        old_position = None

        # Если пользователь уже в очереди — удаляем
        if user_name in queue:
            old_position = queue.index(user_name) + 1
            queue.remove(user_name)

        # Вставляем на нужную позицию
        queue.insert(position, user_name)

        await self.repo.update_queue(ctx.chat_id, ctx.queue_name, queue)

        if old_position:
            QueueLogger.removed(ctx.chat_title, ctx.queue_name, ctx.actor, user_name, old_position + 1)
        QueueLogger.inserted(ctx.chat_title, ctx.queue_name, ctx.actor, user_name, position + 1)

        return user_name, position + 1, queue, old_position

    async def get_queue_text(self, chat_id: int, queue_name: str) -> str:
        queue = await self.repo.get_queue(chat_id, queue_name)
        escaped = escape_markdown(queue_name, version=2)

        if not queue:
            return f"*`{escaped}`*\n\nОчередь пуста\\."

        lines = [f"{i + 1}\\. {escape_markdown(u, version=2)}" for i, u in enumerate(queue)]
        return f"*`{escaped}`*\n\n" + "\n".join(lines)

    async def get_queue_index(self, chat_id: int, queue_name: str) -> int:
        queues = await self.repo.get_all_queues(chat_id)
        return list(queues.keys()).index(queue_name)

    async def send_queue_message(self, ctx: ActionContext, context: ContextTypes.DEFAULT_TYPE):
        last_id = await self.repo.get_queue_message_id(ctx.chat_id, ctx.queue_name)
        if last_id:
            await safe_delete(context, ctx, last_id)

        text = await self.get_queue_text(ctx.chat_id, ctx.queue_name)
        keyboard = queue_keyboard(await self.get_queue_index(ctx.chat_id, ctx.queue_name))

        sent = await context.bot.send_message(
            chat_id=ctx.chat_id,
            text=text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
            message_thread_id=ctx.thread_id,
        )
        await self.repo.set_queue_message_id(ctx.chat_id, ctx.queue_name, sent.message_id)

    async def update_queue_message(
        self,
        ctx: ActionContext,
        query_or_update=None,
        context: Optional[ContextTypes.DEFAULT_TYPE] = None,
    ):
        text = await self.get_queue_text(ctx.chat_id, ctx.queue_name)
        keyboard = queue_keyboard(await self.get_queue_index(ctx.chat_id, ctx.queue_name))

        try:
            # 1. Query with edit capability
            if hasattr(query_or_update, "edit_message_text"):
                msg_id = query_or_update.message.message_id
                await query_or_update.edit_message_text(text=text, parse_mode="MarkdownV2", reply_markup=keyboard)

            # 2. Fallback: edit by stored ID
            else:
                last_id = await self.repo.get_queue_message_id(ctx.chat_id, ctx.queue_name)
                if last_id and context:
                    msg_id = last_id
                    await context.bot.edit_message_text(
                        chat_id=ctx.chat_id,
                        message_id=last_id,
                        text=text,
                        parse_mode="MarkdownV2",
                        reply_markup=keyboard,
                    )
                else:
                    raise RuntimeError("Queue message not found")

        except BadRequest as e:
            if "Message is not modified" in str(e):
                return
            QueueLogger.log(
                ctx.chat_title, ctx.queue_name, ctx.actor, f"edit failed (BadRequest): {e}", level=logging.ERROR
            )
            raise

        except Exception as e:
            QueueLogger.log(ctx.chat_title, ctx.queue_name, ctx.actor, f"edit failed: {e}", level=logging.ERROR)
            if context:
                sent = await context.bot.send_message(
                    chat_id=ctx.chat_id,
                    text=text,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )
                await self.repo.set_queue_message_id(ctx.chat_id, ctx.queue_name, sent.message_id)
            return

        await self.repo.set_queue_message_id(ctx.chat_id, ctx.queue_name, msg_id)

    async def rename_queue(self, ctx: ActionContext, new_name: str):
        await self.repo.rename_queue(ctx.chat_id, ctx.queue_name, new_name)
        QueueLogger.log(ctx.chat_title, ctx.queue_name, ctx.actor, f"rename queue → {new_name}")

    async def generate_queue_name(self, chat_id: int) -> str:
        i = 1
        queues = await self.repo.get_all_queues(chat_id)
        while f"Очередь {i}" in queues:
            i += 1
        return f"Очередь {i}"

    async def get_count_queues(self, chat_id: int) -> int:
        queues = await self.repo.get_all_queues(chat_id)
        return len(queues)

    async def get_user_display_name(self, user: User, chat_id: int) -> str:
        doc_user = await self.repo.get_user_display_name(user)
        chat_str = str(chat_id)

        return (
            doc_user["display_names"].get(chat_str)
            or doc_user["display_names"].get("global")
            or f"{user.get('last_name', '').strip()} {user.get('first_name', '').strip()}".strip()
            or user.get("username", "Unknown User")
        )

    async def set_user_display_name(self, ctx: ActionContext, user: User, display_name: str):
        user_doc = await self.repo.get_user_display_name(user)
        chat_str = str(ctx.chat_id)

        if "display_names" not in user_doc:
            user_doc["display_names"] = {}

        user_doc["display_names"][chat_str] = display_name or strip_user_full_name(user)
        await self.repo.update_user_display_name(user.id, user_doc["display_names"])

        QueueLogger.log(ctx.chat_title, ctx.queue_name, ctx.actor, f"set display name → {display_name}")

    async def clear_user_display_name(self, ctx: ActionContext, user: User):
        user_doc = await self.repo.get_user_display_name(user)
        chat_str = str(ctx.chat_id)

        if "display_names" not in user_doc:
            return

        user_doc["display_names"].pop(chat_str, None)

        await self.repo.update_user_display_name(user.id, user_doc["display_names"])

        QueueLogger.log(ctx.chat_title, ctx.queue_name, ctx.actor, "clear display name")

    async def update_existing_queues_info(self, bot, ctx: ActionContext):
        queues = await self.repo.get_all_queues(ctx.chat_id)
        if not queues:
            return

        for queue_index, (queue_name, queue_data) in enumerate(queues.items()):
            message_id = queue_data.get("last_queue_message_id")
            if not message_id:
                continue

            try:
                await bot.edit_message_text(
                    chat_id=ctx.chat_id,
                    message_id=message_id,
                    text=await self.get_queue_text(ctx.chat_id, queue_name),
                    parse_mode="MarkdownV2",
                    reply_markup=queue_keyboard(queue_index),
                )
            except BadRequest as e:
                if "Message is not modified" in e.message:
                    continue
                else:
                    raise
            except Exception as ex:
                QueueLogger.log(
                    ctx.chat_title,
                    queue_name,
                    ctx.actor,
                    f"mass-update failed: {type(ex).__name__}: {ex}",
                    level=logging.ERROR,
                )
