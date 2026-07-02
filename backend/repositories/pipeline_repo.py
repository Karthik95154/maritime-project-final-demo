from .base import BaseRepository
from motor.motor_asyncio import AsyncIOMotorDatabase

class PipelineRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "pipeline_data")
