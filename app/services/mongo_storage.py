# queue/mongo_storage.py
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase



class MongoDatabase:
    def __init__(self):
        load_dotenv()
        self.mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        self.db_name = "queue_bot"
        self.client: AsyncIOMotorClient = None
        self.db: AsyncIOMotorDatabase = None

    async def connect(self):
        """Создает подключение"""
        self.client = AsyncIOMotorClient(self.mongo_url)
        self.db = self.client[self.db_name]

    async def close(self):
        """Закрывает подключение"""
        if self.client:
            self.client.close()

    async def ensure_indexes(self):
        """Создаёт уникальные индексы чатов и подписок."""
        await self.db["queue_data"].create_index("chat_id", unique=True)
        await self.db["queue_subscriptions"].create_index(
            [("chat_id", 1), ("user_id", 1)], unique=True
        )
