from .base import BaseService
from repositories.vessel_repo import VesselRepository
from motor.motor_asyncio import AsyncIOMotorDatabase

class VesselService(BaseService):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = VesselRepository(db)
