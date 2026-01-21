# queue/mongo_storage.py
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from app.services.logger import logger


class MongoDatabase:
    def __init__(self):
        load_dotenv()
        self.mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        self.db_name = "queue_bot"
        self.client: AsyncIOMotorClient = None
        self.db = None

    def connect(self):
        """Создает подключение"""
        self.client = AsyncIOMotorClient(self.mongo_url)
        self.db = self.client[self.db_name]
        logger.log("INFO", f"Connected to MongoDB: {self.mongo_url}")

    def close(self):
        """Закрывает подключение"""
        if self.client:
            self.client.close()

    async def ensure_indexes(self):
        """Создаёт уникальный индекс по chat_id"""
        await self.db["queue_data"].create_index("chat_id", unique=True)
        logger.log("INFO", "Создание индексов")


mongo_db = MongoDatabase()
mongo_db.connect()
