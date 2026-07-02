import abc
import json
import asyncio
from typing import Any, Dict

class StorageBackend(abc.ABC):
    @abc.abstractmethod
    def save_json(self, session_id: str, stage_key: str, data: Any):
        pass

    @abc.abstractmethod
    def load_json(self, session_id: str, stage_key: str) -> Any:
        pass

    @abc.abstractmethod
    async def save_json_async(self, session_id: str, stage_key: str, data: Any):
        pass

    @abc.abstractmethod
    async def load_json_async(self, session_id: str, stage_key: str) -> Any:
        pass


class MongoStorageBackend(StorageBackend):
    def __init__(self):
        from database import db
        # If running sync, we might need a sync client, but Motor is async.
        # However, we can use pymongo directly for sync operations by using the same URI.
        from pymongo import MongoClient
        from config import settings
        self.sync_client = MongoClient(settings.mongo_uri)
        self.sync_db = self.sync_client[settings.mongo_db_name]
        self.collection = self.sync_db.pipeline_data

    def save_json(self, session_id: str, stage_key: str, data: Any):
        self.collection.update_one(
            {"session_id": session_id, "stage_key": stage_key},
            {"$set": {"data": data}},
            upsert=True
        )

    def load_json(self, session_id: str, stage_key: str) -> Any:
        doc = self.collection.find_one({"session_id": session_id, "stage_key": stage_key})
        if doc and "data" in doc:
            return doc["data"]
        return {}

    async def save_json_async(self, session_id: str, stage_key: str, data: Any):
        from database import get_db
        db = get_db()
        await db.pipeline_data.update_one(
            {"session_id": session_id, "stage_key": stage_key},
            {"$set": {"data": data}},
            upsert=True
        )

    async def load_json_async(self, session_id: str, stage_key: str) -> Any:
        from database import get_db
        db = get_db()
        doc = await db.pipeline_data.find_one({"session_id": session_id, "stage_key": stage_key})
        if doc and "data" in doc:
            return doc["data"]
        return {}

# Global instance
storage_backend = MongoStorageBackend()
