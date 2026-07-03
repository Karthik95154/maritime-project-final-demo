import json
import os
import traceback
from collections import Counter

from loguru import logger

from database import get_db
from modules.cds_module import CDSModule
from modules.document_generation_module import DocumentGenerationModule
from modules.frame_extraction_module import FrameExtractionModule
from modules.repair_estimation_module import RepairEstimationModule
from modules.temporal_consistency_module import TemporalConsistencyModule
from modules.unique_defect_frame_extraction_module import UniqueDefectFrameExtractor
from session_manager import update_session

import tempfile
from contextlib import contextmanager

@contextmanager
def temp_json(data):
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    try:
        yield path
    finally:
        if os.path.exists(path):
            os.remove(path)


def save_json(data, arg2, arg3=None):
    if arg3 is None:
        path = arg2
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)
    else:
        session_id = arg2
        stage_key = arg3
        from services.storage import storage_backend
        storage_backend.save_json(session_id, stage_key, data)


def load_json(arg1, arg2=None):
    if arg2 is None:
        path = arg1
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    else:
        session_id = arg1
        stage_key = arg2
        from services.storage import storage_backend
        data = storage_backend.load_json(session_id, stage_key)
        return data if data is not None else []


async def _session_doc(session_id):
    db = get_db()
    return await db.inspection_sessions.find_one({"session_id": session_id})


def _paths(session_folder):
    return {
        "frame_json": os.path.join(session_folder, "module_1_frame_extraction_output", "extracted_frames.json"),
        "classification_ai_json": os.path.join(session_folder, "module_2_classification_output", "classification_ai.json"),
        "classification_human_json": os.path.join(session_folder, "module_2_classification_output", "classification_human.json"),
        "part_detection_ai_json": os.path.join(session_folder, "module_3_part_detection_output", "part_detection_ai.json"),
        "part_detection_human_json": os.path.join(session_folder, "module_3_part_detection_output", "part_detection_human.json"),
        "defect_detection_ai_json": os.path.join(session_folder, "module_3b_defect_detection_output", "defect_detection_ai.json"),
        "defect_detection_human_json": os.path.join(session_folder, "module_3b_defect_detection_output", "defect_detection_human.json"),
        "segmentation_ai_json": os.path.join(session_folder, "module_4_segmentation_output", "segmentation_ai.json"),
        "segmentation_human_json": os.path.join(session_folder, "module_4_segmentation_output", "segmentation_human.json"),
        "temporal_json": os.path.join(session_folder, "module_5_temporal_output", "temporally_stable_outputs.json"),
        "unique_json": os.path.join(session_folder, "module_6_unique_defect_frame_output", "unique_defect_outputs.json"),
        "area_human_json": os.path.join(session_folder, "module_6_unique_defect_frame_output", "area_human_outputs.json"),
        "repair_ai_json": os.path.join(session_folder, "module_7_repair_estimation_output", "repair_estimation_ai.json"),
        "repair_human_json": os.path.join(session_folder, "module_7_repair_estimation_output", "repair_estimation_human.json"),
        "report_ai_json": os.path.join(session_folder, "module_8_report_generation_output", "report_ai.json"),
    }


def _pause_for_review(session_id, stage_name, checkpoint_name, resume_from):
    logger.info(f"[{session_id}] Human review required for stage: {stage_name}")
    update_session(
        session_id,
        status="awaiting_review",
        current_stage=f"Awaiting {stage_name} Review",
        review_checkpoint=checkpoint_name,
        review_status="pending",
        pipeline_resume_from=resume_from,
    )


def _frame_extraction(session_id, session_folder, video_paths, previous_frame_jsons=None):
    update_session(session_id, progress=5, status="processing", current_stage="Frame Extraction")
    module_1_output = os.path.join(session_folder, "module_1_frame_extraction_output")
    os.makedirs(module_1_output, exist_ok=True)

    all_frames = []
    global_frame_id = 0

    # Do not append previous_frame_jsons into the current session frames
    # as this causes old images to show up in the current HITL queue
    # and re-processes already analyzed data.
    if previous_frame_jsons:
        logger.info(f"[{session_id}] Ignoring {len(previous_frame_jsons)} previous frame JSONs to prevent mixing sessions.")

    for index, video_path in enumerate(video_paths):
        output_dir = module_1_output if len(video_paths) == 1 else os.path.join(module_1_output, f"video_{index}")
        os.makedirs(output_dir, exist_ok=True)
        extractor = FrameExtractionModule(
            output_dir=output_dir,
            frame_skip=5,
            blur_threshold=200,
            similarity_threshold=0.92,
            memory_size=20,
        )
        extracted_frames = extractor.process_video(video_path)
        for frame in extracted_frames:
            copied = frame.copy()
            copied["frame_id"] = global_frame_id
            all_frames.append(copied)
            global_frame_id += 1

    save_json(all_frames, session_id, "frame_json")
    logger.info(f"[{session_id}] Frame Extraction Completed. Total Frames: {len(all_frames)}")
    return all_frames


def run_classification_stage(session_id, session_folder, extracted_frames):
    update_session(session_id, progress=15, current_stage="Classification AI")
    paths = _paths(session_folder)
    
    cds_module = CDSModule(
        classification_model_path="final_models/yolo26m_classification_best.pt",
        part_segmentation_model_path="final_models/yolo26m_part_seg_best.pt",
        defect_segmentation_model_path="final_models/yolo_seg_deformation_best.pt",
        tracker="botsort.yaml",
    )
    classification_outputs = cds_module.run_classification(extracted_frames)
    save_json(classification_outputs, session_id, "classification_ai_json")
    
    # Pause for Classification HITL
    _pause_for_review(session_id, "Classification", "classification_review", "run_part_detection_stage")


def run_part_detection_stage(session_id, session_folder):
    update_session(session_id, progress=30, status="processing", current_stage="Part Detection AI")
    paths = _paths(session_folder)
    
    frames = load_json(session_id, "frame_json")
    human_classifications = load_json(session_id, "classification_human_json")
    
    cds_module = CDSModule(
        classification_model_path="final_models/yolo26m_classification_best.pt",
        part_segmentation_model_path="final_models/yolo26m_part_seg_best.pt",
        defect_segmentation_model_path="final_models/yolo_seg_deformation_best.pt",
        tracker="botsort.yaml",
    )
    detection_outputs = cds_module.run_part_detection(frames, human_classifications)
    save_json(detection_outputs, session_id, "part_detection_ai_json")
    
    # Pause for Part Detection HITL
    _pause_for_review(session_id, "Part Detection", "part_detection_review", "run_defect_detection_stage")


def run_defect_detection_stage(session_id, session_folder):
    update_session(session_id, progress=35, status="processing", current_stage="Defect Detection AI")
    paths = _paths(session_folder)
    
    frames = load_json(session_id, "frame_json")
    human_part_detections = load_json(session_id, "part_detection_human_json")
    
    cds_module = CDSModule(
        classification_model_path="final_models/yolo26m_classification_best.pt",
        part_segmentation_model_path="final_models/yolo26m_part_seg_best.pt",
        defect_segmentation_model_path="final_models/yolo_seg_deformation_best.pt",
        tracker="botsort.yaml",
    )
    detection_outputs = cds_module.run_defect_detection(frames, human_part_detections)
    save_json(detection_outputs, session_id, "defect_detection_ai_json")
    
    # Pause for Defect Detection HITL
    _pause_for_review(session_id, "Defect Detection", "defect_detection_review", "run_segmentation_stage")


def run_segmentation_stage(session_id, session_folder):
    update_session(session_id, progress=45, status="processing", current_stage="Segmentation AI")
    paths = _paths(session_folder)
    
    frames = load_json(session_id, "frame_json")
    human_detections = load_json(session_id, "defect_detection_human_json")
    
    cds_module = CDSModule(
        classification_model_path="final_models/yolo26m_classification_best.pt",
        part_segmentation_model_path="final_models/yolo26m_part_seg_best.pt",
        defect_segmentation_model_path="final_models/yolo_seg_deformation_best.pt",
        tracker="botsort.yaml",
    )
    segmentation_outputs = cds_module.run_segmentation(frames, human_detections)
    save_json(segmentation_outputs, session_id, "segmentation_ai_json")
    
    # Skip Segmentation HITL and proceed directly
    run_area_estimation_stage(session_id, session_folder)


def run_area_estimation_stage(session_id, session_folder):
    update_session(session_id, progress=60, status="processing", current_stage="Temporal Consistency & Area Estimation")
    paths = _paths(session_folder)
    
    # Sync DB data to disk for the modules that expect a local file path
    seg_human = load_json(session_id, "segmentation_human_json")
    if not seg_human:
        seg_human = load_json(session_id, "segmentation_ai_json")
    save_json(seg_human, paths["segmentation_human_json"])
    
    # Run Temporal Consistency on the human-approved segmentations
    os.makedirs(os.path.dirname(paths["temporal_json"]), exist_ok=True)
    temporal_module = TemporalConsistencyModule(
        clip_similarity_threshold=0.88,
        iou_threshold=0.35,
        area_similarity_threshold=0.60,
        association_threshold=0.70,
    )
    temporal_module.process(paths["segmentation_human_json"], paths["temporal_json"])
    
    # Run Unique Defect Extraction
    os.makedirs(os.path.dirname(paths["unique_json"]), exist_ok=True)
    unique_defect_module = UniqueDefectFrameExtractor(
        defect_area_default=5,
        defect_area_metrics="sq.m",
        overlap_threshold=0.01,
    )
    unique_outputs = unique_defect_module.process(paths["temporal_json"], paths["unique_json"])

    # ========================================================
    # AREA ESTIMATION (main_pipeline_1 Integration)
    # ========================================================
    import sys
    import cv2
    from utils.image import load_image
    from pathlib import Path
    
    mp1_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "modules", "main_pipeline_1", "code"))
    if mp1_path not in sys.path:
        sys.path.insert(0, mp1_path)
        
    saved_config = sys.modules.pop("config", None)
        
    try:
        from image_io import PipelineImage
        from apriltag_detection import detect_apriltag_scale
        from homography import compute_full_image_homography
        from area_estimation import calculate_rectified_damage_areas
        from config import load_main_pipeline_config
    finally:
        if sys.path and sys.path[0] == mp1_path:
            sys.path.pop(0)
        sys.modules.pop("config", None)
        if saved_config:
            sys.modules["config"] = saved_config

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    config_path = os.path.join(os.path.dirname(__file__), "modules", "main_pipeline_1", "config", "main_pipeline_1_config.yaml")
    config = load_main_pipeline_config(config_path)

    images = []
    damage_results = []
    
    for persistent_id, defect_data in unique_outputs.items():
        best_frame_path = defect_data["best_frame_path"]
        loaded = next((img for img in images if img.path.as_posix() == Path(best_frame_path).as_posix()), None)
        
        if not loaded:
            img_mat = load_image(best_frame_path)
            if img_mat is not None:
                loaded = PipelineImage(name=Path(best_frame_path).name, path=Path(best_frame_path), image=img_mat)
                images.append(loaded)
        
        if loaded:
            img_dr = next((dr for dr in damage_results if dr["image_name"] == loaded.name), None)
            if not img_dr:
                img_dr = {"image_name": loaded.name, "damages": []}
                damage_results.append(img_dr)
            
            img_dr["damages"].append({
                "damage_id": persistent_id,
                "class_name": defect_data.get("defect_name", "unknown"),
                "bbox": defect_data.get("bbox", []),
                "source": "unique_defect_frame_extraction",
                "segmentation": defect_data.get("segmentation")
            })

    debug_dir = Path(session_folder) / "module_6_area_estimation_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    if images:
        apriltag_results = detect_apriltag_scale(
            images=images,
            config=config,
            output_dir=debug_dir / "apriltag_detection",
        )
        homography_results = compute_full_image_homography(
            images=images,
            damage_results=damage_results,
            apriltag_results=apriltag_results,
            output_dir=debug_dir / "homography",
            config=config,
            project_root=Path(project_root),
        )
        area_results = calculate_rectified_damage_areas(
            homography_results=homography_results,
            output_dir=debug_dir / "area_estimation",
        )
        
        for area_res in area_results:
            pid = str(area_res.get("damage_id"))
            if pid in unique_outputs:
                if area_res.get("area_m2") is not None:
                    unique_outputs[pid]["defect_area"] = float(area_res["area_m2"])
                    unique_outputs[pid]["area_metrics"] = "sq.m"
                    unique_outputs[pid]["area_status"] = area_res.get("status")
                else:
                    unique_outputs[pid]["area_status"] = area_res.get("status", "failed")

    save_json(unique_outputs, session_id, "unique_json")

    _pause_for_review(session_id, "Area", "area_review", "run_cost_estimation_stage")


def run_cost_estimation_stage(session_id, session_folder):
    update_session(session_id, progress=75, status="processing", current_stage="Cost Estimation AI")
    paths = _paths(session_folder)
    
    human_areas_data = load_json(session_id, "area_human_json")
    if not human_areas_data:
        human_areas_data = load_json(session_id, "unique_json")
    repair_module = RepairEstimationModule(
        knowledge_folder="repair_process_docs",
        currency="INR",
    )
    with temp_json(human_areas_data) as in_path, temp_json({}) as out_path:
        repair_module.process(
            unique_defect_json_path=in_path,
            output_json_path=out_path,
        )
        with open(out_path, 'r') as f:
            repair_out = json.load(f)
        save_json(repair_out, session_id, "repair_ai_json")
    
    _pause_for_review(session_id, "Cost Estimation", "cost_review", "run_report_generation_stage")


def run_report_generation_stage(session_id, session_folder):
    update_session(session_id, progress=90, status="processing", current_stage="Report Generation")
    paths = _paths(session_folder)
    
    human_cost_data = load_json(session_id, "repair_human_json")
    if not human_cost_data:
        human_cost_data = load_json(session_id, "repair_ai_json")
    
    try:
        from session_manager import sync_db
        analysis_doc = sync_db.analysis_sessions.find_one({"session_id": session_id})
        visit_id = analysis_doc.get("visit_id") if analysis_doc else None
        from modules.defect_matching_engine import DefectMatchingEngine

        with temp_json(human_cost_data) as in_path:
            DefectMatchingEngine(db=sync_db).process_session(session_id, in_path, visit_id=visit_id)
    except Exception as exc:
        logger.error(f"[{session_id}] Defect Matching Failed: {exc}")

    module_8_output = os.path.join(session_folder, "module_8_report_generation_output")
    os.makedirs(module_8_output, exist_ok=True)
    with temp_json(human_cost_data) as in_path:
        report_urls = DocumentGenerationModule(
            gemini_model_name="gemini-2.5-flash",
            output_folder=module_8_output,
        ).create_report(repair_estimation_json_path=in_path)
    
    save_json({"document_path": report_urls.get("document_pdf_url", report_urls.get("document_docx_url"))}, session_id, "report_ai_json")
    
    update_session(
        session_id, 
        progress=100, 
        status="completed", 
        current_stage="Completed", 
        review_checkpoint="completed", 
        review_status="approved", 
        pipeline_resume_from="completed",
        document_path=report_urls.get("document_pdf_url"),
        document_pdf_url=report_urls.get("document_pdf_url"),
        document_docx_url=report_urls.get("document_docx_url")
    )


async def run_pipeline(session_id, video_path, session_folder):
    try:
        logger.info(f"[{session_id}] Pipeline Started")
        frames = _frame_extraction(session_id, session_folder, [video_path])
        run_classification_stage(session_id, session_folder, frames)
    except Exception as exc:
        logger.error(f"[{session_id}] Pipeline Failed")
        logger.error(str(exc))
        logger.error(traceback.format_exc())
        update_session(session_id, status="failed", current_stage="Failed")


async def run_batch_pipeline(session_id, video_paths, session_folder, previous_frame_jsons):
    try:
        logger.info(f"[{session_id}] Batch Pipeline Started")
        frames = _frame_extraction(session_id, session_folder, video_paths, previous_frame_jsons)
        run_classification_stage(session_id, session_folder, frames)
    except Exception as exc:
        logger.error(f"[{session_id}] Batch Pipeline Failed")
        logger.error(str(exc))
        logger.error(traceback.format_exc())
        update_session(session_id, status="failed", current_stage="Failed")


async def resume_pipeline(session_id):
    session_doc = await _session_doc(session_id)
    if not session_doc:
        raise ValueError("Session not found")

    session_folder = session_doc.get("output_path")
    resume_from = session_doc.get("pipeline_resume_from")
    if not session_folder or not resume_from:
        raise ValueError("Session is missing resume information")

    try:
        if resume_from == "run_part_detection_stage":
            run_part_detection_stage(session_id, session_folder)
        elif resume_from == "run_defect_detection_stage":
            run_defect_detection_stage(session_id, session_folder)
        elif resume_from == "run_segmentation_stage":
            run_segmentation_stage(session_id, session_folder)
        elif resume_from == "run_area_estimation_stage":
            run_area_estimation_stage(session_id, session_folder)
        elif resume_from == "run_cost_estimation_stage":
            run_cost_estimation_stage(session_id, session_folder)
        elif resume_from == "run_report_generation_stage":
            run_report_generation_stage(session_id, session_folder)
        elif resume_from == "completed":
            paths = _paths(session_folder)
            report_ai = load_json(session_id, "report_ai_json")
            update_session(
                session_id,
                progress=100,
                status="completed",
                current_stage="Completed",
                document_path=report_ai.get("document_path"),
                review_checkpoint="completed",
                review_status="approved",
                pipeline_resume_from="completed",
            )
        else:
            logger.info(f"[{session_id}] No resume action required for {resume_from}")
    except Exception as exc:
        logger.error(f"[{session_id}] Pipeline Resume Failed at {resume_from}")
        logger.error(str(exc))
        logger.error(traceback.format_exc())
        update_session(session_id, status="failed", current_stage="Failed")

def recalculate_area_with_manual_homography(session_folder, defect_id, homography_points, image_name):
    """Recalculates area for a single defect using manual homography points."""
    import sys
    import cv2
    from utils.image import load_image
    from pathlib import Path

    paths = _paths(session_folder)
    session_id = os.path.basename(os.path.normpath(session_folder))
    
    # Write manual values to the main_pipeline_1 data folder so it gets picked up
    mp1_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "main_pipeline_1", "main_pipeline_1"))
    manual_dir = os.path.join(mp1_root, "data", "manual_image_values")
    os.makedirs(manual_dir, exist_ok=True)
    
    manual_json_path = os.path.join(manual_dir, f"{image_name}.json")
    with open(manual_json_path, 'w') as f:
        json.dump({
            "image_name": image_name,
            "manual_homography_plane_points": homography_points
        }, f)
    
    # Now load the unique_json or human_area_json to get the defect
    outputs = load_json(session_id, "area_human_json")
    if not outputs:
        outputs = load_json(session_id, "unique_json")
        
    defect_data = outputs.get(defect_id)
    if not defect_data:
        return None
        
    best_frame_path = defect_data["best_frame_path"]
    
    mp1_path = os.path.join(os.path.dirname(__file__), "modules", "main_pipeline_1", "code")
    if mp1_path not in sys.path:
        sys.path.insert(0, mp1_path)
        
    saved_config = sys.modules.pop("config", None)
        
    try:
        from image_io import PipelineImage
        from apriltag_detection import detect_apriltag_scale
        from homography import compute_full_image_homography
        from area_estimation import calculate_rectified_damage_areas
        from config import load_main_pipeline_config
    finally:
        if sys.path and sys.path[0] == mp1_path:
            sys.path.pop(0)
        sys.modules.pop("config", None)
        if saved_config:
            sys.modules["config"] = saved_config

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    config_path = os.path.join(os.path.dirname(__file__), "modules", "main_pipeline_1", "config", "main_pipeline_1_config.yaml")
    config = load_main_pipeline_config(config_path)

    if best_frame_path.startswith("http://") or best_frame_path.startswith("https://"):
        import urllib.request
        import numpy as np
        try:
            req = urllib.request.urlopen(best_frame_path)
            arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
            img_mat = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception as e:
            print(f"Failed to load image from URL: {e}")
            img_mat = None
    else:
        img_mat = cv2.imread(best_frame_path)
        
    if img_mat is None:
        return None
    loaded = PipelineImage(name=image_name, path=Path(best_frame_path), image=img_mat)
    
    damage_results = [{
        "image_name": image_name,
        "damages": [{
            "damage_id": defect_id,
            "class_name": defect_data.get("defect_name", "unknown"),
            "bbox": defect_data.get("bbox", []),
            "source": "unique_defect_frame_extraction",
            "segmentation": defect_data.get("segmentation")
        }]
    }]

    debug_dir = Path(session_folder) / "module_6_area_estimation_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    apriltag_results = detect_apriltag_scale([loaded], config=config, output_dir=debug_dir / "apriltag_detection")
    
    # Because we wrote the json, compute_full_image_homography should pick it up and use _manual_plane_homography
    homography_results = compute_full_image_homography(
        images=[loaded],
        damage_results=damage_results,
        apriltag_results=apriltag_results,
        output_dir=debug_dir / "homography",
        config=config,
        project_root=Path(project_root),
    )
    
    area_results = calculate_rectified_damage_areas(
        homography_results=homography_results,
        output_dir=debug_dir / "area_estimation",
    )
    
    if area_results:
        res = area_results[0]
        if res.get("area_m2") is not None:
            defect_data["defect_area"] = float(res["area_m2"])
            defect_data["area_metrics"] = "sq.m"
            defect_data["area_status"] = res.get("status")
        else:
            defect_data["area_status"] = res.get("status", "failed")
            
    outputs[defect_id] = defect_data
    save_json(outputs, session_id, "area_human_json")
    return outputs

