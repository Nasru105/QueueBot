from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from telegram import Bot

from app.queues.models import ActionContext
from app.queues.queue_repository import QueueRepository
from app.services.logger import QueueLogger
from app.utils.utils import get_now, safe_delete


class QueueAutoCleanupService:
    """Сервис, отвечающий за авто-удаление очередей."""

    def __init__(self, bot: Bot, repo: QueueRepository, scheduler: AsyncIOScheduler, logger: QueueLogger):
        self.bot: Bot = bot
        self.repo: QueueRepository = repo
        self.scheduler: AsyncIOScheduler = scheduler
        self.logger: QueueLogger = logger

    async def schedule_expiration(self, ctx: ActionContext, expires_in_seconds=86_400):
        """Сохраняет время удаления в БД и планирует job"""
        # сохраняем в БД время удаления (datetime)
        now = get_now()
        expiration_dt = now + timedelta(seconds=expires_in_seconds)
        await self.repo.set_queue_expiration(ctx.chat_id, ctx.queue_id, expiration_dt)
        # планируем job в APScheduler
        self.scheduler.add_job(
            self._expiration_job,
            trigger=DateTrigger(run_date=expiration_dt),
            id=self._job_name(ctx),
            args=(ctx,),
            replace_existing=True,
        )

    async def cancel_expiration(self, ctx: ActionContext):
        """Отменяет запланированное удаление очереди"""
        job_id = self._job_name(ctx)
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
        # очищаем значение в БД

    async def reschedule_expiration(self, ctx: ActionContext, new_expires_in_seconds=86_400):
        """
        Изменяет время автоудаления очереди.
        Удаляет существующий job и создает новый с новым временем.
        """
        # Отменяем существующий job
        await self.cancel_expiration(ctx)

        # Создаем новый job с новым временем
        await self.schedule_expiration(ctx, new_expires_in_seconds)

        await self.logger.log(ctx, f"reschedule {ctx.queue_name} expiration to {new_expires_in_seconds // 3600} hours")

    async def get_remaining_time(self, ctx: ActionContext) -> timedelta:
        """
        Возвращает оставшееся время до удаления очереди.
        Если job не запланирован — смотрит в БД по полю `expiration`.
        """
        job = self.scheduler.get_job(self._job_name(ctx))
        if job:
            next_run = job.next_run_time
            if next_run:
                remaining = next_run - datetime.now()
                if remaining.total_seconds() < 0:
                    return timedelta(seconds=0)
                return remaining

        # если job не найден — проверяем сохранённое время в БД
        expiration = await self.repo.get_queue_expiration(ctx.chat_id, ctx.queue_id)
        if not expiration:
            return timedelta(seconds=0)

        remaining = expiration - get_now()
        if remaining.total_seconds() < 0:
            return timedelta(seconds=0)
        return remaining

    @staticmethod
    def _job_name(ctx: ActionContext):
        return f"delete_{ctx.chat_id}_{ctx.queue_id}"

    async def restore_all_expirations(self) -> None:
        """При старте бота — пересоздаёт запланированные задачи из БД"""
        chats = await self.repo.get_all_chats_with_queues()

        for doc in chats:
            chat_id = doc.get("chat_id")
            chat_title = doc.get("chat_title") or ""
            queues = doc.get("queues", {}) or {}
            for qid, q in queues.items():
                exp_dt = await self.repo.get_queue_expiration(chat_id, qid)
                if not exp_dt:
                    continue
                exp_dt = exp_dt + timedelta(hours=3)
                exp_dt = exp_dt.replace(tzinfo=timezone(timedelta(hours=3)))
                if not exp_dt:
                    continue
                now = get_now()

                # если время истекло, удаляем очередь сразу
                if exp_dt <= now:
                    ctx = ActionContext(
                        chat_id=chat_id,
                        chat_title=chat_title,
                        queue_id=q.get("id"),
                        queue_name=q.get("name"),
                        actor="queue_restore_job",
                    )

                    last_msg_id = await self.repo.get_queue_message_id(ctx.chat_id, ctx.queue_id)
                    if last_msg_id:
                        await safe_delete(self.bot, ctx, last_msg_id)

                    await self.repo.delete_queue(chat_id, qid)
                    await self.logger.log(ctx, "delete queue")
                    continue

                # сформируем ctx и планируем job
                ctx = ActionContext(
                    chat_id=chat_id, chat_title=chat_title, queue_id=q.get("id"), queue_name=q.get("name")
                )

                self.scheduler.add_job(
                    self._expiration_job,
                    trigger=DateTrigger(run_date=exp_dt),
                    id=self._job_name(ctx),
                    args=(ctx,),
                    replace_existing=True,
                )

    async def _expiration_job(self, ctx: ActionContext):
        """Job для удаления истекшей очереди"""
        ctx.actor = "queue_expire_job"

        last_modified = await self.repo.get_last_modified_time(ctx.chat_id, ctx.queue_id)
        now = get_now()

        # если очередь обновлялась в последний час — откладываем удаление ещё на час
        if last_modified and now - last_modified < timedelta(hours=1):
            await self.reschedule_expiration(ctx, 3600)
            return

        # Удаляем сообщение очереди
        last_msg_id = await self.repo.get_queue_message_id(ctx.chat_id, ctx.queue_id)
        if last_msg_id:
            await safe_delete(self.bot, ctx, last_msg_id)

        await self.repo.delete_queue(ctx.chat_id, ctx.queue_id)
        await self.logger.log(ctx, "delete queue")
