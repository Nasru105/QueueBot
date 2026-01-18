import logging
from typing import Optional

from telegram import User
from telegram.ext import ContextTypes

from app.queues.queue_repository import QueueRepository
from app.queues.services.auto_cleanup_service import QueueAutoCleanupService
from app.services.logger import QueueLogger

from .domain import QueueDomainService
from .errors import InvalidPositionError, QueueError, UserNotFoundError
from .message_service import QueueMessageService
from .models import ActionContext
from .presenter import QueuePresenter
from .user_service import UserService


class QueueFacadeService:
    """
    Верхнеуровневый сервис, который используют хендлеры.
    Компоненты (repo, presenter, message_service ...) инжектируются через конструктор.
    """

    def __init__(self, repo, logger=QueueLogger):
        self.repo: QueueRepository = repo
        self.domain = QueueDomainService()
        self.presenter = QueuePresenter()
        self.message_service = QueueMessageService(repo, logger)
        self.user_service = UserService(repo)
        self.auto_cleanup_service = QueueAutoCleanupService(repo, logger)
        self.logger = logger

    # ------ queue management (thin orchestrations) ------
    async def create_queue(self, context, ctx: ActionContext, expires_in):
        try:
            queue_id = await self.repo.create_queue(ctx.chat_id, ctx.chat_title, ctx.queue_name)
            ctx.queue_id = queue_id
            await self.auto_cleanup_service.schedule_expiration(context, ctx, expires_in)
            await self.logger.log(ctx, "create queue")
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
        return queue_id

    async def delete_queue(self, context, ctx: ActionContext):
        try:
            await self.repo.delete_queue(ctx.chat_id, ctx.queue_id)
            await self.auto_cleanup_service.cancel_expiration(context, ctx)
            await self.logger.log(ctx, "delete queue")

        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)

    async def join_to_queue(self, ctx: ActionContext, user: User) -> int:
        try:
            display_name = await self.user_service.get_user_display_name(user, ctx.chat_id)
            position = await self.repo.add_to_queue(ctx.chat_id, ctx.queue_id, user.id, display_name)
            if position:
                await self.logger.joined(ctx, display_name, position)
            return position
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)

    async def leave_from_queue(self, ctx: ActionContext, user: User) -> int:
        try:
            position = await self.repo.remove_from_queue(ctx.chat_id, ctx.queue_id, user.id)
            if position:
                display_name = await self.user_service.get_user_display_name(user, ctx.chat_id)
                await self.logger.leaved(ctx, display_name, position)
            return position
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)

    # ------ business operations (using domain) ------
    async def insert_into_queue(
        self, ctx: ActionContext, user_name: str = None, desired_pos: int = None
    ) -> tuple[Optional[str], Optional[int], Optional[int]]:
        try:
            queue = await self.repo.get_queue_by_name(ctx.chat_id, ctx.queue_name)
            ctx.queue_id = queue["id"]
            members = queue.get("members", [])
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return None

        try:
            user_name, desired_pos, old_position = self.domain.insert_at_position(members, user_name, desired_pos)
        except InvalidPositionError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return None, None, None
        except Exception as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.ERROR)
            return None, None, None

        if user_name:
            try:
                await self.repo.update_queue_members(ctx.chat_id, ctx.queue_id, members)
                if old_position:
                    # old_position already 1-based
                    await self.logger.removed(ctx, user_name, old_position)
                await self.logger.inserted(ctx, user_name, desired_pos)
            except QueueError as ex:
                await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
        return user_name, desired_pos, old_position

    async def remove_from_queue(
        self, ctx: ActionContext, pos: int = None, user_name: str = None
    ) -> tuple[Optional[str], Optional[int]]:
        try:
            queue = await self.repo.get_queue_by_name(ctx.chat_id, ctx.queue_name)
            ctx.queue_id = queue["id"]
            members = queue.get("members", [])
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return None, None

        try:
            if pos is not None:
                removed_name, position = self.domain.remove_by_position(members, pos)
            elif user_name is not None:
                removed_name, position = self.domain.remove_by_name(members, user_name)

        except InvalidPositionError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return None, None
        except Exception as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.ERROR)
            return None, None

        if removed_name:
            try:
                await self.repo.update_queue_members(ctx.chat_id, ctx.queue_id, members)
                await self.logger.removed(ctx, removed_name, position)
            except QueueError as ex:
                await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
        return removed_name, position

    async def replace_users_queue(
        self, ctx: ActionContext, pos1=None, pos2=None, name1=None, name2=None
    ) -> tuple[Optional[int], Optional[int], Optional[str], Optional[str]]:
        try:
            queue = await self.repo.get_queue_by_name(ctx.chat_id, ctx.queue_name)
            members = queue.get("members", [])
            ctx.queue_id = queue["id"]
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return None, None, None, None

        try:
            if pos1 is not None and pos2 is not None:
                pos1, pos2, name1, name2 = self.domain.replace_by_positions(members, pos1, pos2)
            elif name1 is not None and name2 is not None:
                pos1, pos2, name1, name2 = self.domain.replace_by_names(members, name1, name2)
        except (InvalidPositionError, UserNotFoundError) as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return None, None, None, None
        except Exception as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.ERROR)
            return None, None, None, None

        try:
            await self.repo.update_queue_members(ctx.chat_id, ctx.queue_id, members)
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return pos1, pos2, name1, name2

        await self.logger.replaced(ctx, name1, pos1, name2, pos2)
        return pos1, pos2, name1, name2

    async def send_queue_message(self, ctx: ActionContext, context):
        try:
            queue = await self.repo.get_queue(ctx.chat_id, ctx.queue_id)
            text = self.presenter.format_queue_text(queue)
            keyboard = self.presenter.build_queue_keyboard(ctx.queue_id)
            return await self.message_service.send_queue_message(ctx, text, keyboard, context)
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)

    async def update_queue_message(self, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
        try:
            if ctx.queue_id:
                queue = await self.repo.get_queue(ctx.chat_id, ctx.queue_id)
            else:
                queue = await self.repo.get_queue_by_name(ctx.chat_id, ctx.queue_name)
            ctx.queue_id = queue["id"]
            ctx.queue_name = queue["name"]
            text = self.presenter.format_queue_text(queue)
            keyboard = self.presenter.build_queue_keyboard(ctx.queue_id)
            return await self.message_service.edit_queue_message(context, ctx, text, keyboard)
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)

    async def rename_queue(self, ctx: ActionContext, new_name: str):
        try:
            await self.repo.rename_queue(ctx.chat_id, ctx.queue_name, new_name)
            await self.logger.log(ctx, f"rename queue {ctx.queue_name} → {new_name}")
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)

    async def generate_queue_name(self, chat_id: int) -> str:
        queues = await self.repo.get_all_queues(chat_id)
        return self.domain.generate_queue_name(queues)

    async def get_count_queues(self, chat_id: int) -> int:
        queues = await self.repo.get_all_queues(chat_id)
        return len(queues)

    async def get_user_display_name(self, user, chat_id: int):
        try:
            return await self.user_service.get_user_display_name(user, chat_id)
        except QueueError as ex:
            # Fallback to raw user if any error
            await self.logger.log(None, f"ERROR getting display name: {ex}", logging.WARNING)
            return None

    async def set_user_display_name(self, ctx, user, display_name: str, global_mode=False):
        try:
            await self.user_service.set_user_display_name(ctx, user, display_name, global_mode)
            await self.logger.log(ctx, f"set display name → {display_name}")
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)

    async def clear_user_display_name(self, ctx, user, global_mode=False):
        try:
            user_display_name = await self.user_service.clear_user_display_name(ctx, user, global_mode)
            await self.logger.log(ctx, "clear display name")
            return user_display_name
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)

    async def set_queue_description(self, ctx: ActionContext, description):
        try:
            await self.repo.set_queue_description(ctx.chat_id, ctx.queue_id, description)
            await self.logger.log(ctx, "set description")
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
