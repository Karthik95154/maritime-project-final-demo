"""Damage geometry resolution for main_pipeline_1."""

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from image_io import PipelineImage


BBOX_WARNING = "bbox_damage_geometry_used_area_is_approximate"


def resolve_damage_geometry(
    images: list[PipelineImage],
    config: dict[str, Any],
    project_root: Path,
) -> list[dict[str, Any]]:
    """Resolve damage geometry from automatic detection and manual/HITL inputs."""
    paths = config["paths"]
    damage_config = config["damage_resolution"]
    debug_dir = Path(paths["debug_dir"])
    hitl_required_dir = Path(paths["hitl_required_dir"])

    manual_inputs = _load_manual_damage_inputs(
        images=images,
        manual_values_dir=Path(paths["manual_img_values_dir"]),
        manual_polygon_dir=Path(paths["manual_damage_polygon_dir"]),
    )
    automatic_results: list[dict[str, Any]] = []
    if not bool(damage_config.get("force_damage_hitl", False)):
        automatic_results = _run_damage_segmentation(
            images=_images_requiring_auto_damage(
                images=images,
                manual_inputs=manual_inputs,
                priority=str(damage_config.get("input_priority", "auto_first")),
            ),
            model_path=Path(config["models"]["damage_segmentation_model_path"]),
            output_dir=debug_dir / "damage_segmentation",
            confidence_threshold=float(config["inference"]["damage_confidence_threshold"]),
        )

    return _resolve_damage_results(
        images=images,
        automatic_results=automatic_results,
        manual_inputs=manual_inputs,
        enable_damage_hitl=bool(damage_config.get("enable_damage_hitl", True)),
        force_damage_hitl=bool(damage_config.get("force_damage_hitl", False)),
        input_priority=str(damage_config.get("input_priority", "auto_first")),
        hitl_required_dir=hitl_required_dir,
    )


def write_damage_hitl_request(
    image_name: str,
    output_dir: str | Path,
    reason: str,
) -> str:
    """Write a manual damage correction request for one image."""
    resolved_output_dir = Path(output_dir).resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    output_path = resolved_output_dir / f"{Path(image_name).stem}_damage_hitl_request.json"
    request = {
        "pipeline_name": "main_pipeline_1",
        "image_name": image_name,
        "trigger_reason": reason,
        "required_user_action": "provide_or_correct_damage_polygon",
        "accepted_input_types": [
            "manual_damage_polygon",
            "labelstudio_polygon",
            "yolo_txt_segmentation",
            "yolo_txt_bbox",
        ],
    }
    _write_json(output_path, request)
    return str(output_path)


def _run_damage_segmentation(
    images: list[PipelineImage],
    model_path: Path,
    output_dir: Path,
    confidence_threshold: float,
) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not model_path.exists():
        raise FileNotFoundError(f"Damage segmentation model not found: {model_path.resolve()}")
    if not images:
        _write_json(output_dir / "damage_segmentation_results.json", [])
        return []

    try:
        from ultralytics import YOLO
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("Ultralytics is required for damage segmentation.") from exc

    model = YOLO(str(model_path.resolve()))
    results: list[dict[str, Any]] = []
    for loaded_image in images:
        prediction = model.predict(
            source=loaded_image.image,
            conf=confidence_threshold,
            verbose=False,
        )[0]
        image_result = _extract_damage_result(loaded_image.name, prediction)
        results.append(image_result)
        overlay = _render_damage_overlay(loaded_image.image, image_result["damages"])
        cv2.imwrite(str(output_dir / f"{loaded_image.path.stem}_damage_overlay.jpg"), overlay)

    _write_json(output_dir / "damage_segmentation_results.json", results)
    return results


def _extract_damage_result(image_name: str, prediction: Any) -> dict[str, Any]:
    boxes = prediction.boxes
    masks = prediction.masks
    damages: list[dict[str, Any]] = []
    if boxes is None or len(boxes) == 0:
        return {"image_name": image_name, "damages": damages}

    names = prediction.names
    xyxy_values = boxes.xyxy.cpu().numpy()
    confidence_values = boxes.conf.cpu().numpy()
    class_values = boxes.cls.cpu().numpy().astype(int)
    mask_arrays = _extract_mask_arrays(masks)
    mask_polygons = _extract_mask_polygons(masks)

    for index, (bbox_xyxy, confidence, class_id) in enumerate(
        zip(xyxy_values, confidence_values, class_values),
        start=1,
    ):
        mask_index = index - 1
        polygon_points = mask_polygons[mask_index] if mask_index < len(mask_polygons) else []
        mask_pixel_area = (
            int(np.count_nonzero(mask_arrays[mask_index]))
            if mask_index < len(mask_arrays)
            else 0
        )
        damages.append(
            {
                "damage_id": f"auto_{index}",
                "class_id": int(class_id),
                "class_name": str(names.get(int(class_id), int(class_id))),
                "confidence": round(float(confidence), 4),
                "bbox_xyxy": [round(float(value), 2) for value in bbox_xyxy.tolist()],
                "polygon_points": polygon_points,
                "mask_pixel_area": mask_pixel_area,
                "source": "automatic_damage_segmentation",
                "warnings": [],
            }
        )
    return {"image_name": image_name, "damages": damages}


def _load_manual_damage_inputs(
    images: list[PipelineImage],
    manual_values_dir: Path,
    manual_polygon_dir: Path,
) -> dict[str, list[dict[str, Any]]]:
    manual_inputs = {image.name: [] for image in images}
    if manual_values_dir.exists():
        _load_manual_damage_dir(manual_inputs, manual_values_dir)
    if manual_polygon_dir.exists():
        _load_manual_damage_dir(manual_inputs, manual_polygon_dir)
    return manual_inputs


def _load_manual_damage_dir(
    manual_inputs: dict[str, list[dict[str, Any]]],
    manual_dir: Path,
) -> None:
    for path in manual_dir.glob("*.json"):
        image_name = _image_name_from_stem(manual_inputs, path.stem)
        if image_name is None:
            continue
        _append_manual_entries(manual_inputs[image_name], _safe_read_json(path))


def _append_manual_entries(target: list[dict[str, Any]], data: Any) -> None:
    entries = (
        data
        if isinstance(data, list)
        else data.get("manual_damage_polygons", [])
        if isinstance(data, dict)
        else []
    )
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            continue
        points = entry.get("points") or entry.get("manual_damage_polygon")
        if not _valid_polygon(points):
            continue
        target.append(
            {
                "damage_id": entry.get("damage_id", f"manual_{index}"),
                "class_name": entry.get("damage_class", "damage"),
                "confidence": None,
                "bbox_xyxy": _bbox_from_points(points),
                "polygon_points": _round_points(points),
                "mask_pixel_area": _polygon_area(points),
                "source": "manual_damage_polygon",
                "warnings": [],
            }
        )


def _images_requiring_auto_damage(
    images: list[PipelineImage],
    manual_inputs: dict[str, list[dict[str, Any]]],
    priority: str,
) -> list[PipelineImage]:
    if priority == "user_first":
        return [image for image in images if not manual_inputs.get(image.name)]
    return images


def _resolve_damage_results(
    images: list[PipelineImage],
    automatic_results: list[dict[str, Any]],
    manual_inputs: dict[str, list[dict[str, Any]]],
    enable_damage_hitl: bool,
    force_damage_hitl: bool,
    input_priority: str,
    hitl_required_dir: Path,
) -> list[dict[str, Any]]:
    auto_by_image = {result["image_name"]: result for result in automatic_results}
    resolved: list[dict[str, Any]] = []
    for image in images:
        manual_damages = manual_inputs.get(image.name, [])
        automatic_damages = _valid_auto_damages(
            auto_by_image.get(image.name, {"damages": []}).get("damages", [])
        )

        if input_priority == "user_first" and manual_damages:
            resolved.append(_damage_result(image.name, manual_damages, "manual_damage_polygon", True, False))
        elif not force_damage_hitl and automatic_damages:
            resolved.append(_damage_result(image.name, automatic_damages, "automatic_damage_segmentation", False, False))
        elif manual_damages:
            resolved.append(_damage_result(image.name, manual_damages, "manual_damage_polygon", True, False))
        elif not enable_damage_hitl:
            resolved.append(_missing_damage_result(image.name, hitl_required=False))
        else:
            request_path = write_damage_hitl_request(
                image_name=image.name,
                output_dir=hitl_required_dir,
                reason="damage_geometry_missing_or_invalid",
            )
            result = _missing_damage_result(image.name, hitl_required=True)
            result["damage_hitl_request_path"] = request_path
            resolved.append(result)
    return resolved


def _damage_result(
    image_name: str,
    damages: list[dict[str, Any]],
    source: str,
    hitl_used: bool,
    hitl_required: bool,
) -> dict[str, Any]:
    return {
        "image_name": image_name,
        "damages": damages,
        "damage_source": source,
        "damage_hitl_used": hitl_used,
        "damage_hitl_required": hitl_required,
        "warnings": _unique([warning for damage in damages for warning in damage.get("warnings", [])]),
        "failure_reason": None,
        "required_user_action": None,
        "damage_hitl_request_path": None,
    }


def _missing_damage_result(image_name: str, hitl_required: bool) -> dict[str, Any]:
    return {
        "image_name": image_name,
        "damages": [],
        "damage_source": "unavailable",
        "damage_hitl_used": False,
        "damage_hitl_required": hitl_required,
        "warnings": [],
        "failure_reason": "damage_geometry_missing_or_invalid",
        "required_user_action": "provide_or_correct_damage_polygon",
        "damage_hitl_request_path": None,
    }


def _valid_auto_damages(damages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [damage for damage in damages if _valid_polygon(damage.get("polygon_points", []))]


def _extract_mask_arrays(masks: Any) -> list[np.ndarray]:
    if masks is None or masks.data is None:
        return []
    mask_data = masks.data.cpu().numpy()
    return [(mask > 0.5).astype(np.uint8) for mask in mask_data]


def _extract_mask_polygons(masks: Any) -> list[list[list[float]]]:
    if masks is None or masks.xy is None:
        return []
    return [
        [[round(float(point[0]), 2), round(float(point[1]), 2)] for point in polygon]
        for polygon in masks.xy
    ]


def _render_damage_overlay(image: np.ndarray, damages: list[dict[str, Any]]) -> np.ndarray:
    overlay = image.copy()
    mask_layer = image.copy()
    for damage in damages:
        polygon_points = damage.get("polygon_points", [])
        if polygon_points:
            contour = np.array(polygon_points, dtype=np.int32)
            cv2.fillPoly(mask_layer, [contour], (0, 0, 255))
            cv2.polylines(overlay, [contour], True, (0, 0, 255), 2)
    return cv2.addWeighted(mask_layer, 0.35, overlay, 0.65, 0)


def _valid_polygon(points: Any) -> bool:
    return isinstance(points, list) and len(points) >= 3 and _polygon_area(points) > 0


def _polygon_area(points: Any) -> float:
    try:
        return round(float(cv2.contourArea(np.array(points, dtype=np.float32))), 4)
    except (TypeError, ValueError):
        return 0.0


def _bbox_from_points(points: list[list[float]]) -> list[float]:
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return [round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)]


def _round_points(points: list[list[float]]) -> list[list[float]]:
    return [[round(float(point[0]), 2), round(float(point[1]), 2)] for point in points]


def _image_name_from_stem(manual_inputs: dict[str, list[dict[str, Any]]], stem: str) -> str | None:
    for image_name in manual_inputs:
        if Path(image_name).stem == stem:
            return image_name
    return None


def _safe_read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as json_file:
            return json.load(json_file)
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as json_file:
        json.dump(data, json_file, indent=2)


def _unique(values: list[str]) -> list[str]:
    unique_values = []
    for value in values:
        if value and value not in unique_values:
            unique_values.append(value)
    return unique_values
