from fastapi import Depends, Request
from database import get_db
from motor.motor_asyncio import AsyncIOMotorDatabase
from services.user_service import UserService
from services.inspection_service import InspectionService
from services.vessel_service import VesselService
from services.defect_service import DefectService
from services.analysis_session_service import AnalysisSessionService
from services.drydock_visit_service import DrydockVisitService

def get_user_service(db: AsyncIOMotorDatabase = Depends(get_db)) -> UserService:
    return UserService(db)

def get_inspection_service(db: AsyncIOMotorDatabase = Depends(get_db)) -> InspectionService:
    return InspectionService(db)

def get_vessel_service(db: AsyncIOMotorDatabase = Depends(get_db)) -> VesselService:
    return VesselService(db)

def get_defect_service(db: AsyncIOMotorDatabase = Depends(get_db)) -> DefectService:
    return DefectService(db)


def get_analysis_session_service(db: AsyncIOMotorDatabase = Depends(get_db)) -> AnalysisSessionService:
    return AnalysisSessionService(db)

def get_drydock_visit_service(db: AsyncIOMotorDatabase = Depends(get_db)) -> DrydockVisitService:
    return DrydockVisitService(db)
