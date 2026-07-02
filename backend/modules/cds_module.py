import os
import cv2
import time
import torch
import numpy as np

from ultralytics import YOLO
from collections import defaultdict


class CDSModule:

    def __init__(

        self,

        classification_model_path,
        part_segmentation_model_path,
        defect_segmentation_model_path,

        tracker="botsort.yaml",

        device=None,

        temporal_nms_iou=0.7
    ):

        self.device = device or (
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        self.tracker = tracker

        self.temporal_nms_iou = temporal_nms_iou

        # =====================================================
        # LOAD MODELS
        # =====================================================

        self.classification_model = YOLO(
            classification_model_path
        )

        self.part_segmentation_model = YOLO(
            part_segmentation_model_path
        )

        self.defect_segmentation_model = YOLO(
            defect_segmentation_model_path
        )

        # =====================================================
        # TEMPORAL TRACK MEMORY
        # =====================================================

        self.track_first_seen = {}
        self.track_frequency = defaultdict(int)

    # =========================================================
    # CLASSIFICATION
    # =========================================================

    def classify_frame(self, frame):

        results = self.classification_model(frame)

        if len(results) == 0:
            return None

        r = results[0]

        class_id = int(r.probs.top1)

        return {
            "class_id": class_id,
            "class_name": r.names[class_id],
            "confidence": float(r.probs.top1conf)
        }

    # =========================================================
    # IOU
    # =========================================================

    def compute_iou(self, box1, box2):

        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])

        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        inter = max(0, x2 - x1) * max(0, y2 - y1)

        area1 = (
            (box1[2] - box1[0]) *
            (box1[3] - box1[1])
        )

        area2 = (
            (box2[2] - box2[0]) *
            (box2[3] - box2[1])
        )

        union = area1 + area2 - inter

        if union <= 0:
            return 0

        return inter / union

    # =========================================================
    # TEMPORAL STABLE NMS
    # =========================================================

    def temporal_stable_nms(self, result, frame_index):

        if result.boxes is None:
            return []

        boxes = result.boxes.xyxy.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy().astype(int)

        if result.boxes.id is not None:
            track_ids = (
                result.boxes.id
                .cpu()
                .numpy()
                .astype(int)
            )
        else:
            track_ids = np.arange(len(boxes))

        detections = []

        for i in range(len(boxes)):

            track_id = int(track_ids[i])

            self.track_frequency[track_id] += 1

            if track_id not in self.track_first_seen:
                self.track_first_seen[track_id] = frame_index

            detections.append({

                "box": boxes[i].tolist(),

                "confidence": float(confs[i]),

                "class_id": int(classes[i]),

                "track_id": track_id,

                "mask_index": i,

                "first_seen":
                    self.track_first_seen[track_id],

                "track_frequency":
                    self.track_frequency[track_id]
            })

        # =====================================================
        # SORT TEMPORALLY
        # =====================================================

        detections.sort(

            key=lambda d: (

                d["first_seen"],

                -d["track_frequency"],

                -d["confidence"]
            )
        )

        keep = []
        removed = set()

        for i, det_a in enumerate(detections):

            if i in removed:
                continue

            keep.append(det_a)

            for j, det_b in enumerate(detections):

                if i == j:
                    continue

                if j in removed:
                    continue

                if det_a["class_id"] != det_b["class_id"]:
                    continue

                iou = self.compute_iou(
                    det_a["box"],
                    det_b["box"]
                )

                if iou > self.temporal_nms_iou:
                    removed.add(j)

        return keep

    # =========================================================
    # PARSE YOLO SEGMENTATION OUTPUT
    # =========================================================

    def parse_segmentation_results(

        self,
        result,
        filtered_detections
    ):

        parsed = []

        polygons = None

        if result.masks is not None:
            polygons = result.masks.xy

        for det in filtered_detections:

            mask_polygon = None

            if polygons is not None:

                mask_index = det["mask_index"]

                if mask_index < len(polygons):

                    mask_polygon = (
                        polygons[mask_index]
                        .astype(np.int32)
                        .tolist()
                    )

            parsed.append({

                "track_id": det["track_id"],

                "class_id": det["class_id"],

                "class_name":
                    result.names[det["class_id"]],

                "confidence":
                    det["confidence"],

                "bbox":
                    det["box"],

                "segmentation":
                    mask_polygon
            })

        return parsed
    
    
    def generate_color(self, class_id):

        np.random.seed(class_id)

        color = np.random.randint(
            0,
            255,
            size=3
        )

        return (
            int(color[0]),
            int(color[1]),
            int(color[2])
        )

    # =========================================================
    # PROCESS VIDEO FRAMES
    # =========================================================

    def run_classification(self, frames):
        outputs = []
        for frame_data in frames:
            frame = cv2.imread(frame_data["frame_path"])
            if frame is None:
                continue
            print(f"[INFO] Running Classification on Frame: {frame_data['frame_id']}")
            classification = self.classify_frame(frame)
            outputs.append({
                "frame_id": frame_data["frame_id"],
                "timestamp": frame_data["timestamp"],
                "frame_path": frame_data["frame_path"],
                "classification": classification
            })
        return outputs

    def run_part_detection(self, frames, human_classifications):
        outputs = []
        class_map = {item["frame_id"]: item.get("classification") for item in human_classifications}
        frame_index = 0
        for frame_data in frames:
            frame_id = frame_data["frame_id"]
            frame = cv2.imread(frame_data["frame_path"])
            if frame is None:
                continue
            print(f"[INFO] Running Part Detection on Frame: {frame_index}")
            
            part_results = self.part_segmentation_model.track(source=frame, persist=True, tracker=self.tracker, verbose=False, imgsz=320)[0]
            filtered_parts = self.temporal_stable_nms(part_results, frame_index)
            parsed_parts = self.parse_segmentation_results(part_results, filtered_parts)

            outputs.append({
                "frame_id": frame_id,
                "timestamp": frame_data["timestamp"],
                "frame_path": frame_data["frame_path"],
                "classification": class_map.get(frame_id),
                "part_detections": parsed_parts,
                "defect_detections": []
            })
            frame_index += 1
        return outputs

    def run_defect_detection(self, frames, human_part_detections):
        outputs = []
        frame_index = 0
        for frame_data, item in zip(frames, human_part_detections):
            frame_id = item["frame_id"]
            frame = cv2.imread(item["frame_path"])
            if frame is None:
                continue
            print(f"[INFO] Running Defect Detection on Frame: {frame_index}")

            defect_results = self.defect_segmentation_model.track(source=frame, persist=True, tracker=self.tracker, verbose=False, imgsz=320)[0]
            filtered_defects = self.temporal_stable_nms(defect_results, frame_index)
            parsed_defects = self.parse_segmentation_results(defect_results, filtered_defects)

            outputs.append({
                "frame_id": frame_id,
                "timestamp": item["timestamp"],
                "frame_path": item["frame_path"],
                "classification": item.get("classification"),
                "part_detections": item.get("part_detections", []),
                "defect_detections": parsed_defects
            })
            frame_index += 1
        return outputs

    def run_segmentation(self, frames, human_detections):
        outputs = []
        for item in human_detections:
            frame_id = item["frame_id"]
            frame = cv2.imread(item["frame_path"])
            if frame is None:
                continue
            print(f"[INFO] Running Segmentation on Frame: {frame_id}")

            part_results = self.part_segmentation_model(frame, verbose=False, imgsz=320)[0]
            defect_results = self.defect_segmentation_model(frame, verbose=False, imgsz=320)[0]

            def map_masks_to_boxes(boxes, yolo_result):
                if not boxes: return boxes
                if yolo_result.masks is None or yolo_result.boxes is None:
                    return boxes
                
                yolo_boxes = yolo_result.boxes.xyxy.cpu().numpy()
                polygons = yolo_result.masks.xy
                
                mapped_boxes = []
                for box_item in boxes:
                    human_box = box_item["bbox"]
                    best_iou = 0
                    best_mask = None
                    for i, yb in enumerate(yolo_boxes):
                        iou = self.compute_iou(human_box, yb)
                        if iou > best_iou and iou > 0.3:
                            best_iou = iou
                            if i < len(polygons):
                                best_mask = polygons[i].astype(np.int32).tolist()
                    box_copy = box_item.copy()
                    if box_copy.get("segmentation") is None and best_mask is not None:
                        box_copy["segmentation"] = best_mask
                    
                    mapped_boxes.append(box_copy)
                return mapped_boxes

            part_detections_with_masks = map_masks_to_boxes(item.get("part_detections", []), part_results)
            defect_detections_with_masks = map_masks_to_boxes(item.get("defect_detections", []), defect_results)

            outputs.append({
                "frame_id": frame_id,
                "timestamp": item["timestamp"],
                "frame_path": item["frame_path"],
                "classification": item.get("classification"),
                "part_detections": part_detections_with_masks,
                "defect_detections": defect_detections_with_masks
            })
        return outputs


# =============================================================
# TESTING