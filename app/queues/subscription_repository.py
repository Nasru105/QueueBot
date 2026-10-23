from motor.motor_asyncio import AsyncIOMotorDatabase


class SubscriptionRepository:
    """Подписки не зависят от наличия активных очередей в чате."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["queue_subscriptions"]

    async def subscribe(self, chat_id: int, user_id: int) -> bool:
        result = await self.collection.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {"$setOnInsert": {"chat_id": chat_id, "user_id": user_id}},
            upsert=True,
        )
        return result.upserted_id is not None

    async def unsubscribe(self, chat_id: int, user_id: int) -> bool:
        result = await self.collection.delete_one({"chat_id": chat_id, "user_id": user_id})
        return result.deleted_count > 0

    async def get_subscribers(self, chat_id: int) -> list[int]:
        cursor = self.collection.find({"chat_id": chat_id}, {"_id": 0, "user_id": 1})
        return [doc["user_id"] async for doc in cursor]
