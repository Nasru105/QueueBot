# app/queues/service/queue_auto_cleanup_service.py
from datetime import datetime, timedelta

from telegram.ext import ContextTypes

from app.queues.models import ActionContext
from app.queues.service import QueueFacadeService
from app.utils.utils import get_now, safe_delete


class QueueAutoCleanupService:
    """
    Сервис, отвечающий за авто-удаление очередей.
    Используется только scheduler'ом.
    """

    def __init__(self, queue_facade: QueueFacadeService):
        self.queue_service = queue_facade

    async def schedule_expiration(
        self, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext, expires_in_seconds=86_400
    ):
        """Сохраняет время удаления в БД и планирует job"""
        # сохраняем в БД время удаления (datetime)
        now = await get_now()
        expiration_dt = now + timedelta(seconds=expires_in_seconds)
        await self.queue_service.repo.set_queue_expiration(ctx.chat_id, ctx.queue_id, expiration_dt)

        # планируем job
        context.job_queue.run_once(
            self._expiration_job,
            when=expires_in_seconds,
            data={"ctx": ctx},
            name=self._job_name(ctx),
        )

    async def cancel_expiration(self, context, ctx: ActionContext):
        jobs = context.job_queue.get_jobs_by_name(self._job_name(ctx))
        for job in jobs:
            job.schedule_removal()
        # очищаем значение в БД
        await self.queue_service.repo.clear_queue_expiration(ctx.chat_id, ctx.queue_id)

    async def reschedule_expiration(self, context, ctx: ActionContext, new_expires_in_seconds=86_400):
        """
        Изменяет время автоудаления очереди.
        Удаляет существующий job и создает новый с новым временем.
        """
        # Отменяем существующий job
        await self.cancel_expiration(context, ctx)

        # Создаем новый job с новым временем
        await self.schedule_expiration(context, ctx, new_expires_in_seconds)

    async def get_remaining_time(self, context, ctx: ActionContext) -> timedelta:
        """
        Возвращает оставшееся время до удаления очереди.
        Если job не запланирован — смотрит в БД по полю `expiration`.
        """
        jobs = context.job_queue.get_jobs_by_name(self._job_name(ctx))
        if jobs:
            job = jobs[0]
            return job.trigger.trigger_date - datetime.now()

        # если job не найден — проверяем сохранённое время в БД
        expiration = await self.queue_service.repo.get_queue_expiration(ctx.chat_id, ctx.queue_id)
        if not expiration:
            return timedelta(seconds=0)

        remaining = expiration - await get_now()
        if remaining.total_seconds() < 0:
            return timedelta(seconds=0)
        return remaining

    @staticmethod
    def _job_name(ctx: ActionContext):
        return f"delete_{ctx.chat_id}_{ctx.queue_id}"

    async def restore_all_expirations(self, app) -> None:
        """При старте бота — пересоздаёт запланированные задачи из БД"""
        chats = await self.queue_service.repo.get_all_chats_with_queues()
        for doc in chats:
            chat_id = doc.get("chat_id")
            chat_title = (
                doc.get(
                    "chat_title",
                )
                or ""
            )
            queues = doc.get("queues", {}) or {}

            for qid, q in queues.items():
                # Получим expiration через репозиторий (он вернёт datetime или None)
                exp_dt = await self.queue_service.repo.get_queue_expiration(chat_id, qid)
                if not exp_dt:
                    continue

                now = await get_now()
                delta = (exp_dt - now).total_seconds()

                # сформируем ctx
                ctx = ActionContext(
                    chat_id=chat_id, chat_title=chat_title, queue_id=q.get("id"), queue_name=q.get("name")
                )

                if delta <= 0:
                    # срок уже истёк — планируем немедленную задачу
                    app.job_queue.run_once(self._expiration_job, when=0, data={"ctx": ctx}, name=self._job_name(ctx))
                else:
                    app.job_queue.run_once(
                        self._expiration_job, when=delta, data={"ctx": ctx}, name=self._job_name(ctx)
                    )

    async def _expiration_job(self, context):
        job = context.job
        ctx: ActionContext = job.data["ctx"]
        ctx.actor = "queue_expire_job"

        last_modified = await self.queue_service.repo.get_last_modified_time(ctx.chat_id, ctx.queue_id)
        now = await get_now()

        # если очередь обновлялась в последний час — откладываем удаление ещё на час
        if last_modified and now - last_modified < timedelta(hours=1):
            await self.reschedule_expiration(context, ctx, expires_in_seconds=3600)
            return

        # Удаляем сообщение очереди
        last_msg_id = await self.queue_service.repo.get_queue_message_id(ctx.chat_id, ctx.queue_id)
        if last_msg_id:
            await safe_delete(context.bot, ctx, last_msg_id)

        # удаляем саму очередь
        await self.queue_service.delete_queue(ctx)
        # очищаем поле expiration (на случай, если что-то осталось)
        try:
            await self.queue_service.repo.clear_queue_expiration(ctx.chat_id, ctx.queue_id)
        except Exception:
            pass
