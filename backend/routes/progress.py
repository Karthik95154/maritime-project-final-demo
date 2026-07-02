from fastapi import APIRouter, Depends
from dependencies.services import get_inspection_service
from services.inspection_service import InspectionService

router = APIRouter()

@router.get("/progress/{session_id}")
async def get_progress(session_id: str, inspection_service: InspectionService = Depends(get_inspection_service)):
    session = await inspection_service.repo.find_one({"session_id": session_id})

    if not session:
        return {"error": "Session not found"}

    return {
        "session_id": session.get("session_id"),
        "status": session.get("status"),
        "progress": session.get("progress"),
        "current_stage": session.get("current_stage"),
        "document_ready": session.get("document_path") is not None,
        "document_path": session.get("document_path")
    }
