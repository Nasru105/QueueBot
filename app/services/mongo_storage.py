# queue/mongo_storage.py
import os
from logging import ERROR

from motor.motor_asyncio import AsyncIOMotorClient

from .logger import QueueLogger

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "queue_bot"

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
queue_collection = db["queue_data"]


async def ensure_indexes():
    """Создаёт уникальный индекс по chat_id"""
    try:
        await queue_collection.create_index("chat_id", unique=True)
        QueueLogger.log("MongoDB index on 'chat_id' ensured.")
    except Exception as e:
        QueueLogger.log(f"Failed to create index: {e}", level=ERROR)
