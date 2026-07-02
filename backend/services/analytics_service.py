from .base import BaseService
from repositories.analytics_repo import AnalyticsRepository
from motor.motor_asyncio import AsyncIOMotorDatabase

class AnalyticsService(BaseService):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = AnalyticsRepository(db)
