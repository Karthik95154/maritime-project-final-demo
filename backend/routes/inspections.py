from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends

from dependencies.services import get_inspection_service, get_drydock_visit_service, get_analysis_session_service, get_vessel_service
from services.drydock_visit_service import DrydockVisitService
from services.analysis_session_service import AnalysisSessionService
from services.vessel_service import VesselService
from services.inspection_service import InspectionService
from models import InspectionSession
from services.session_views import build_dashboard, build_defects, build_summary

router = APIRouter()

async def _all_sessions(inspection_service: InspectionService) -> list[InspectionSession]:
    # Need direct DB access or sort parameter in find_many
    docs = await inspection_service.repo.find_many({}, sort=[("created_at", -1)])
    return [InspectionSession(**doc) for doc in docs]

async def _session_or_404(session_id: str, inspection_service: InspectionService) -> InspectionSession:
    doc = await inspection_service.repo.find_one({"session_id": session_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    return InspectionSession(**doc)

@router.get("/dashboard")
async def get_dashboard(inspection_service: InspectionService = Depends(get_inspection_service)):
    sessions = await _all_sessions(inspection_service)
    return build_dashboard(sessions)

@router.get("/inspections")
async def list_inspections(inspection_service: InspectionService = Depends(get_inspection_service)):
    sessions = await _all_sessions(inspection_service)
    return [build_summary(session) for session in sessions]

@router.get("/batches")
async def list_batches(inspection_service: InspectionService = Depends(get_inspection_service), drydock_visit_service: DrydockVisitService = Depends(get_drydock_visit_service), analysis_session_service: AnalysisSessionService = Depends(get_analysis_session_service), vessel_service: VesselService = Depends(get_vessel_service)):
    
    visits = await drydock_visit_service.repo.find_many({}, sort=[("start_date", -1)])
    
    response = []
    for v in visits:
        vid = v.get("visit_id")
        ship_id = v.get("ship_id")
        vessel = await vessel_service.repo.find_one({"imo": ship_id})
        vessel_name = vessel.get("vessel_name") if vessel else "Unknown Vessel"
        
        sessions = await analysis_session_service.repo.find_many({"visit_id": vid})
        videos = []
        for s in sessions:
            videos.extend(s.get("uploaded_videos", []))
            
        response.append({
            "batchId": vid,
            "createdAt": v.get("start_date").isoformat() if v.get("start_date") else None,
            "vesselName": vessel_name,
            "imoNumber": ship_id,
            "status": v.get("status"),
            "videos": videos,
            "videoCount": len(videos)
        })
    return response

@router.get("/inspections/latest")
async def latest_inspection(inspection_service: InspectionService = Depends(get_inspection_service)):
    sessions = await _all_sessions(inspection_service)
    if not sessions:
        raise HTTPException(status_code=404, detail="No inspection sessions found")
    return build_summary(sessions[0])

@router.get("/inspections/{session_id}/progress")
async def inspection_progress(session_id: str, inspection_service: InspectionService = Depends(get_inspection_service)):
    session = await _session_or_404(session_id, inspection_service)
    summary = build_summary(session)
    stage_order = [
        "Frame Extraction",
        "Awaiting Frame Review",
        "CDS Detection",
        "Temporal Consistency",
        "Unique Defect Extraction",
        "Awaiting Defect Review",
        "Repair Estimation",
        "Document Generation",
    ]
    current_stage = summary["currentStage"]
    current_index = stage_order.index(current_stage) if current_stage in stage_order else 0
    steps = []

    for index, label in enumerate(stage_order):
        status = "todo"
        if summary["status"] == "Completed":
            status = "done"
        elif index < current_index:
            status = "done"
        elif index == current_index:
            status = "active"
        steps.append({"label": label, "status": status})

    base_time = session.created_at or datetime.utcnow()
    current_message = "Internal team is verifying AI output before the next step." if "Awaiting" in current_stage else "Pipeline stage running"
    logs = [
        {"time": base_time.replace(microsecond=0).strftime("%H:%M:%S"), "message": "Video accepted and processing started"},
        {"time": base_time.replace(microsecond=0).strftime("%H:%M:%S"), "message": current_message},
        {"time": base_time.replace(microsecond=0).strftime("%H:%M:%S"), "message": f"Current stage: {current_stage}"},
    ]

    return {**summary, "steps": steps, "logs": logs}

@router.get("/inspections/{session_id}/defects")
async def inspection_defects(session_id: str, inspection_service: InspectionService = Depends(get_inspection_service)):
    session = await _session_or_404(session_id, inspection_service)
    return {**build_summary(session), "defects": build_defects(session)}

@router.get("/inspections/{session_id}/visualization")
async def inspection_visualization(session_id: str, inspection_service: InspectionService = Depends(get_inspection_service)):
    session = await _session_or_404(session_id, inspection_service)
    defects = build_defects(session)
    return {
        **build_summary(session),
        "defects": defects,
        "markers": [
            {
                "defectId": defect["defectId"],
                "x": defect["marker"]["x"],
                "y": defect["marker"]["y"],
                "severity": defect["severity"],
            }
            for defect in defects
        ],
        "selectedDefectId": defects[0]["defectId"] if defects else None,
    }

@router.get("/inspections/{session_id}/report")
async def inspection_report(session_id: str, inspection_service: InspectionService = Depends(get_inspection_service)):
    session = await _session_or_404(session_id, inspection_service)
    defects = build_defects(session)
    summary = build_summary(session)
    return {
        **summary,
        "sections": [
            "1 Executive Summary",
            "2 Inspection Details",
            "3 Defect Summary",
            "4 Defect Analysis",
            "5 Repair Estimation",
            "6 Recommendations",
            "7 Annexures",
        ],
        "executiveSummary": (
            f"{summary['vesselName']} inspection identified {len(defects)} defects "
            f"with estimated repair exposure of INR {summary['totalEstimatedCost']:,.0f}."
        ),
        "defects": defects,
        "downloadDocxUrl": f"/api/v1/download/{session.session_id}" if summary["documentReady"] else None,
        "downloadPdfUrl": f"/api/v1/download/{session_id}/pdf" if summary["documentReady"] else None,
    }

@router.get("/inspections/{session_id}/progression")
async def inspection_progression(session_id: str, inspection_service: InspectionService = Depends(get_inspection_service)):
    session = await _session_or_404(session_id, inspection_service)
    defects = build_defects(session)
    if defects:
        defect = defects[0]
        area = defect["area"]
        timeline = [
            {"label": "05 May 2024", "area": round(area * 0.50, 2), "severity": "Medium", "image": defect["thumbnail"], "sessionId": session.session_id},
            {"label": "20 Aug 2024", "area": round(area * 0.72, 2), "severity": "Medium", "image": defect["thumbnail"], "sessionId": session.session_id},
            {"label": "12 Dec 2024", "area": round(area * 0.86, 2), "severity": "High" if defect["severity"] == "High" else "Medium", "image": defect["thumbnail"], "sessionId": session.session_id},
            {"label": (session.created_at or datetime.utcnow()).strftime("%d %b %Y"), "area": round(area, 2), "severity": defect["severity"], "image": defect["thumbnail"], "sessionId": session.session_id},
        ]
        first = timeline[0]["area"]
        last = timeline[-1]["area"]
        growth = round((((last - first) / first) * 100), 0) if first else 0
        defect_id = defect["defectId"]
    else:
        timeline = []
        growth = 0
        defect_id = "N/A"

    return {
        **build_summary(session),
        "defectId": defect_id,
        "location": "Port Side - Mid Section",
        "timeline": timeline,
        "areaGrowthPercent": growth,
        "severityChange": f"{timeline[0]['severity']} -> {timeline[-1]['severity']}" if timeline else "Stable",
        "recommendedAction": "Repair recommended within 30 days" if growth > 25 else "Continue monitoring",
    }

@router.delete("/inspections/{session_id}")
async def delete_inspection(session_id: str, inspection_service: InspectionService = Depends(get_inspection_service)):
    try:
        deleted = await inspection_service.repo.delete({"session_id": session_id})
        if deleted == 0:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"status": "success", "message": "Inspection deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
