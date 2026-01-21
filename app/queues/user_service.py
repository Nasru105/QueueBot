from telegram import User

from app.queues.queue_repository import QueueRepository
from app.utils.utils import strip_user_full_name


class UserService:
    """
    Работа с отображаемыми именами пользователей (обёртка над repo).
    """

    def __init__(self, repo):
        self.repo: QueueRepository = repo

    async def get_user_display_name(self, user: User, chat_id: int) -> str:
        doc_user = await self.repo.get_user_display_name(user)
        chat_str = str(chat_id)
        display_names = doc_user.get("display_names", {})

        # prefer chat-specific, then global, then full name, then username
        return display_names.get(chat_str) or display_names.get("global") or strip_user_full_name(user)

    async def set_user_display_name(self, ctx, user: User, display_name: str, global_mode: bool = False):
        user_doc = await self.repo.get_user_display_name(user)
        chat_str = str(ctx.chat_id)
        if "display_names" not in user_doc:
            user_doc["display_names"] = {}
        user_doc["display_names"][chat_str if not global_mode else "global"] = display_name or strip_user_full_name(
            user
        )
        await self.repo.update_user_display_name(user.id, user_doc["display_names"])

    async def clear_user_display_name(self, ctx, user: User, global_mode: bool = False):
        user_doc = await self.repo.get_user_display_name(user)
        chat_str = str(ctx.chat_id)

        if global_mode or "display_names" not in user_doc:
            user_doc["display_names"]["global"] = strip_user_full_name(user)
        else:
            user_doc["display_names"].pop(chat_str, None)
        await self.repo.update_user_display_name(user.id, user_doc["display_names"])
        return user_doc["display_names"]["global"]
