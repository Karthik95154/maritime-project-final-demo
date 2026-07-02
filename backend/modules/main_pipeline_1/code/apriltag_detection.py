"""AprilTag detection and scale estimation for main_pipeline_1."""

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from image_io import PipelineImage


def detect_apriltag_scale(
    images: list[PipelineImage],
    config: dict[str, Any],
    output_dir: str | Path,
) -> list[dict[str, Any]]:
    """Detect AprilTags and estimate image scale."""
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    if not images:
        _write_json(output_path / "apriltag_scale_results.json", [])
        return []

    apriltag_config = config["apriltag"]
    tag_options = _load_tag_options(apriltag_config)
    detector = _create_detector(str(apriltag_config["tag_family"]))
    results: list[dict[str, Any]] = []
    for image in images:
        gray_image = cv2.cvtColor(image.image, cv2.COLOR_BGR2GRAY)
        detections = detector.detect(gray_image)
        result = _build_detection_result(
            image_name=image.name,
            detections=detections,
            configured_tag_family=str(apriltag_config["tag_family"]),
            tag_options=tag_options,
            selection_policy=str(apriltag_config.get("selection_policy", "config_priority")),
        )
        results.append(result)
        cv2.imwrite(
            str(output_path / f"{image.path.stem}_apriltag_overlay.jpg"),
            _render_overlay(image.image, result),
        )

    _write_json(output_path / "apriltag_scale_results.json", results)
    print(f"main_pipeline_1 AprilTag processed images: {len(images)}")
    print(f"main_pipeline_1 AprilTag detected: {sum(1 for result in results if result['apriltag_detected'])}")
    return results


def _create_detector(tag_family: str) -> Any:
    try:
        from pupil_apriltags import Detector
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("pupil-apriltags is required for AprilTag detection.") from exc
    return Detector(families=tag_family)


def _build_detection_result(
    image_name: str,
    detections: list[Any],
    configured_tag_family: str,
    tag_options: list[dict[str, Any]],
    selection_policy: str,
) -> dict[str, Any]:
    selected = _select_detection(detections, tag_options)
    detected_tag_ids = _detected_tag_ids(detections)
    configured_tag_ids = [int(option["tag_id"]) for option in tag_options]
    default_tag_size_mm = float(tag_options[0]["tag_size_mm"]) if tag_options else None
    detection = selected["detection"] if selected else None
    tag_option = selected["tag_option"] if selected else None
    if detection is None:
        return {
            "image_name": image_name,
            "apriltag_detected": False,
            "tag_family": configured_tag_family,
            "tag_id": None,
            "tag_label": None,
            "corners": [],
            "tag_pixel_size_avg": None,
            "tag_real_size_mm": default_tag_size_mm,
            "scale_mm_per_pixel": None,
            "configured_tag_ids": configured_tag_ids,
            "detected_tag_ids": detected_tag_ids,
            "selection_policy": selection_policy,
            "selected_by": None,
            "selection_status": "no_configured_apriltag_detected",
        }

    tag_family = detection.tag_family
    if isinstance(tag_family, bytes):
        tag_family = tag_family.decode("utf-8")
    tag_pixel_size_avg = _average_side_length(detection.corners)
    tag_size_mm = float(tag_option["tag_size_mm"])
    return {
        "image_name": image_name,
        "apriltag_detected": True,
        "tag_family": str(tag_family),
        "tag_id": int(detection.tag_id),
        "tag_label": tag_option.get("label"),
        "corners": _round_points(detection.corners),
        "tag_pixel_size_avg": round(float(tag_pixel_size_avg), 4),
        "tag_real_size_mm": float(tag_size_mm),
        "scale_mm_per_pixel": round(float(tag_size_mm / tag_pixel_size_avg), 8),
        "configured_tag_ids": configured_tag_ids,
        "detected_tag_ids": detected_tag_ids,
        "selection_policy": selection_policy,
        "selected_by": "config_priority",
        "selection_status": "configured_apriltag_selected",
    }


def _load_tag_options(apriltag_config: dict[str, Any]) -> list[dict[str, Any]]:
    tag_options = apriltag_config.get("tag_options")
    if isinstance(tag_options, list):
        return [
            {
                "tag_id": int(option["tag_id"]),
                "tag_size_mm": float(option["tag_size_mm"]),
                "label": option.get("label"),
                "enabled": bool(option.get("enabled", True)),
            }
            for option in tag_options
            if isinstance(option, dict) and bool(option.get("enabled", True))
        ]

    return [
        {
            "tag_id": int(apriltag_config["tag_id"]),
            "tag_size_mm": float(apriltag_config["tag_size_mm"]),
            "label": apriltag_config.get("tag_label"),
            "enabled": True,
        }
    ]


def _select_detection(detections: list[Any], tag_options: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not detections:
        return None
    detections_by_id = {int(detection.tag_id): detection for detection in detections}
    for tag_option in tag_options:
        detection = detections_by_id.get(int(tag_option["tag_id"]))
        if detection is not None:
            return {"detection": detection, "tag_option": tag_option}
    return None


def _detected_tag_ids(detections: list[Any]) -> list[int]:
    return sorted({int(detection.tag_id) for detection in detections})


def _average_side_length(corners: np.ndarray) -> float:
    side_lengths = [
        float(np.linalg.norm(corners[index] - corners[(index + 1) % 4]))
        for index in range(4)
    ]
    return float(np.mean(side_lengths))


def _render_overlay(image: np.ndarray, result: dict[str, Any]) -> np.ndarray:
    overlay = image.copy()
    if not result["apriltag_detected"]:
        cv2.putText(
            overlay,
            "AprilTag: not detected",
            (20, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
        return overlay

    corners = np.array(result["corners"], dtype=np.int32)
    cv2.polylines(overlay, [corners], True, (0, 255, 0), 2)
    label = f"AprilTag ID {result['tag_id']} | {result['scale_mm_per_pixel']:.4f} mm/px"
    cv2.putText(
        overlay,
        label,
        tuple(corners[0] + np.array([0, -12])),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )
    return overlay


def _round_points(points: np.ndarray) -> list[list[float]]:
    return [[round(float(point[0]), 2), round(float(point[1]), 2)] for point in points]


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as json_file:
        json.dump(data, json_file, indent=2)
