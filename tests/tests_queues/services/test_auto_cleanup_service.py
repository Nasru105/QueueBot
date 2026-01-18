from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ContextTypes

from app.queues.models import ActionContext
from app.queues.services.auto_cleanup_service import QueueAutoCleanupService

# Путь для патчинга утилит внутри тестируемого файла
MODULE_PATH = "app.queues.services.auto_cleanup_service"


@pytest.fixture
def mock_dependencies():
    """Создает моки для репозитория, логгера и контекста."""
    repo = MagicMock()
    repo.set_queue_expiration = AsyncMock()
    repo.clear_queue_expiration = AsyncMock()
    repo.get_queue_expiration = AsyncMock()
    repo.get_all_chats_with_queues = AsyncMock()
    repo.get_last_modified_time = AsyncMock()
    repo.get_queue_message_id = AsyncMock()
    repo.delete_queue = AsyncMock()

    logger = MagicMock()
    logger.log = AsyncMock()

    # Мок Context и JobQueue
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.job_queue = MagicMock()
    context.job_queue.run_once = MagicMock()
    context.job_queue.get_jobs_by_name = MagicMock(return_value=[])
    context.bot = AsyncMock()

    return {"repo": repo, "logger": logger, "context": context}


@pytest.fixture
def service(mock_dependencies):
    return QueueAutoCleanupService(mock_dependencies["repo"], mock_dependencies["logger"])


@pytest.fixture
def sample_ctx():
    return ActionContext(chat_id=123, chat_title="Test Chat", queue_id="q1", queue_name="Test Queue", actor="tester")


@pytest.fixture
def fixed_now():
    """Фиксированное время для тестов."""
    return datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
class TestQueueAutoCleanupService:
    async def test_schedule_expiration(self, service, mock_dependencies, sample_ctx, fixed_now):
        """Тест планирования удаления."""
        expires_in = 3600

        with patch(f"{MODULE_PATH}.get_now", new_callable=AsyncMock) as mock_get_now:
            mock_get_now.return_value = fixed_now

            await service.schedule_expiration(mock_dependencies["context"], sample_ctx, expires_in)

            # 1. Проверяем сохранение в БД
            expected_dt = fixed_now + timedelta(seconds=expires_in)
            mock_dependencies["repo"].set_queue_expiration.assert_awaited_once_with(
                sample_ctx.chat_id, sample_ctx.queue_id, expected_dt
            )

            # 2. Проверяем постановку задачи в job_queue
            mock_dependencies["context"].job_queue.run_once.assert_called_once()
            call_args = mock_dependencies["context"].job_queue.run_once.call_args

            # Проверяем аргументы run_once(callback, when, data, name)
            assert call_args[0][0] == service._expiration_job  # callback
            assert call_args[1]["when"] == expires_in
            assert call_args[1]["data"]["ctx"] == sample_ctx
            assert call_args[1]["name"] == f"delete_{sample_ctx.chat_id}_{sample_ctx.queue_id}"

    async def test_cancel_expiration(self, service, mock_dependencies, sample_ctx):
        """Тест отмены запланированного удаления."""
        # Создаем мок задачи (Job)
        mock_job = MagicMock()
        mock_dependencies["context"].job_queue.get_jobs_by_name.return_value = [mock_job]

        await service.cancel_expiration(mock_dependencies["context"], sample_ctx)

        # 1. Проверяем удаление job
        mock_dependencies["context"].job_queue.get_jobs_by_name.assert_called_once_with(
            f"delete_{sample_ctx.chat_id}_{sample_ctx.queue_id}"
        )
        mock_job.schedule_removal.assert_called_once()

        # 2. Проверяем очистку БД
        mock_dependencies["repo"].clear_queue_expiration.assert_awaited_once_with(
            sample_ctx.chat_id, sample_ctx.queue_id
        )

    async def test_reschedule_expiration(self, service, mock_dependencies, sample_ctx):
        """Тест перепланирования (отмена + новая задача)."""
        new_time = 7200

        # Патчим методы самого сервиса, чтобы проверить цепочку вызовов,
        # не выполняя реальную логику (unit-тест потока)
        with (
            patch.object(service, "cancel_expiration", new_callable=AsyncMock) as mock_cancel,
            patch.object(service, "schedule_expiration", new_callable=AsyncMock) as mock_schedule,
        ):
            await service.reschedule_expiration(mock_dependencies["context"], sample_ctx, new_time)

            mock_cancel.assert_awaited_once_with(mock_dependencies["context"], sample_ctx)
            mock_schedule.assert_awaited_once_with(mock_dependencies["context"], sample_ctx, new_time)

            # Проверяем лог
            mock_dependencies["logger"].log.assert_awaited_once()
            assert "reschedule" in mock_dependencies["logger"].log.call_args[0][1]

    async def test_get_remaining_time_from_job(self, service, mock_dependencies, sample_ctx):
        """Тест получения времени из активного job."""
        mock_job = MagicMock()
        # Имитируем, что job сработает через 10 минут
        future_trigger = datetime.now() + timedelta(minutes=10)
        mock_job.trigger.trigger_date = future_trigger

        mock_dependencies["context"].job_queue.get_jobs_by_name.return_value = [mock_job]

        # Патчим datetime.now внутри функции (хотя в коде используется datetime.now(),
        # для простоты теста проверяем дельту приблизительно или патчим класс datetime, если нужно точность)
        # В данном случае просто проверим, что возвращается timedelta

        result = await service.get_remaining_time(mock_dependencies["context"], sample_ctx)

        assert isinstance(result, timedelta)
        # Должно быть около 10 минут (с допуском на время выполнения теста)
        assert 590 <= result.total_seconds() <= 610

    async def test_get_remaining_time_from_db(self, service, mock_dependencies, sample_ctx, fixed_now):
        """Тест получения времени из БД, если job не найден."""
        mock_dependencies["context"].job_queue.get_jobs_by_name.return_value = []

        # Время истечения через 5 минут
        db_expiration = fixed_now + timedelta(minutes=5)
        mock_dependencies["repo"].get_queue_expiration.return_value = db_expiration

        with patch(f"{MODULE_PATH}.get_now", new_callable=AsyncMock) as mock_get_now:
            mock_get_now.return_value = fixed_now

            result = await service.get_remaining_time(mock_dependencies["context"], sample_ctx)

            assert result == timedelta(minutes=5)

    async def test_get_remaining_time_none(self, service, mock_dependencies, sample_ctx):
        """Тест, если времени нет нигде."""
        mock_dependencies["context"].job_queue.get_jobs_by_name.return_value = []
        mock_dependencies["repo"].get_queue_expiration.return_value = None

        result = await service.get_remaining_time(mock_dependencies["context"], sample_ctx)

        assert result == timedelta(seconds=0)

    async def test_restore_all_expirations(self, service, mock_dependencies, fixed_now):
        """Тест восстановления задач при старте."""
        # Подготовка данных из БД
        mock_dependencies["repo"].get_all_chats_with_queues.return_value = [
            {
                "chat_id": 100,
                "chat_title": "Chat 1",
                "queues": {
                    "q1": {"id": "q1", "name": "Queue 1"},  # Активная
                    "q2": {"id": "q2", "name": "Queue 2"},  # Без даты (пропуск)
                },
            }
        ]

        # Настройка возврата get_queue_expiration
        async def get_exp_side_effect(chat_id, queue_id):
            if queue_id == "q1":
                # Истекает через 1000 секунд
                return fixed_now + timedelta(seconds=1000)
            return None

        mock_dependencies["repo"].get_queue_expiration.side_effect = get_exp_side_effect

        # Мокаем app (он передается вместо context в этом методе)
        mock_app = MagicMock()
        mock_app.job_queue.run_once = MagicMock()

        with patch(f"{MODULE_PATH}.get_now", new_callable=AsyncMock) as mock_get_now:
            mock_get_now.return_value = fixed_now

            await service.restore_all_expirations(mock_app)

            # Должен быть вызван run_once только для q1
            mock_app.job_queue.run_once.assert_called_once()
            call_kwargs = mock_app.job_queue.run_once.call_args[1]

            assert call_kwargs["when"] == 1000.0
            assert call_kwargs["name"] == "delete_100_q1"
            assert call_kwargs["data"]["ctx"].queue_id == "q1"

    async def test_expiration_job_executes_delete(self, service, mock_dependencies, sample_ctx, fixed_now):
        """Тест выполнения job: удаление очереди, так как она давно не обновлялась."""
        # Настройка job data
        mock_job = MagicMock()
        mock_job.data = {"ctx": sample_ctx}
        mock_dependencies["context"].job = mock_job

        # Очередь обновлялась 2 часа назад (условие < 1 час не сработает)
        last_modified = fixed_now - timedelta(hours=2)
        mock_dependencies["repo"].get_last_modified_time.return_value = last_modified

        # Есть сообщение
        mock_dependencies["repo"].get_queue_message_id.return_value = 555

        with (
            patch(f"{MODULE_PATH}.get_now", new_callable=AsyncMock) as mock_get_now,
            patch(f"{MODULE_PATH}.safe_delete", new_callable=AsyncMock) as mock_safe_delete,
        ):
            mock_get_now.return_value = fixed_now

            await service._expiration_job(mock_dependencies["context"])

            # Проверки
            # 1. Удаление сообщения
            mock_safe_delete.assert_awaited_once_with(mock_dependencies["context"].bot, sample_ctx, 555)

            # 2. Удаление очереди из БД
            mock_dependencies["repo"].delete_queue.assert_awaited_once_with(sample_ctx.chat_id, sample_ctx.queue_id)

            # 3. Лог
            assert "delete queue" in mock_dependencies["logger"].log.call_args[0][1]

            # 4. Очистка expiration
            mock_dependencies["repo"].clear_queue_expiration.assert_awaited_once()

    async def test_expiration_job_postpones(self, service, mock_dependencies, sample_ctx, fixed_now):
        """Тест выполнения job: откладывание удаления, так как очередь активна."""
        mock_job = MagicMock()
        mock_job.data = {"ctx": sample_ctx}
        mock_dependencies["context"].job = mock_job

        # Очередь обновлялась 10 минут назад (условие < 1 час сработает)
        last_modified = fixed_now - timedelta(minutes=10)
        mock_dependencies["repo"].get_last_modified_time.return_value = last_modified

        with (
            patch(f"{MODULE_PATH}.get_now", new_callable=AsyncMock) as mock_get_now,
            patch.object(service, "reschedule_expiration", new_callable=AsyncMock) as mock_reschedule,
        ):
            mock_get_now.return_value = fixed_now

            await service._expiration_job(mock_dependencies["context"])

            # Должен перепланировать на час (3600 сек)
            mock_reschedule.assert_awaited_once_with(mock_dependencies["context"], sample_ctx, 3600)

            # Удаление НЕ должно вызываться
            mock_dependencies["repo"].delete_queue.assert_not_awaited()
