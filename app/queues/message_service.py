import logging

from telegram.error import BadRequest
from telegram.ext import ContextTypes

from app.queues.models import ActionContext
from app.queues.queue_repository import QueueRepository
from app.services.logger import QueueLogger
from app.utils.utils import safe_delete

from .errors import MessageServiceError


class QueueMessageService:
    """
    Работа с Telegram: отправка/редактирование/удаление сообщений.
    Отвечает также за сохранение message_id через repo (repo должен быть передан).
    """

    def __init__(self, repo, bot_logger=QueueLogger):
        self.repo: QueueRepository = repo
        self.logger = bot_logger

    async def send_queue_message(self, ctx: ActionContext, text: str, keyboard, context: ContextTypes.DEFAULT_TYPE):
        """
        Отправить сообщение о очереди: при наличии старого — удалить.
        Сохраняет message_id в repo.
        """
        try:
            last_id = await self.repo.get_queue_message_id(ctx.chat_id, ctx.queue_id)
            if last_id:
                await safe_delete(context.bot, ctx, last_id)

            sent = await context.bot.send_message(
                chat_id=ctx.chat_id,
                text=text,
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
                message_thread_id=ctx.thread_id,
                disable_notification=True,
            )
            await self.repo.set_queue_message_id(ctx.chat_id, ctx.queue_id, sent.message_id)
            return sent.message_id
        except Exception as ex:
            self.logger.log(ctx, f"send failed: {type(ex).__name__}: {ex}", level=logging.ERROR)
            raise MessageServiceError(ex)

    async def edit_queue_message(self, context: ContextTypes.DEFAULT_TYPE, ctx, text: str, keyboard):
        """
        Попытаться отредактировать сообщение, если не получается - отправляем новое:
        Возвращает message_id
        """
        msg_id = None

        try:
            msg_id = await self.repo.get_queue_message_id(ctx.chat_id, ctx.queue_id)
            if msg_id and context:
                await context.bot.edit_message_text(
                    chat_id=ctx.chat_id,
                    message_id=msg_id,
                    text=text,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )
            else:
                raise RuntimeError("Queue message not found, will send new message")
        except BadRequest as ex:
            # игнорируем "Message is not modified"
            if "not modified" in str(ex).lower():
                return msg_id
            self.logger.log(ctx, f"edit failed (BadRequest): {ex}", level=logging.ERROR)
            raise MessageServiceError(ex)
        except Exception as ex:
            # log and fallback to sending new message (if bot context available)
            self.logger.log(ctx, f"edit failed: {ex}", level=logging.ERROR)
            if context:
                sent = await context.bot.send_message(
                    chat_id=ctx.chat_id,
                    text=text,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                    disable_notification=True,
                )
                await self.repo.set_queue_message_id(ctx.chat_id, ctx.queue_id, sent.message_id)
                return sent.message_id
            raise MessageServiceError(ex)

        return msg_id

    async def hide_queues_list_message(self, context, ctx, last_queues_id=None):
        if not last_queues_id:
            last_queues_id = await self.repo.get_list_message_id(ctx.chat_id)
        if last_queues_id:
            await safe_delete(context.bot, ctx, last_queues_id)
            await self.repo.clear_list_message_id(ctx.chat_id)
