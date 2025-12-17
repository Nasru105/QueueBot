import logging
from typing import Dict, Optional

from telegram.error import BadRequest
from telegram.ext import ContextTypes, ExtBot

from app.queues.models import ActionContext
from app.queues.presenter import QueuePresenter
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
            last_id = await self.repo.get_queue_message_id(ctx.chat_id, ctx.queue_name)
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
            await self.repo.set_queue_message_id(ctx.chat_id, ctx.queue_name, sent.message_id)
            return sent.message_id
        except Exception as ex:
            self.logger.log(
                ctx.chat_title,
                ctx.queue_name,
                ctx.actor,
                f"send failed: {type(ex).__name__}: {ex}",
                level=logging.ERROR,
            )
            raise MessageServiceError(ex)

    async def edit_queue_message(
        self, ctx, text: str, keyboard, query_or_update=None, context: Optional[ContextTypes.DEFAULT_TYPE] = None
    ):
        """
        Попытаться отредактировать сообщение тремя способами:
        1) используем query_or_update.edit_message_text, если есть
        2) иначе используем message_id из repo и context.bot.edit_message_text
        3) иначе отправляем новое сообщение
        Возвращает message_id
        """
        msg_id = None
        try:
            if hasattr(query_or_update, "edit_message_text"):
                # inline query/ callback_query or update with edit method
                msg_id = query_or_update.message.message_id
                await query_or_update.edit_message_text(text=text, parse_mode="MarkdownV2", reply_markup=keyboard)
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
                    # fallback: send new message
                    raise RuntimeError("Queue message not found, will send new message")
        except BadRequest as e:
            # игнорируем "Message is not modified"
            if "not modified" in str(e).lower():
                return msg_id
            self.logger.log(ctx, f"edit failed (BadRequest): {e}", level=logging.ERROR)
            raise MessageServiceError(e)
        except Exception as ex:
            # log and fallback to sending new message (if bot context available)
            self.logger.log(ctx.chat_title, ctx.queue_name, ctx.actor, f"edit failed: {ex}", level=logging.ERROR)
            if context:
                sent = await context.bot.send_message(
                    chat_id=ctx.chat_id,
                    text=text,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                    disable_notification=True,
                )
                await self.repo.set_queue_message_id(ctx.chat_id, ctx.queue_name, sent.message_id)
                return sent.message_id
            raise MessageServiceError(ex)

        if msg_id is not None:
            await self.repo.set_queue_message_id(ctx.chat_id, ctx.queue_name, msg_id)
        return msg_id

    async def mass_update(self, bot: ExtBot, ctx: ActionContext, queues: Dict, presenter: QueuePresenter):
        """
        Обновить все существующие сообщения очередей (в фоновой задаче).
        queues: mapping name -> data (from repo.get_all_queues)
        presenter: объект QueuePresenter
        """
        for queue_index, (queue_name, queue_data) in enumerate(queues.items()):
            message_id = queue_data.get("last_queue_message_id")
            if not message_id:
                continue
            try:
                text = presenter.format_queue_text(queue_name, queue_data.get("queue", []))
                keyboard = presenter.build_keyboard(queue_index)
                await bot.edit_message_text(
                    chat_id=ctx.chat_id,
                    message_id=message_id,
                    text=text,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )
            except BadRequest as e:
                if "not modified" in str(e).lower():
                    continue
                else:
                    raise MessageServiceError(e)
            except Exception as ex:
                # Log per-queue failures and continue
                self.logger.log(
                    ctx.chat_title,
                    queue_name,
                    ctx.actor,
                    f"mass-update failed: {type(ex).__name__}: {ex}",
                    level=logging.ERROR,
                )
