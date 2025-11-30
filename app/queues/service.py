import logging
from typing import List

from telegram.ext import ContextTypes

from app.queues.queue_repository import QueueRepository
from app.services.logger import QueueLogger
from app.utils.utils import parse_users_names

from .domain import QueueDomainService
from .message_service import QueueMessageService
from .models import ActionContext, InsertResult, RemoveResult, ReplaceResult
from .presenter import QueuePresenter
from .user_service import UserService


class QueueFacadeService:
    """
    Верхнеуровневый сервис, который используют хендлеры.
    Компоненты (repo, presenter, message_service ...) инжектируются через конструктор.
    """

    def __init__(self, repo, keyboard_factory, logger=QueueLogger):
        self.repo: QueueRepository = repo
        self.domain = QueueDomainService()
        self.presenter = QueuePresenter(keyboard_factory)
        self.message_service = QueueMessageService(repo, bot_logger=logger)
        self.user_service = UserService(repo)
        self.logger = logger

    # ------ queue management (thin orchestrations) ------
    async def create_queue(self, ctx: ActionContext):
        await self.repo.create_queue(ctx.chat_id, ctx.chat_title, ctx.queue_name)
        self.logger.log(ctx.chat_title, ctx.queue_name, ctx.actor, "create queue")

    async def delete_queue(self, ctx: ActionContext):
        deleted = await self.repo.delete_queue(ctx.chat_id, ctx.queue_name)
        if deleted:
            self.logger.log(ctx.chat_title, ctx.queue_name, ctx.actor, "delete queue")
        else:
            self.logger.log(ctx.chat_title, ctx.queue_name, ctx.actor, "queue not found", level=logging.WARNING)

    async def join_to_queue(self, ctx: ActionContext, user_name: str):
        # repo should implement add_to_queue (atomic on DB side if possible)
        position = await self.repo.add_to_queue(ctx.chat_id, ctx.queue_name, user_name)
        if position:
            self.logger.joined(ctx.chat_title, ctx.queue_name, ctx.actor, user_name, position)
        return position

    async def leave_from_queue(self, ctx: ActionContext, user_name: str):
        position = await self.repo.remove_from_queue(ctx.chat_id, ctx.queue_name, user_name)
        if position:
            self.logger.leaved(ctx.chat_title, ctx.queue_name, ctx.actor, user_name, position)
        return position

    # ------ business operations (using domain) ------
    async def remove_from_queue(self, ctx: ActionContext, args: List[str]) -> RemoveResult:
        queue = await self.repo.get_queue(ctx.chat_id, ctx.queue_name)
        if queue is None:
            return RemoveResult(None, None, None)

        res = self.domain.remove_by_pos_or_name(queue, args)
        if res.removed_name:
            await self.repo.update_queue(ctx.chat_id, ctx.queue_name, res.updated_queue)
            self.logger.removed(ctx.chat_title, ctx.queue_name, ctx.actor, res.removed_name, res.position)
        return res

    async def insert_into_queue(self, ctx: ActionContext, args: List[str]) -> InsertResult:
        queue = await self.repo.get_queue(ctx.chat_id, ctx.queue_name)
        if queue is None:
            return InsertResult(None, None, None, None)

        # parse args: if last is int -> position
        desired_pos = None
        try:
            desired_pos = int(args[-1]) - 1
            user_name = " ".join(args[:-1]).strip()
        except Exception:
            user_name = " ".join(args).strip()
            desired_pos = None

        res = self.domain.insert_at_position(queue, user_name, desired_pos)
        if res.user_name:
            await self.repo.update_queue(ctx.chat_id, ctx.queue_name, res.updated_queue)
            if res.old_position:
                # old_position already 1-based
                self.logger.removed(ctx.chat_title, ctx.queue_name, ctx.actor, user_name, res.old_position)
            self.logger.inserted(ctx.chat_title, ctx.queue_name, ctx.actor, user_name, res.position)
        return res

    async def replace_users_queue(self, ctx: ActionContext, args: List[str]) -> ReplaceResult:
        queue = await self.repo.get_queue(ctx.chat_id, ctx.queue_name)
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
                result: ReplaceResult = QueueDomainService.replace_by_positions(queue, pos1, pos2, ctx.queue_name)
            else:
                name1, name2 = parse_users_names(args, queue)
                result: ReplaceResult = QueueDomainService.replace_by_names(queue, name1, name2, ctx.queue_name)
        except Exception as ex:
            self.logger.log(ctx.chat_title, ctx.queue_name, ctx.actor, f"ERROR {ex}", logging.ERROR)
            return ReplaceResult(ctx.queue_name, None, None, None, None, None)

        await self.repo.update_queue(ctx.chat_id, ctx.queue_name, result.updated_queue)

        self.logger.replaced(
            ctx.chat_title, ctx.queue_name, ctx.actor, result.user1, result.pos1 + 1, result.user2, result.pos2 + 1
        )
        return result

    async def send_queue_message(self, ctx: ActionContext, context):
        queue = await self.repo.get_queue(ctx.chat_id, ctx.queue_name) or []
        text = self.presenter.format_queue_text(ctx.queue_name, queue)
        queue_index = await self.get_queue_index(ctx.chat_id, ctx.queue_name)
        keyboard = self.presenter.build_keyboard(queue_index)
        return await self.message_service.send_queue_message(ctx, text, keyboard, context)

    async def update_queue_message(
        self, ctx: ActionContext, query_or_update=None, context: ContextTypes.DEFAULT_TYPE = None
    ):
        queue = await self.repo.get_queue(ctx.chat_id, ctx.queue_name) or []
        text = self.presenter.format_queue_text(ctx.queue_name, queue)
        queue_index = await self.get_queue_index(ctx.chat_id, ctx.queue_name)
        keyboard = self.presenter.build_keyboard(queue_index)
        return await self.message_service.edit_queue_message(
            ctx, text, keyboard, query_or_update=query_or_update, context=context
        )

    async def get_queue_index(self, chat_id: int, queue_name: str) -> int:
        queues = await self.repo.get_all_queues(chat_id)
        return list(queues.keys()).index(queue_name)

    async def rename_queue(self, ctx: ActionContext, new_name: str):
        await self.repo.rename_queue(ctx.chat_id, ctx.queue_name, new_name)
        self.logger.log(ctx.chat_title, ctx.queue_name, ctx.actor, f"rename queue {ctx.queue_name} → {new_name}")

    async def generate_queue_name(self, chat_id: int) -> str:
        queues = await self.repo.get_all_queues(chat_id)
        return self.domain.generate_queue_name(queues)

    async def get_count_queues(self, chat_id: int) -> int:
        queues = await self.repo.get_all_queues(chat_id)
        return len(queues)

    async def get_user_display_name(self, user, chat_id: int):
        return await self.user_service.get_user_display_name(user, chat_id)

    async def set_user_display_name(self, ctx, user, display_name: str, global_mode=False):
        await self.user_service.set_user_display_name(ctx, user, display_name, global_mode)
        self.logger.log(ctx.chat_title, ctx.queue_name, ctx.actor, f"set display name → {display_name}")

    async def clear_user_display_name(self, ctx, user, global_mode=False):
        await self.user_service.clear_user_display_name(ctx, user, global_mode)
        self.logger.log(ctx.chat_title, ctx.queue_name, ctx.actor, "clear display name")

    async def mass_update_existing_queues(self, bot, ctx):
        queues = await self.repo.get_all_queues(ctx.chat_id)
        if not queues:
            return
        await self.message_service.mass_update(bot, ctx, queues, self.presenter)
