# queue/mongo_storage.py
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
print(MONGO_URL)


DB_NAME = "queue_bot"

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
queue_collection = db["queue_data"]
user_collection = db["user_data"]
log_collection = db["log_data"]
