import logging
from typing import List

from telegram.ext import ContextTypes, ExtBot

from app.queues.queue_repository import QueueRepository
from app.queues_menu.inline_keyboards import queues_menu_keyboard
from app.services.logger import QueueLogger
from app.utils.utils import parse_users_names, safe_delete

from .domain import QueueDomainService
from .errors import InvalidPositionError, QueueError, QueueNotFoundError, UserNotFoundError
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
        try:
            await self.repo.create_queue(ctx.chat_id, ctx.chat_title, ctx.queue_name)
            self.logger.log(ctx, "create queue")
            return ctx.queue_name
        except QueueError as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return

    async def delete_queue(self, ctx: ActionContext):
        try:
            await self.repo.delete_queue(ctx.chat_id, ctx.queue_name)
            self.logger.log(ctx, "delete queue")

        except QueueError as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)

    async def join_to_queue(self, ctx: ActionContext, user) -> int:
        # repo should implement add_to_queue (atomic on DB side if possible)
        try:
            # If user is a string (tests, admin insert), use it as display_name
            if isinstance(user, str):
                display_name = user
                try:
                    # try calling new signature on repo (some mocks may accept any args)
                    position = await self.repo.add_to_queue(ctx.chat_id, ctx.queue_name, None, display_name)
                except TypeError:
                    # fallback for mocks or legacy repos that accept (chat_id, queue_name, display_name)
                    position = await self.repo.add_to_queue(ctx.chat_id, ctx.queue_name, display_name)
                if position:
                    self.logger.joined(ctx, display_name, position)
                return position

            display_name = await self.user_service.get_user_display_name(user, ctx.chat_id)
            # Try bind the user id to an existing item with matching display_name
            try:
                idx = await self.repo.attach_user_id_by_display_name(ctx.chat_id, ctx.queue_name, display_name, user.id)
            except Exception:
                idx = None

            if idx is not None:
                # updated existing entry — return position
                position = idx + 1
                if position:
                    self.logger.joined(ctx, display_name, position)
                return position
            position = await self.repo.add_to_queue(ctx.chat_id, ctx.queue_name, user.id, display_name)
            if position:
                self.logger.joined(ctx, display_name, position)
            return position
        except QueueError as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)

    async def leave_from_queue(self, ctx: ActionContext, user) -> int:
        try:
            # backward compatibility: user may be display_name string
            if isinstance(user, str):
                try:
                    position = await self.repo.remove_from_queue(ctx.chat_id, ctx.queue_name, user.id)
                except TypeError:
                    position = await self.repo.remove_from_queue(ctx.chat_id, ctx.queue_name, None)
                if position:
                    self.logger.leaved(ctx, user, position)
                return position

            try:
                position = await self.repo.remove_from_queue(ctx.chat_id, ctx.queue_name, user.id)
            except TypeError:
                position = await self.repo.remove_from_queue(ctx.chat_id, ctx.queue_name, user)

            if position:
                display_name = await self.user_service.get_user_display_name(user, ctx.chat_id)
                self.logger.leaved(ctx, display_name, position)
            return position
        except QueueError as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)

    # ------ business operations (using domain) ------
    async def remove_from_queue(self, ctx: ActionContext, args: List[str]) -> RemoveResult:
        try:
            queue = await self.repo.get_queue(ctx.chat_id, ctx.queue_name)
        except QueueError as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return RemoveResult(None, None, None)

        if queue is None:
            return RemoveResult(None, None, None)

        try:
            res = self.domain.remove_by_pos_or_name(queue, args)
        except InvalidPositionError as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return RemoveResult(None, None, None)
        except Exception as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.ERROR)
            return RemoveResult(None, None, None)

        if res.removed_name:
            try:
                await self.repo.update_queue(ctx.chat_id, ctx.queue_name, res.updated_queue)
                self.logger.removed(ctx, res.removed_name, res.position)
            except QueueError as ex:
                self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
        return res

    async def insert_into_queue(self, ctx: ActionContext, args: List[str]) -> InsertResult:
        try:
            queue = await self.repo.get_queue(ctx.chat_id, ctx.queue_name)
        except QueueError as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return InsertResult(None, None, None, None)

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

        try:
            res = self.domain.insert_at_position(queue, user_name, desired_pos)
        except InvalidPositionError as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return InsertResult(None, None, None, None)
        except Exception as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.ERROR)
            return InsertResult(None, None, None, None)

        if res.user_name:
            try:
                await self.repo.update_queue(ctx.chat_id, ctx.queue_name, res.updated_queue)
                if res.old_position:
                    # old_position already 1-based
                    self.logger.removed(ctx, user_name, res.old_position)
                self.logger.inserted(ctx, user_name, res.position)
            except QueueError as ex:
                self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
        return res

    async def replace_users_queue(self, ctx: ActionContext, args: List[str]) -> ReplaceResult:
        try:
            queue = await self.repo.get_queue(ctx.chat_id, ctx.queue_name)
        except QueueError as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
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
                result: ReplaceResult = QueueDomainService.replace_by_positions(queue, pos1, pos2, ctx.queue_name)
            else:
                name1, name2 = parse_users_names(args, queue)
                result: ReplaceResult = QueueDomainService.replace_by_names(queue, name1, name2, ctx.queue_name)
        except (InvalidPositionError, UserNotFoundError) as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return ReplaceResult(ctx.queue_name, None, None, None, None, None)
        except Exception as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.ERROR)
            return ReplaceResult(ctx.queue_name, None, None, None, None, None)

        try:
            await self.repo.update_queue(ctx.chat_id, ctx.queue_name, result.updated_queue)
        except QueueError as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
            return result

        self.logger.replaced(ctx, result.user1, result.pos1 + 1, result.user2, result.pos2 + 1)
        return result

    async def send_queue_message(self, ctx: ActionContext, context):
        try:
            queue = await self.repo.get_queue(ctx.chat_id, ctx.queue_name) or []
            text = self.presenter.format_queue_text(ctx.queue_name, queue)
            queue_index = await self.get_queue_index(ctx.chat_id, ctx.queue_name)
            keyboard = self.presenter.build_keyboard(queue_index)
            return await self.message_service.send_queue_message(ctx, text, keyboard, context)
        except QueueError as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)

    async def update_queue_message(
        self, ctx: ActionContext, query_or_update=None, context: ContextTypes.DEFAULT_TYPE = None
    ):
        try:
            queue = await self.repo.get_queue(ctx.chat_id, ctx.queue_name) or []
            text = self.presenter.format_queue_text(ctx.queue_name, queue)
            queue_index = await self.get_queue_index(ctx.chat_id, ctx.queue_name)
            keyboard = self.presenter.build_keyboard(queue_index)
            return await self.message_service.edit_queue_message(
                ctx, text, keyboard, query_or_update=query_or_update, context=context
            )
        except QueueError as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)

    async def get_queue_index(self, chat_id: int, queue_name: str) -> int:
        try:
            queues = await self.repo.get_all_queues(chat_id)
            return list(queues.keys()).index(queue_name)
        except ValueError:
            raise QueueNotFoundError(f"queue '{queue_name}' not found")
        except QueueError:
            raise

    async def rename_queue(self, ctx: ActionContext, new_name: str):
        try:
            await self.repo.rename_queue(ctx.chat_id, ctx.queue_name, new_name)
            self.logger.log(ctx, f"rename queue {ctx.queue_name} → {new_name}")
        except QueueError as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)

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
            self.logger.log(None, f"ERROR getting display name: {ex}", logging.WARNING)
            return None

    async def set_user_display_name(self, ctx, user, display_name: str, global_mode=False):
        try:
            await self.user_service.set_user_display_name(ctx, user, display_name, global_mode)
            self.logger.log(ctx, f"set display name → {display_name}")
        except QueueError as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)

    async def clear_user_display_name(self, ctx, user, global_mode=False):
        try:
            user_display_name = await self.user_service.clear_user_display_name(ctx, user, global_mode)
            self.logger.log(ctx, "clear display name")
            return user_display_name
        except QueueError as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)

    async def mass_update_existing_queues(self, bot: ExtBot[None], ctx, message_list_id):
        queues = await self.repo.get_all_queues(ctx.chat_id)

        if not queues:
            await safe_delete(bot, ctx, message_list_id)
        try:
            await self.message_service.mass_update(bot, ctx, queues, self.presenter)
            if message_list_id:
                new_keyboard = await queues_menu_keyboard(list(queues.keys()))
                await bot.edit_message_text(
                    text="Выберите очередь:", chat_id=ctx.chat_id, message_id=message_list_id, reply_markup=new_keyboard
                )

        except QueueError as ex:
            self.logger.log(ctx, f"{type(ex).__name__}: {ex}", logging.WARNING)
