import asyncio
from datetime import timedelta

from loguru import logger
from telegram.error import Forbidden, RetryAfter

from app.queues.models import ActionContext
from app.queues.subscription_repository import SubscriptionRepository


class QueueSubscriptionService:
    def __init__(self, bot, repo: SubscriptionRepository):
        self.bot = bot
        self.repo = repo

    async def subscribe(self, ctx: ActionContext, user_id: int) -> bool:
        return await self.repo.subscribe(ctx.chat_id, user_id)

    async def unsubscribe(self, chat_id: int, user_id: int) -> bool:
        return await self.repo.unsubscribe(chat_id, user_id)

    async def _send_notification(self, user_id: int, text: str) -> None:
        try:
            await self.bot.send_message(chat_id=user_id, text=text)
        except RetryAfter as ex:
            delay = ex.retry_after
            if isinstance(delay, timedelta):
                delay = delay.total_seconds()
            await asyncio.sleep(delay)
            await self.bot.send_message(chat_id=user_id, text=text)

    async def notify_queue_created(self, ctx: ActionContext, message_link: str | None = None) -> None:
        """Ошибки рассылки не должны мешать работе с очередями."""
        try:
            subscribers = await self.repo.get_subscribers(ctx.chat_id)
        except Exception:
            logger.exception("Не удалось получить подписчиков чата {}", ctx.chat_id)
            return

        # Ограничиваем длину с учётом лимита сообщений Telegram.
        text = f'В чате «{ctx.chat_title[:255]}» создана новая очередь:\n{ctx.queue_name[:3500]}'
        if message_link:
            text += f"\n\n{message_link}"
        for user_id in subscribers:
            try:
                await self._send_notification(user_id, text)
            except Forbidden:
                try:
                    await self.repo.unsubscribe(ctx.chat_id, user_id)
                except Exception:
                    logger.exception("Не удалось удалить недоступную подписку {} в чате {}", user_id, ctx.chat_id)
            except Exception:
                logger.exception("Не удалось уведомить пользователя {} о новой очереди в чате {}", user_id, ctx.chat_id)
