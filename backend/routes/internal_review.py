import asyncio
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from dependencies.services import get_inspection_service
from services.inspection_service import InspectionService
from fastapi import Depends
from models import InspectionSession
from services.storage import storage_backend
from pipeline_runner import load_json, save_json, resume_pipeline, _paths
from services.session_views import build_defects, build_summary
from session_manager import update_session, log_audit_trail, log_training_feedback

router = APIRouter(prefix="/internal/reviews", tags=["internal-review"])


async def _get_session_doc(session_id: str, inspection_service: InspectionService):
    doc = await inspection_service.repo.find_one({"session_id": session_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    return doc

@router.get("")
async def review_queue(inspection_service: InspectionService = Depends(get_inspection_service)):
    
    docs = await inspection_service.repo.find_many({}, sort=[("created_at", -1)])
    return [build_summary(InspectionSession(**doc)) for doc in docs]

@router.get("/{session_id}")
async def review_detail(session_id: str, inspection_service: InspectionService = Depends(get_inspection_service)):
    
    doc = await inspection_service.repo.find_one({"session_id": session_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")

    session = InspectionSession(**doc)
    summary = build_summary(session)
    output_path = doc.get("output_path", "")
    paths = _paths(output_path)
    
    # Load all available outputs for the UI
    data = {}
    for key in paths.keys():
        stage_data = await storage_backend.load_json_async(session_id, key)
        if stage_data:
            data[key] = stage_data

    return {
        **summary,
        "pipeline_data": data,
        "pipeline_context": session.pipeline_context
    }

class BaseDecisionPayload(BaseModel):
    decision: str
    notes: Optional[str] = None
    reviewer: Optional[str] = None

class ClassificationPayload(BaseDecisionPayload):
    corrections: list = []

class DetectionPayload(BaseDecisionPayload):
    corrections: list = []

class SegmentationPayload(BaseDecisionPayload):
    corrections: list = []

class AreaPayload(BaseDecisionPayload):
    corrections: dict = {}

class CostPayload(BaseDecisionPayload):
    corrections: dict = {}

class ReportPayload(BaseDecisionPayload):
    corrections: dict = {}

def apply_and_resume(session_id: str, payload, checkpoint: str, next_stage: str, output_key: str, data_to_save):
    if payload.decision == "reject":
        update_session(
            session_id,
            status="rejected",
            current_stage=f"{checkpoint} Rejected",
            review_status="rejected",
            review_notes=payload.notes,
            review_updated_by=payload.reviewer,
        )
        return {"status": "rejected"}
    
    # Save the human approved data
    
    # Synchronously get the document (wait this is inside an async endpoint, we should use async db)
    # So we do the save in the endpoint before calling this or just pass doc.
    pass

@router.post("/{session_id}/classification")
async def submit_classification(session_id: str, payload: ClassificationPayload, background_tasks: BackgroundTasks, inspection_service: InspectionService = Depends(get_inspection_service)):
    doc = await _get_session_doc(session_id, inspection_service)

    if payload.decision == "save_assessment":
        await storage_backend.save_json_async(session_id, "classification_human_json", payload.corrections)
        return {"status": "saved"}

    if doc.get("review_checkpoint") != "classification_review":
        raise HTTPException(status_code=400, detail="Invalid session or checkpoint")

    if payload.decision == "assess_continue":
        await storage_backend.save_json_async(session_id, "classification_human_json", payload.corrections)
        
        update_session(
            session_id,
            review_status="approved",
            review_notes=payload.notes,
            review_updated_by=payload.reviewer,
            status="processing",
            current_stage="Assessment Completed"
        )
        background_tasks.add_task(resume_pipeline, session_id)
        return {"status": "accepted"}
    raise HTTPException(status_code=400, detail="Unsupported decision")

@router.post("/{session_id}/part_detection")
async def submit_part_detection(session_id: str, payload: DetectionPayload, background_tasks: BackgroundTasks, inspection_service: InspectionService = Depends(get_inspection_service)):
    doc = await _get_session_doc(session_id, inspection_service)

    if payload.decision == "save_assessment":
        await storage_backend.save_json_async(session_id, "part_detection_human_json", payload.corrections)
        return {"status": "saved"}

    if doc.get("review_checkpoint") != "part_detection_review":
        raise HTTPException(status_code=400, detail="Invalid session or checkpoint")

    if payload.decision == "assess_continue":
        await storage_backend.save_json_async(session_id, "part_detection_human_json", payload.corrections)
        
        update_session(
            session_id,
            review_status="approved",
            review_notes=payload.notes,
            review_updated_by=payload.reviewer,
            status="processing",
            current_stage="Assessment Completed"
        )
        background_tasks.add_task(resume_pipeline, session_id)
        return {"status": "accepted"}
    raise HTTPException(status_code=400, detail="Unsupported decision")

@router.post("/{session_id}/defect_detection")
async def submit_defect_detection(session_id: str, payload: DetectionPayload, background_tasks: BackgroundTasks, inspection_service: InspectionService = Depends(get_inspection_service)):
    doc = await _get_session_doc(session_id, inspection_service)

    if payload.decision == "save_assessment":
        await storage_backend.save_json_async(session_id, "defect_detection_human_json", payload.corrections)
        return {"status": "saved"}

    if doc.get("review_checkpoint") != "defect_detection_review":
        raise HTTPException(status_code=400, detail="Invalid session or checkpoint")

    if payload.decision == "assess_continue":
        await storage_backend.save_json_async(session_id, "defect_detection_human_json", payload.corrections)
        
        update_session(
            session_id,
            review_status="approved",
            review_notes=payload.notes,
            review_updated_by=payload.reviewer,
            status="processing",
            current_stage="Assessment Completed"
        )
        background_tasks.add_task(resume_pipeline, session_id)
        return {"status": "accepted"}
    raise HTTPException(status_code=400, detail="Unsupported decision")

@router.post("/{session_id}/segmentation")
async def submit_segmentation(session_id: str, payload: SegmentationPayload, background_tasks: BackgroundTasks, inspection_service: InspectionService = Depends(get_inspection_service)):
    
    doc = await inspection_service.repo.find_one({"session_id": session_id})
    if not doc or doc.get("review_checkpoint") != "segmentation_review":
        raise HTTPException(status_code=400, detail="Invalid session or checkpoint")

    if payload.decision == "assess_continue":
        paths = _paths(doc.get("output_path"))
        await storage_backend.save_json_async(session_id, "segmentation_human_json", payload.corrections)
        
        update_session(
            session_id,
            review_status="approved",
            review_notes=payload.notes,
            review_updated_by=payload.reviewer,
            status="processing",
            current_stage="Assessment Completed"
        )
        background_tasks.add_task(resume_pipeline, session_id)
        return {"status": "accepted"}
    elif payload.decision == "save_assessment":
        await storage_backend.save_json_async(session_id, "segmentation_human_json", payload.corrections)
        return {"status": "saved"}

@router.post("/{session_id}/area")
async def submit_area(session_id: str, payload: AreaPayload, background_tasks: BackgroundTasks, inspection_service: InspectionService = Depends(get_inspection_service)):
    
    doc = await inspection_service.repo.find_one({"session_id": session_id})
    if not doc or doc.get("review_checkpoint") != "area_review":
        raise HTTPException(status_code=400, detail="Invalid session or checkpoint")

    if payload.decision == "assess_continue":
        paths = _paths(doc.get("output_path"))
        await storage_backend.save_json_async(session_id, "area_human_json", payload.corrections)
        
        update_session(
            session_id,
            review_status="approved",
            review_notes=payload.notes,
            review_updated_by=payload.reviewer,
            status="processing",
            current_stage="Assessment Completed"
        )
        background_tasks.add_task(resume_pipeline, session_id)
        return {"status": "accepted"}
    elif payload.decision == "save_assessment":
        await storage_backend.save_json_async(session_id, "area_human_json", payload.corrections)
        return {"status": "saved"}

@router.post("/{session_id}/cost")
async def submit_cost(session_id: str, payload: CostPayload, background_tasks: BackgroundTasks, inspection_service: InspectionService = Depends(get_inspection_service)):
    doc = await _get_session_doc(session_id, inspection_service)

    if payload.decision == "save_assessment":
        await storage_backend.save_json_async(session_id, "repair_human_json", payload.corrections)
        return {"status": "saved"}

    if doc.get("review_checkpoint") != "cost_review":
        raise HTTPException(status_code=400, detail="Invalid session or checkpoint")

    if payload.decision == "assess_continue":
        await storage_backend.save_json_async(session_id, "repair_human_json", payload.corrections)
        
        update_session(
            session_id,
            review_status="approved",
            review_notes=payload.notes,
            review_updated_by=payload.reviewer,
            status="processing",
            current_stage="Assessment Completed"
        )
        background_tasks.add_task(resume_pipeline, session_id)
        return {"status": "accepted"}
    raise HTTPException(status_code=400, detail="Unsupported decision")

class RecalculateAreaPayload(BaseModel):
    defect_id: str
    homography_points: list
    image_name: str

@router.post("/{session_id}/area/recalculate")
async def recalculate_area(session_id: str, payload: RecalculateAreaPayload, inspection_service: InspectionService = Depends(get_inspection_service)):
    
    doc = await inspection_service.repo.find_one({"session_id": session_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
        
    from pipeline_runner import recalculate_area_with_manual_homography
    
    output_path = doc.get("output_path", "")
    new_data = recalculate_area_with_manual_homography(
        session_folder=output_path, 
        defect_id=payload.defect_id, 
        homography_points=payload.homography_points, 
        image_name=payload.image_name
    )
    
    if not new_data:
        raise HTTPException(status_code=500, detail="Recalculation failed")
        
    return {"status": "success", "data": new_data}
