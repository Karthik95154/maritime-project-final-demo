from .base import BaseService
from repositories.inspection_repo import InspectionRepository
from motor.motor_asyncio import AsyncIOMotorDatabase

class InspectionService(BaseService):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = InspectionRepository(db)
