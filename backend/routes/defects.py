from fastapi import APIRouter, Depends
from dependencies.services import get_defect_service
from services.defect_service import DefectService

router = APIRouter()

@router.get("/")
async def get_all_defects(defect_service: DefectService = Depends(get_defect_service)):
    docs = await defect_service.repo.find_many({}, sort=[("last_detected", -1)])
    
    all_defects = []
    for defect in docs:
        all_defects.append({
            "defectId": defect.get("defect_id"),
            "vesselId": defect.get("vessel_id"),
            "thumbnail": defect.get("thumbnail"),
            "partName": defect.get("component"),
            "defectType": defect.get("defect_type"),
            "severity": defect.get("severity"),
            "area": defect.get("area"),
            "status": defect.get("status"),
            "repairCost": defect.get("cost_estimation", 0.0),
            "firstDetected": defect.get("first_detected").isoformat() if defect.get("first_detected") else None,
            "lastDetected": defect.get("last_detected").isoformat() if defect.get("last_detected") else None,
            "sessionIds": defect.get("session_ids", []),
            "history": defect.get("history", []),
        })
            
    return all_defects
