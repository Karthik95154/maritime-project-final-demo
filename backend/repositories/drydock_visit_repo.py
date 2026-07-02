from .base import BaseRepository
from motor.motor_asyncio import AsyncIOMotorDatabase

class DrydockVisitRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "drydock_visits")
