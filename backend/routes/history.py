from fastapi import APIRouter, HTTPException, Depends
from dependencies.services import get_inspection_service
from services.inspection_service import InspectionService

router = APIRouter()

@router.get("/history")
async def get_history(inspection_service: InspectionService = Depends(get_inspection_service)):
    sessions = await inspection_service.repo.find_many({})
    
    response = []
    for s in sessions:
        response.append({
            "session_id": s.get("session_id"),
            "video_name": s.get("video_name"),
            "status": s.get("status"),
            "progress": s.get("progress"),
            "created_at": s.get("created_at"),
            "document_path": s.get("document_path")
        })

    return response

@router.delete("/history/{session_id}")
async def delete_history(session_id: str, inspection_service: InspectionService = Depends(get_inspection_service)):
    deleted_count = await inspection_service.repo.delete({"session_id": session_id})
    
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return {"message": "Session deleted successfully"}
