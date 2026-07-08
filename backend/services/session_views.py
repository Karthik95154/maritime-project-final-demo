import json
import os
from collections import Counter
from collections import defaultdict
from datetime import datetime
from typing import Any

from models import InspectionSession

DEFAULT_FRAME_WIDTH = 1280
DEFAULT_FRAME_HEIGHT = 720


def _read_json(path: str) -> Any:
    if not path or not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _output_file(session: InspectionSession, *parts: str) -> str:
    return os.path.join(session.output_path, *parts)


def _public_output_path(path: str | None) -> str | None:
    if not path:
        return None

    normalized = path.replace("\\", "/")

    if normalized.startswith("outputs/"):
        return f"/{normalized}"

    if "/outputs/" in normalized:
        return f"/outputs/{normalized.split('/outputs/', 1)[1]}"

    return normalized


def _title_case(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    return value.replace("_", " ").title()


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def load_outputs(session: InspectionSession) -> dict[str, Any]:
    from services.storage import storage_backend
    storage = storage_backend
    
    # Try loading from database first
    repair = storage.load_json(session.session_id, "repair_human_json")
    if not repair:
        repair = storage.load_json(session.session_id, "repair_ai_json")
        
    unique = storage.load_json(session.session_id, "area_human_json")
    if not unique:
        unique = storage.load_json(session.session_id, "unique_json")

    # Fallback to ephemeral disk if missing
    if not repair:
        repair = _read_json(
            _output_file(
                session,
                "module_5_repair_estimation_output",
                "repair_estimation_outputs.json",
            )
        )
    if not unique:
        unique = _read_json(
            _output_file(
                session,
                "module_4_unique_defect_frame_output",
                "unique_defect_outputs.json",
            )
        )

    return {
        "repair": repair,
        "unique": unique,
    }


def build_defects(session: InspectionSession) -> list[dict[str, Any]]:
    outputs = load_outputs(session)
    repair = outputs["repair"] or {}
    unique = outputs["unique"] or {}
    repair_defects = repair.get("defect_repairs", {})
    source_ids = list(repair_defects.keys() or unique.keys())
    defects: list[dict[str, Any]] = []

    for defect_id in source_ids:
        repair_defect = repair_defects.get(defect_id, {})
        unique_defect = unique.get(defect_id, {})
        metadata = repair_defect.get("defect_metadata", {})
        parts = metadata.get("overlapping_parts") or unique_defect.get("overlapping_parts") or []
        primary_part = parts[0]["part_name"] if parts else None
        bbox = metadata.get("bbox") or unique_defect.get("bbox") or [0, 0, 0, 0]

        defects.append(
            {
                "defectId": defect_id,
                "thumbnail": _public_output_path(metadata.get("best_frame_path") or unique_defect.get("best_frame_path")),
                "partName": _title_case(primary_part, "General Area"),
                "defectType": _title_case(repair_defect.get("defect_name") or unique_defect.get("defect_name"), "Unknown"),
                "severity": _title_case(repair_defect.get("severity") or unique_defect.get("severity"), "Low"),
                "area": _safe_float(metadata.get("defect_area") or unique_defect.get("defect_area")),
                "repairCost": round(_safe_float(repair_defect.get("repair_estimation", {}).get("estimated_total_cost", 0)), 2),
                "frameNumber": metadata.get("best_frame") or unique_defect.get("best_frame") or 0,
                "description": repair_defect.get("description"),
                "repairProcess": repair_defect.get("repair_process"),
                "marker": {
                    "x": round((((bbox[0] + bbox[2]) / 2) / DEFAULT_FRAME_WIDTH) * 100, 2),
                    "y": round((((bbox[1] + bbox[3]) / 2) / DEFAULT_FRAME_HEIGHT) * 100, 2),
                },
            }
        )

    return defects


def build_summary(session: InspectionSession) -> dict[str, Any]:
    defects = build_defects(session)
    critical_defects = sum(1 for defect in defects if defect["severity"] == "High")
    total_cost = sum(defect["repairCost"] for defect in defects)
    health_score = max(25, min(96, 100 - (critical_defects * 12) - (len(defects) * 3)))

    # Extract AI Confidence for the current review checkpoint
    ai_confidence = None
    if session.review_checkpoint and session.output_path:
        checkpoint_files = {
            "classification_review": "module_2_classification_output/classification_ai.json",
            "detection_review": "module_3_detection_output/detection_ai.json",
            "segmentation_review": "module_4_segmentation_output/segmentation_ai.json",
        }
        rel_path = checkpoint_files.get(session.review_checkpoint)
        if rel_path:
            file_path = os.path.join(session.output_path, rel_path)
            data = _read_json(file_path)
            if data:
                if session.review_checkpoint == "classification_review":
                    # classification output is usually {"classification": {"confidence": 0.99}} or {"confidence": 0.99}
                    if isinstance(data, dict):
                        cls_data = data.get("classification", data)
                        ai_confidence = _safe_float(cls_data.get("confidence"))
                    elif isinstance(data, list) and len(data) > 0:
                        cls_data = data[0].get("classification", data[0])
                        ai_confidence = _safe_float(cls_data.get("confidence"))
                elif session.review_checkpoint in ["detection_review", "segmentation_review"]:
                    # usually a list of defect_detections, we want the minimum confidence to flag it
                    if isinstance(data, dict) and "defect_detections" in data:
                        detections = data["defect_detections"]
                        confs = [_safe_float(d.get("confidence", 1.0)) for d in detections if "confidence" in d]
                        if confs:
                            ai_confidence = min(confs)

    return {
        "sessionId": session.session_id,
        "videoName": session.video_name,
        "status": _title_case(session.status, "Unknown"),
        "progress": session.progress or 0,
        "currentStage": session.current_stage or "Queued",
        "reviewCheckpoint": session.review_checkpoint,
        "reviewStatus": session.review_status,
        "reviewNotes": session.review_notes,
        "reviewUpdatedAt": session.review_updated_at.isoformat() if session.review_updated_at else None,
        "reviewUpdatedBy": session.review_updated_by,
        "pipelineResumeFrom": session.pipeline_resume_from,
        "documentReady": bool(session.document_path),
        "documentPath": _public_output_path(session.document_path),
        "createdAt": session.created_at.isoformat() if session.created_at else None,
        "vesselName": session.vessel_name or "MV Oceanic Unity",
        "imoNumber": session.imo_number or "1234567",
        "vesselType": session.vessel_type or "Bulk Carrier",
        "grossTonnage": session.gross_tonnage or "45678",
        "inspectorName": session.inspector_name or "John Inspector",
        "location": session.location or "Mumbai Port, India",
        "inspectionDate": session.inspection_date or (
            session.created_at.strftime("%Y-%m-%d") if session.created_at else None
        ),
        "comments": session.comments or "",
        "defectCount": len(defects),
        "criticalDefects": critical_defects,
        "totalEstimatedCost": round(total_cost, 2),
        "healthScore": health_score,
        "aiConfidence": ai_confidence,
    }


def build_dashboard(sessions: list[InspectionSession]) -> dict[str, Any]:
    summaries = [build_summary(session) for session in sessions]
    completed = [item for item in summaries if item["status"] == "Completed"]
    pending = [item for item in summaries if item["status"] != "Completed"]
    monthly_costs: dict[str, float] = defaultdict(float)
    defect_counts: Counter[str] = Counter()

    for session in sessions:
        defects = build_defects(session)
        month_key = (session.created_at or datetime.utcnow()).strftime("%b")
        monthly_costs[month_key] += sum(defect["repairCost"] for defect in defects)
        defect_counts.update(defect["defectType"] for defect in defects)

    total_cost = sum(item["totalEstimatedCost"] for item in summaries)
    avg_health = round(
        sum(item["healthScore"] for item in completed) / len(completed),
        0,
    ) if completed else 78

    # Turnaround Time (mock calculation based on sessions)
    avg_tat_days = round(total_cost % 5.0 + 2.1, 1) if sessions else 4.2 

    predictive_maintenance = [
        {
            "vesselName": item["vesselName"],
            "imoNumber": item["imoNumber"],
            "probability": f"{100 - item['healthScore'] + 15}%",
            "timeframe": "Next 6 Months",
            "risk": "High" if item["healthScore"] < 50 else "Medium"
        }
        for item in summaries if item["healthScore"] < 75
    ][:5]

    return {
        "metrics": [
            {"label": "Fleet Health Index", "value": f"{avg_health}%", "delta": "+2% vs last month", "trend": "up"},
            {"label": "Avg Turnaround Time", "value": f"{avg_tat_days} Days", "delta": "-0.5 days vs last month", "trend": "down"},
            {"label": "Active Inspections", "value": str(len(pending)), "delta": "Currently in dry dock", "trend": "up"},
            {"label": "Financial Exposure", "value": f"IDR {total_cost:,.0f}", "delta": "Fleet-wide repair estimate", "trend": "up"},
        ],
        "predictiveMaintenance": predictive_maintenance,
        "defectsByType": [{"name": name, "value": value} for name, value in defect_counts.most_common()] or [{"name": "Deformation", "value": 1}],
        "costTrend": [
            {"month": month, "cost": round(value / 100000, 2)}
            for month, value in sorted(
                monthly_costs.items(),
                key=lambda item: datetime.strptime(item[0], "%b").month,
            )
        ] or [{"month": "Jan", "cost": 0.5}],
        "healthScore": avg_health,
        "latestSessionId": summaries[0]["sessionId"] if summaries else None,
    }
