from .base import BaseService
from repositories.defect_repo import DefectRepository
from motor.motor_asyncio import AsyncIOMotorDatabase

class DefectService(BaseService):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = DefectRepository(db)
