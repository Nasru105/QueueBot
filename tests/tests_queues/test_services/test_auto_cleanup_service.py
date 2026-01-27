from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# --- ВАЖНО: Ограничиваем тесты только asyncio, чтобы избежать ошибок Trio ---
@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
class TestQueueAutoCleanupService:
    """Тесты для QueueAutoCleanupService"""

    async def test_schedule_expiration(self, auto_cleanup_service, mock_repo, mock_scheduler, action_context):
        """Тест: планирование удаления очереди."""
        expires_sec = 3600

        # Используем UTC время для корректного сравнения
        now = datetime.now(timezone.utc)

        with patch("app.queues.services.auto_cleanup_service.get_now", return_value=now):
            expected_expiration_dt = now + timedelta(seconds=expires_sec)

            await auto_cleanup_service.schedule_expiration(action_context, expires_sec)

            # Проверка вызова репозитория
            mock_repo.set_queue_expiration.assert_awaited_once_with(
                action_context.chat_id, action_context.queue_id, expected_expiration_dt
            )

            # Проверка вызова планировщика
            mock_scheduler.add_job.assert_called_once()
            call_kwargs = mock_scheduler.add_job.call_args.kwargs

            assert call_kwargs["id"] == f"delete_{action_context.chat_id}_{action_context.queue_id}"
            assert call_kwargs["replace_existing"] is True
            assert call_kwargs["trigger"].run_date == expected_expiration_dt

    async def test_cancel_expiration_job_exists(self, auto_cleanup_service, mock_scheduler, action_context):
        """Тест: отмена существующей задачи."""
        job_id = f"delete_{action_context.chat_id}_{action_context.queue_id}"
        mock_scheduler.get_job.return_value = MagicMock()  # Job существует

        await auto_cleanup_service.cancel_expiration(action_context)

        mock_scheduler.get_job.assert_called_once_with(job_id)
        mock_scheduler.remove_job.assert_called_once_with(job_id)

    async def test_cancel_expiration_job_not_exists(self, auto_cleanup_service, mock_scheduler, action_context):
        """Тест: отмена несуществующей задачи (ошибки быть не должно)."""
        job_id = f"delete_{action_context.chat_id}_{action_context.queue_id}"
        mock_scheduler.get_job.return_value = None  # Job не найден

        await auto_cleanup_service.cancel_expiration(action_context)

        mock_scheduler.get_job.assert_called_once_with(job_id)
        mock_scheduler.remove_job.assert_not_called()

    async def test_reschedule_expiration(self, auto_cleanup_service, mock_logger, action_context):
        """Тест: перепланирование."""
        # Мокаем методы внутри класса
        auto_cleanup_service.cancel_expiration = AsyncMock()
        auto_cleanup_service.schedule_expiration = AsyncMock()
        new_expires_sec = 7200

        await auto_cleanup_service.reschedule_expiration(action_context, new_expires_sec)

        auto_cleanup_service.cancel_expiration.assert_awaited_once_with(action_context)
        auto_cleanup_service.schedule_expiration.assert_awaited_once_with(action_context, new_expires_sec)
        mock_logger.log.assert_awaited_once()

    async def test_get_remaining_time_from_job(self, auto_cleanup_service, mock_scheduler, action_context):
        """Тест: получение времени из APScheduler."""
        now = datetime.now(timezone.utc)
        future_run_time = now + timedelta(minutes=30)

        mock_job = MagicMock()
        mock_job.next_run_time = future_run_time
        mock_scheduler.get_job.return_value = mock_job

        # Патчим datetime.now внутри модуля, чтобы время "замерло"
        with patch("app.queues.services.auto_cleanup_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            # ВАЖНО: timedelta тоже нужно оставить доступным, если он импортирован отдельно,
            # но mock_datetime перекроет класс datetime.

            remaining = await auto_cleanup_service.get_remaining_time(action_context)

            # Проверяем секунды с погрешностью
            assert remaining.total_seconds() == pytest.approx(1800, abs=1)

    async def test_get_remaining_time_from_db(self, auto_cleanup_service, mock_scheduler, mock_repo, action_context):
        """Тест: получение времени из БД, если job нет."""
        mock_scheduler.get_job.return_value = None

        now = datetime.now(timezone.utc)
        db_expiration_time = now + timedelta(minutes=15)
        mock_repo.get_queue_expiration.return_value = db_expiration_time

        with patch("app.queues.services.auto_cleanup_service.get_now", return_value=now):
            remaining = await auto_cleanup_service.get_remaining_time(action_context)
            assert remaining.total_seconds() == pytest.approx(900, abs=1)

    async def test_get_remaining_time_is_zero(self, auto_cleanup_service, mock_scheduler, mock_repo, action_context):
        """Тест: времени нет нигде -> 0."""
        mock_scheduler.get_job.return_value = None
        mock_repo.get_queue_expiration.return_value = None

        remaining = await auto_cleanup_service.get_remaining_time(action_context)
        assert remaining.total_seconds() == 0

    @patch("app.queues.services.auto_cleanup_service.safe_delete", new_callable=AsyncMock)
    async def test_restore_all_expirations(self, mock_safe_delete, auto_cleanup_service, mock_repo, mock_scheduler):
        """Тест: восстановление задач при рестарте."""
        now = datetime.now(timezone.utc)

        chats_from_db = [
            {
                "chat_id": 1,
                "chat_title": "Chat 1",
                "queues": {
                    "q_expired": {"id": "q_expired", "name": "Expired"},
                    "q_active": {"id": "q_active", "name": "Active"},
                    "q_no_exp": {"id": "q_no_exp", "name": "NoExp"},
                },
            }
        ]
        mock_repo.get_all_chats_with_queues.return_value = chats_from_db
        mock_repo.get_queue_message_id.return_value = 100

        # Настраиваем side_effect для возврата разных дат
        async def get_expiration(chat_id, queue_id):
            # ВАЖНО: используем timezone.utc для всех дат
            if queue_id == "q_expired":
                return now - timedelta(hours=5)  # Давно истекла (даже с учетом +3ч в коде)
            if queue_id == "q_active":
                return now + timedelta(hours=5)  # Будущее время
            return None  # q_no_exp

        mock_repo.get_queue_expiration.side_effect = get_expiration

        with patch("app.queues.services.auto_cleanup_service.get_now", return_value=now):
            await auto_cleanup_service.restore_all_expirations()

        # 1. Проверяем удаление просроченной очереди
        # safe_delete должен быть вызван для q_expired
        assert mock_safe_delete.call_count >= 1
        mock_repo.delete_queue.assert_awaited_with(1, "q_expired")

        # 2. Проверяем планирование активной очереди
        # add_job должен быть вызван для q_active
        mock_scheduler.add_job.assert_called()
        # Проверяем аргументы последнего вызова или ищем конкретный
        called_ids = [k["id"] for _, k in mock_scheduler.add_job.call_args_list]
        assert "delete_1_q_active" in called_ids

    @patch("app.queues.services.auto_cleanup_service.safe_delete", new_callable=AsyncMock)
    async def test_expiration_job_deletes_queue(
        self, mock_safe_delete, auto_cleanup_service, mock_repo, mock_logger, action_context
    ):
        """Тест: job удаляет очередь."""
        # --- ИСПРАВЛЕНИЕ: Используем timezone.utc ---
        mock_repo.get_last_modified_time.return_value = datetime.now(timezone.utc) - timedelta(hours=2)
        mock_repo.get_queue_message_id.return_value = 999

        # Патчим get_now, чтобы оно возвращало время в той же таймзоне
        with patch("app.queues.services.auto_cleanup_service.get_now", return_value=datetime.now(timezone.utc)):
            await auto_cleanup_service._expiration_job(action_context)

        mock_safe_delete.assert_awaited_with(auto_cleanup_service.bot, action_context, 999)
        mock_repo.delete_queue.assert_awaited_with(action_context.chat_id, action_context.queue_id)

    async def test_expiration_job_reschedules_queue(self, auto_cleanup_service, mock_repo, action_context):
        """Тест: job переносит удаление (активность < 1 часа)."""
        # --- ИСПРАВЛЕНИЕ: Используем timezone.utc ---
        mock_repo.get_last_modified_time.return_value = datetime.now(timezone.utc) - timedelta(minutes=30)

        auto_cleanup_service.reschedule_expiration = AsyncMock()

        with patch("app.queues.services.auto_cleanup_service.get_now", return_value=datetime.now(timezone.utc)):
            await auto_cleanup_service._expiration_job(action_context)

        auto_cleanup_service.reschedule_expiration.assert_awaited_with(action_context, 3600)
        mock_repo.delete_queue.assert_not_called()
