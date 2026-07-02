from .base import BaseService
from repositories.user_repo import UserRepository
from motor.motor_asyncio import AsyncIOMotorDatabase

class UserService(BaseService):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = UserRepository(db)
