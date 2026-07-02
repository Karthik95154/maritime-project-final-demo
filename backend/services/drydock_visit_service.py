from .base import BaseService
from repositories.drydock_visit_repo import DrydockVisitRepository
from motor.motor_asyncio import AsyncIOMotorDatabase

class DrydockVisitService(BaseService):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = DrydockVisitRepository(db)
