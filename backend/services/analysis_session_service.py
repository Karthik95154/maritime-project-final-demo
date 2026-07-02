from .base import BaseService
from repositories.analysis_session_repo import AnalysisSessionRepository
from motor.motor_asyncio import AsyncIOMotorDatabase

class AnalysisSessionService(BaseService):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = AnalysisSessionRepository(db)
