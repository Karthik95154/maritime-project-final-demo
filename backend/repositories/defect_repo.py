from .base import BaseRepository
from motor.motor_asyncio import AsyncIOMotorDatabase

class DefectRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "defect_registry")
