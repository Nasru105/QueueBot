import logging
from typing import List

from telegram import User
from telegram.ext import ContextTypes

from app.queues.queue_repository import QueueRepository
from app.queues.services.auto_cleanup_service import QueueAutoCleanupService
from app.services.logger import QueueLogger
from app.utils.utils import parse_users_names

from .domain import QueueDomainService
from .errors import InvalidPositionError, QueueError, UserNotFoundError
from .message_service import QueueMessageService
from .models import ActionContext, InsertResult, RemoveResult, ReplaceResult
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
    async def remove_from_queue(self, ctx: ActionContext, args: List[str]) -> RemoveResult:
        try:
            queue = await self.repo.get_queue_by_name(ctx.chat_id, ctx.queue_name)
            ctx.queue_id = queue["id"]
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return RemoveResult(None, None, None)

        if queue is None:
            return RemoveResult(None, None, None)

        try:
            res = self.domain.remove_by_pos_or_name(queue["members"], args)
        except InvalidPositionError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return RemoveResult(None, None, None)
        except Exception as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.ERROR)
            return RemoveResult(None, None, None)

        if res.removed_name:
            try:
                await self.repo.update_queue(ctx.chat_id, ctx.queue_id, res.updated_queue)
                await self.logger.removed(ctx, res.removed_name, res.position)
            except QueueError as ex:
                await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
        return res

    async def insert_into_queue(self, ctx: ActionContext, args: List[str]) -> InsertResult:
        try:
            queue = await self.repo.get_queue_by_name(ctx.chat_id, ctx.queue_name)
            ctx.queue_id = queue["id"]
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return InsertResult(None, None, None, None)

        try:
            desired_pos = int(args[-1]) - 1
            user_name = " ".join(args[:-1]).strip()
        except Exception:
            user_name = " ".join(args).strip()
            desired_pos = None

        try:
            res = self.domain.insert_at_position(queue["members"], user_name, desired_pos)
        except InvalidPositionError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return InsertResult(None, None, None, None)
        except Exception as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.ERROR)
            return InsertResult(None, None, None, None)

        if res.user_name:
            try:
                await self.repo.update_queue(ctx.chat_id, ctx.queue_id, res.updated_queue)
                if res.old_position:
                    # old_position already 1-based
                    await self.logger.removed(ctx, user_name, res.old_position)
                await self.logger.inserted(ctx, user_name, res.position)
            except QueueError as ex:
                await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
        return res

    async def replace_users_queue(self, ctx: ActionContext, args: List[str]) -> ReplaceResult:
        try:
            queue = await self.repo.get_queue_by_name(ctx.chat_id, ctx.queue_name)
            members = queue.get("members", [])
            ctx.queue_id = queue["id"]
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return ReplaceResult(None, None, None, None, None, None)

        if not queue:
            return ReplaceResult(None, None, None, None, None, None)

        # Попытка интерпретировать последние аргументы как позиции
        try:
            pos1 = int(args[-2]) - 1
            pos2 = int(args[-1]) - 1
            mode = "positions"
        except ValueError:
            mode = "names"

        try:
            if mode == "positions":
                result: ReplaceResult = QueueDomainService.replace_by_positions(members, pos1, pos2, ctx.queue_name)
            else:
                name1, name2 = parse_users_names(args, members)
                result: ReplaceResult = QueueDomainService.replace_by_names(members, name1, name2, ctx.queue_name)
        except (InvalidPositionError, UserNotFoundError) as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return ReplaceResult(ctx.queue_name, None, None, None, None, None)
        except Exception as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.ERROR)
            return ReplaceResult(ctx.queue_name, None, None, None, None, None)

        try:
            await self.repo.update_queue(ctx.chat_id, ctx.queue_id, result.updated_queue)
        except QueueError as ex:
            await self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return result

        await self.logger.replaced(ctx, result.user1, result.pos1 + 1, result.user2, result.pos2 + 1)
        return result

    async def send_queue_message(self, ctx: ActionContext, context):
        try:
            queue = await self.repo.get_queue(ctx.chat_id, ctx.queue_id)
            text = self.presenter.format_queue_text(ctx.queue_name, queue["members"])
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
            text = self.presenter.format_queue_text(ctx.queue_name, queue["members"])
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
