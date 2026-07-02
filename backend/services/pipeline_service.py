from .base import BaseService
from repositories.pipeline_repo import PipelineRepository
from motor.motor_asyncio import AsyncIOMotorDatabase

class PipelineService(BaseService):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = PipelineRepository(db)
