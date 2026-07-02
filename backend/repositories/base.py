from typing import Any, Dict, List, Optional, Tuple, Union
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId

class BaseRepository:
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        self.db = db
        self.collection = db[collection_name]

    async def create(self, data: Dict[str, Any]) -> str:
        result = await self.collection.insert_one(data)
        return str(result.inserted_id)

    async def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one(query)

    async def find_many(self, query: Dict[str, Any], limit: int = 0, skip: int = 0, sort: Optional[List[Tuple[str, int]]] = None) -> List[Dict[str, Any]]:
        cursor = self.collection.find(query).skip(skip)
        if sort:
            cursor = cursor.sort(sort)
        if limit > 0:
            cursor = cursor.limit(limit)
        return await cursor.to_list(length=None)

    async def update(self, query: Dict[str, Any], update_data: Dict[str, Any]) -> int:
        result = await self.collection.update_many(query, {"$set": update_data})
        return result.modified_count
        
    async def update_custom(self, query: Dict[str, Any], update_op: Dict[str, Any]) -> int:
        result = await self.collection.update_many(query, update_op)
        return result.modified_count

    async def delete(self, query: Dict[str, Any]) -> int:
        result = await self.collection.delete_many(query)
        return result.deleted_count

    async def exists(self, query: Dict[str, Any]) -> bool:
        count = await self.collection.count_documents(query, limit=1)
        return count > 0

    async def count(self, query: Dict[str, Any]) -> int:
        return await self.collection.count_documents(query)

    async def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cursor = self.collection.aggregate(pipeline)
        return await cursor.to_list(length=None)
