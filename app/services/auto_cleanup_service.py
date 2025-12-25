# app/queues/service/queue_auto_cleanup_service.py
from datetime import datetime, timedelta

from app.queues.models import ActionContext
from app.queues.service import QueueFacadeService
from app.utils.utils import get_now_formatted_time, safe_delete


class QueueAutoCleanupService:
    """
    Сервис, отвечающий за авто-удаление очередей.
    Используется только scheduler'ом.
    """

    def __init__(self, queue_facade: QueueFacadeService):
        self.queue_service = queue_facade

    async def schedule_expiration(self, context, ctx: ActionContext, expires_in_seconds=86_400):
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
        """
        jobs = context.job_queue.get_jobs_by_name(self._job_name(ctx))
        if not jobs:
            return timedelta(seconds=0)

        job = jobs[0]
        return job.trigger.trigger_date - datetime.now()

    @staticmethod
    def _job_name(ctx: ActionContext):
        return f"delete_{ctx.chat_id}_{ctx.queue_name}"

    async def _expiration_job(self, context):
        job = context.job
        ctx: ActionContext = job.data["ctx"]
        ctx.actor = "queue_expire_job"

        last_modified = await self.queue_service.repo.get_last_modified_time(ctx.chat_id, ctx.queue_id)
        last_modified = datetime.strptime(last_modified, "%d.%m.%Y %H:%M:%S")

        now = await get_now_formatted_time()

        if now - last_modified < timedelta(hours=1):
            # Обновляем TTL, но не трогаем очередь
            await self.cancel_expiration(context, ctx)
            await self.schedule_expiration(context, ctx, expires_in_seconds=3600)
            return

        last_msg_id = await self.queue_service.repo.get_queue_message_id(ctx.chat_id, ctx.queue_id)
        if last_msg_id:
            await safe_delete(context.bot, ctx, last_msg_id)

        list_message_id = await self.queue_service.repo.get_list_message_id(ctx.chat_id)

        await self.queue_service.delete_queue(ctx)

        # Обновляем сообщения других очередей в чате
        await self.queue_service.mass_update_existing_queues(context.bot, ctx, list_message_id)
