# queue/mongo_storage.py
import os
from logging import ERROR

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from .logger import QueueLogger

load_dotenv()

MONGO_PUBLIC_URL = os.getenv("MONGO_PUBLIC_URL", "mongodb://localhost:27017")
print(MONGO_PUBLIC_URL)
if not MONGO_PUBLIC_URL:
    MONGO_PUBLIC_URL = "mongodb://localhost:27017"

DB_NAME = "queue_bot"

client = AsyncIOMotorClient(MONGO_PUBLIC_URL)
db = client[DB_NAME]
queue_collection = db["queue_data"]
user_collection = db["user_data"]


async def ensure_indexes():
    """Создаёт уникальный индекс по chat_id"""
    try:
        await queue_collection.create_index("chat_id", unique=True)
        QueueLogger.log("MongoDB index on 'chat_id' ensured.")
    except Exception as e:
        QueueLogger.log(f"Failed to create index: {e}", level=ERROR)
