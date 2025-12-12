from app.queues import queue_service
from app.services.auto_cleanup_service import QueueAutoCleanupService

# Инициализируем авто-очистку поверх фасада
auto_cleanup_service = QueueAutoCleanupService(queue_service)


# Простые функции для вызова из хендлеров
async def schedule_queue_expiration(context, ctx, expires_in=86_400):
    await auto_cleanup_service.schedule_expiration(context, ctx, expires_in)


async def cancel_queue_expiration(context, ctx):
    await auto_cleanup_service.cancel_expiration(context, ctx)
