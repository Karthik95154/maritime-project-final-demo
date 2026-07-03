from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Depends
from dependencies.services import get_vessel_service, get_defect_service, get_drydock_visit_service, get_analysis_session_service
from services.drydock_visit_service import DrydockVisitService
from services.analysis_session_service import AnalysisSessionService
from services.vessel_service import VesselService
from services.defect_service import DefectService
from utils.response import success_response, error_response
from models import Vessel, DefectRegistry, AnalysisSession, DryDockVisit

router = APIRouter()


def _to_iso(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return str(value)

@router.get("/")
async def list_vessels(vessel_service: VesselService = Depends(get_vessel_service), defect_service: DefectService = Depends(get_defect_service)):
    vessels = await vessel_service.repo.find_many({}, limit=0)
    results = []
    for v in vessels:
        vessel_defects = await defect_service.repo.count({"vessel_id": v.get("imo"), "severity": "Critical"})
        total_defects = await defect_service.repo.count({"vessel_id": v.get("imo")})
        health = v.get("health_score", 100)
        risk = "Critical" if health < 60 else "High" if health < 75 else "Medium" if health < 90 else "Low"
        
        results.append({
            "imoNumber": v.get("imo"),
            "vesselName": v.get("vessel_name"),
            "vesselType": v.get("vessel_type"),
            "grossTonnage": v.get("gross_tonnage"),
            "lastInspectionDate": _to_iso(v.get("last_inspection_date")),
            "healthScore": health,
            "riskScore": risk,
            "criticalDefects": vessel_defects,
            "totalDefects": total_defects,
            "totalInspections": v.get("total_visits", 0),
            "owner": v.get("owner"),
            "operator": v.get("operator")
        })
    # Maintain original return signature
    return results

@router.get("/{imo_number}")
async def get_vessel(imo_number: str, vessel_service: VesselService = Depends(get_vessel_service), defect_service: DefectService = Depends(get_defect_service)):
    vessel = await vessel_service.repo.find_one({"imo": imo_number})
    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found")
        
    vessel_defects = await defect_service.repo.count({"vessel_id": imo_number, "severity": "Critical"})
    health = vessel.get("health_score", 100)
    risk = "Critical" if health < 60 else "High" if health < 75 else "Medium" if health < 90 else "Low"
    
    return {
        "imoNumber": vessel.get("imo"),
        "vesselName": vessel.get("vessel_name"),
        "vesselType": vessel.get("vessel_type"),
        "grossTonnage": vessel.get("gross_tonnage"),
        "healthScore": health,
        "riskScore": risk,
        "criticalDefects": vessel_defects,
        "totalVisits": vessel.get("total_visits", 0)
    }

@router.delete("/{imo_number}")
async def delete_vessel(imo_number: str, vessel_service: VesselService = Depends(get_vessel_service), defect_service: DefectService = Depends(get_defect_service), drydock_visit_service: DrydockVisitService = Depends(get_drydock_visit_service)):
    vessel = await vessel_service.repo.find_one({"imo": imo_number})
    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found")
        
    await vessel_service.repo.delete({"imo": imo_number})
    # For drydock visits, we could use a separate service but here we use the DB directly through vessel_service just for this edge case, or add it to repo
    await drydock_visit_service.repo.delete({"ship_id": imo_number})
    await defect_service.repo.delete({"vessel_id": imo_number})
    
    return {"status": "success", "message": f"Vessel {imo_number} deleted successfully"}

@router.get("/{imo_number}/visits")
async def get_vessel_visits(imo_number: str, vessel_service: VesselService = Depends(get_vessel_service), drydock_visit_service: DrydockVisitService = Depends(get_drydock_visit_service), analysis_session_service: AnalysisSessionService = Depends(get_analysis_session_service)):
    # Using underlying db temporarily for drydock visits
    visits = await drydock_visit_service.repo.find_many({"ship_id": imo_number}, sort=[("visit_number", -1)])
    
    response = []
    for v in visits:
        vid = v.get("visit_id")
        sessions = await analysis_session_service.repo.find_many({"visit_id": vid}, sort=[("created_at", -1)])
        
        response.append({
            "visitId": vid,
            "visitNumber": v.get("visit_number"),
            "visitType": v.get("visit_type"),
            "startDate": _to_iso(v.get("start_date")),
            "status": v.get("status"),
            "reportVersion": v.get("report_version"),
            "totalDefects": v.get("total_defects"),
            "sessions": [
                {
                    "sessionId": s.get("session_id"),
                    "videos": s.get("uploaded_videos", []),
                    "status": s.get("status"),
                    "createdAt": _to_iso(s.get("created_at"))
                } for s in sessions
            ]
        })
    return response

@router.get("/{imo_number}/defects")
async def get_vessel_defects(imo_number: str, defect_service: DefectService = Depends(get_defect_service)):
    docs = await defect_service.repo.find_many({"vessel_id": imo_number}, sort=[("last_detected", -1)])
    
    all_defects = []
    for defect in docs:
        all_defects.append({
            "defectId": defect.get("defect_id"),
            "visitId": defect.get("visit_id"),
            "thumbnail": defect.get("thumbnail"),
            "partName": defect.get("component"),
            "defectType": defect.get("defect_type"),
            "severity": defect.get("severity"),
            "area": defect.get("area"),
            "status": defect.get("status"),
            "repairCost": defect.get("cost_estimation", 0.0),
            "lineItems": defect.get("line_items", []),
            "firstDetected": _to_iso(defect.get("first_detected")),
            "lastDetected": _to_iso(defect.get("last_detected")),
            "sessionIds": defect.get("session_ids", []),
            "history": defect.get("history", [])
        })
            
    return all_defects

@router.get("/{imo_number}/reports/compare")
async def compare_reports(imo_number: str, v1: str, v2: str, defect_service: DefectService = Depends(get_defect_service)):
    all_defects = await defect_service.repo.find_many({"vessel_id": imo_number})
    
    new_defects = []
    updated_defects = []
    resolved_defects = []
    cost_diff = 0.0
    
    for defect in all_defects:
        sessions = defect.get("session_ids", [])
        if v2 in sessions and v1 not in sessions:
            new_defects.append(defect.get("defect_type"))
            cost_diff += defect.get("cost_estimation", 0)
        elif v2 in sessions and v1 in sessions:
            updated_defects.append(defect.get("defect_type"))
        elif v1 in sessions and v2 not in sessions and defect.get("status") in ["Repaired", "Closed"]:
            resolved_defects.append(defect.get("defect_type"))
            
    return {
        "fromVersion": v1,
        "toVersion": v2,
        "newDefects": new_defects,
        "updatedDefects": updated_defects,
        "resolvedDefects": resolved_defects,
        "costDifference": cost_diff,
        "healthScoreDifference": 0
    }
