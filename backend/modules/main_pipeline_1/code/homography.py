"""Full-image AprilTag homography for main_pipeline_1."""

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from image_io import PipelineImage


APRILTAG_NOT_DETECTED = "apriltag_not_detected"
HOMOGRAPHY_FAILED = "homography_failed"
MANUAL_DAMAGE_POLYGON_REQUIRED = "manual_damage_polygon_required"


def compute_full_image_homography(
    images: list[PipelineImage],
    damage_results: list[dict[str, Any]],
    apriltag_results: list[dict[str, Any]],
    output_dir: str | Path,
    config: dict[str, Any] | None = None,
    project_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Compute full-image homography and transform damage geometry."""
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    damage_by_image = _index_by_image(damage_results)
    apriltag_by_image = _index_by_image(apriltag_results)
    manual_homography_by_image = _load_manual_homography_inputs(config, project_root)
    manual_fallback_enabled = bool(
        (config or {}).get("homography", {}).get("enable_manual_homography_fallback", True)
    )
    results: list[dict[str, Any]] = []

    for image in images:
        image_name = image.name
        image_stem = image.path.stem
        apriltag = apriltag_by_image.get(image_name, {})
        damage_metadata = damage_by_image.get(image_name, {})
        damages = damage_metadata.get("damages", [])

        if not apriltag.get("apriltag_detected"):
            if manual_fallback_enabled and image_name in manual_homography_by_image:
                results.append(
                    _manual_plane_homography(
                        image=image,
                        damage_metadata=damage_metadata,
                        apriltag=apriltag,
                        plane_points=manual_homography_by_image[image_name],
                        output_dir=output_path,
                    )
                )
                continue
            results.append(_homography_failure(image_name, APRILTAG_NOT_DETECTED))
            continue

        try:
            transform = _compute_apriltag_full_image_homography(
                image=image.image,
                apriltag_corners=apriltag.get("corners", []),
            )
        except (cv2.error, ValueError) as exc:
            if manual_fallback_enabled and image_name in manual_homography_by_image:
                manual_result = _manual_plane_homography(
                    image=image,
                    damage_metadata=damage_metadata,
                    apriltag=apriltag,
                    plane_points=manual_homography_by_image[image_name],
                    output_dir=output_path,
                )
                manual_result["automatic_homography_error"] = str(exc)
                results.append(manual_result)
                continue
            failed = _homography_failure(image_name, HOMOGRAPHY_FAILED)
            failed["error"] = str(exc)
            results.append(failed)
            continue

        rectified_image = cv2.warpPerspective(
            image.image,
            transform["full_homography_np"],
            (
                transform["warped_canvas_size"][0],
                transform["warped_canvas_size"][1],
            ),
        )
        rectified_image_path = output_path / f"{image_stem}_main_pipeline_1_rectified.jpg"
        cv2.imwrite(str(rectified_image_path), rectified_image)

        rectified_damages = _rectify_damages(
            damages=damages,
            homography_matrix=transform["full_homography_np"],
            width=transform["warped_canvas_size"][0],
            height=transform["warped_canvas_size"][1],
            output_dir=output_path,
            image_stem=f"{image_stem}_main_pipeline_1",
        )
        transformed_apriltag_corners = _warp_polygon_points(
            transform["source_apriltag_corners"],
            transform["full_homography_np"],
        )
        rectified_overlay = _render_rectified_overlay(
            rectified_image,
            rectified_damages,
            transformed_apriltag_corners,
        )
        rectified_overlay_path = output_path / f"{image_stem}_main_pipeline_1_overlay.jpg"
        cv2.imwrite(str(rectified_overlay_path), rectified_overlay)

        results.append(
            {
                "image_name": image_name,
                "homography_used": True,
                "status": "homography_success" if damages else MANUAL_DAMAGE_POLYGON_REQUIRED,
                "mode": "apriltag_full_image_homography",
                "full_image_warp_used": True,
                "tag_homography": transform["tag_homography_np"].tolist(),
                "translation_matrix": transform["translation_matrix_np"].tolist(),
                "full_homography": transform["full_homography_np"].tolist(),
                "source_apriltag_corners": transform["source_apriltag_corners"],
                "destination_square_points": transform["destination_square_points"],
                "warped_canvas_size": transform["warped_canvas_size"],
                "rectified_image_path": str(rectified_image_path),
                "rectified_overlay_path": str(rectified_overlay_path),
                "damages": rectified_damages,
                "damage_source": damage_metadata.get("damage_source", "unavailable"),
                "damage_hitl_used": bool(damage_metadata.get("damage_hitl_used", False)),
                "damage_hitl_required": bool(damage_metadata.get("damage_hitl_required", False)),
                "warnings": damage_metadata.get("warnings", []),
                "failure_reason": damage_metadata.get("failure_reason"),
                "required_user_action": damage_metadata.get("required_user_action"),
                "damage_hitl_request_path": damage_metadata.get("damage_hitl_request_path"),
                "rectified_apriltag_corners": transformed_apriltag_corners,
                "apriltag_rectification_check": _validate_rectified_apriltag_square(
                    transformed_apriltag_corners
                ),
                "scale": _calculate_rectified_or_original_scale(
                    apriltag,
                    transformed_apriltag_corners,
                ),
            }
        )

    _write_json(output_path / "homography_results.json", results)
    return results


def _manual_plane_homography(
    image: PipelineImage,
    damage_metadata: dict[str, Any],
    apriltag: dict[str, Any],
    plane_points: list[list[float]],
    output_dir: Path,
) -> dict[str, Any]:
    image_stem = image.path.stem
    ordered_points = _order_quad_points(_validate_quad_points(plane_points, image.name))
    destination_points, width, height = _manual_destination_rectangle(ordered_points)
    homography_matrix = cv2.getPerspectiveTransform(ordered_points, destination_points)
    rectified_image = cv2.warpPerspective(image.image, homography_matrix, (width, height))
    rectified_image_path = output_dir / f"{image_stem}_manual_plane_rectified.jpg"
    cv2.imwrite(str(rectified_image_path), rectified_image)

    damages = damage_metadata.get("damages", [])
    rectified_damages = _rectify_damages(
        damages=damages,
        homography_matrix=homography_matrix,
        width=width,
        height=height,
        output_dir=output_dir,
        image_stem=f"{image_stem}_manual_plane",
    )
    rectified_apriltag_corners = (
        _warp_polygon_points(apriltag.get("corners", []), homography_matrix)
        if len(apriltag.get("corners", [])) == 4
        else []
    )
    rectified_overlay = _render_rectified_overlay(
        rectified_image,
        rectified_damages,
        rectified_apriltag_corners,
    )
    rectified_overlay_path = output_dir / f"{image_stem}_manual_plane_overlay.jpg"
    cv2.imwrite(str(rectified_overlay_path), rectified_overlay)

    return {
        "image_name": image.name,
        "homography_used": True,
        "status": "homography_success" if damages else MANUAL_DAMAGE_POLYGON_REQUIRED,
        "mode": "manual_plane_homography",
        "homography_source": "manual_homography_plane_points",
        "full_image_warp_used": False,
        "full_homography": homography_matrix.tolist(),
        "manual_plane_points": plane_points,
        "destination_square_points": _round_points(destination_points),
        "warped_canvas_size": [width, height],
        "rectified_image_path": str(rectified_image_path),
        "rectified_overlay_path": str(rectified_overlay_path),
        "damages": rectified_damages,
        "damage_source": damage_metadata.get("damage_source", "unavailable"),
        "damage_hitl_used": bool(damage_metadata.get("damage_hitl_used", False)),
        "damage_hitl_required": bool(damage_metadata.get("damage_hitl_required", False)),
        "warnings": damage_metadata.get("warnings", []),
        "failure_reason": None,
        "required_user_action": None,
        "damage_hitl_request_path": damage_metadata.get("damage_hitl_request_path"),
        "rectified_apriltag_corners": rectified_apriltag_corners,
        "apriltag_rectification_check": _validate_rectified_apriltag_square(
            rectified_apriltag_corners
        ),
        "scale": _calculate_rectified_or_original_scale(apriltag, rectified_apriltag_corners),
    }


def _compute_apriltag_full_image_homography(
    image: np.ndarray,
    apriltag_corners: list[list[float]],
) -> dict[str, Any]:
    source_points = _order_quad_points(_validate_quad_points(apriltag_corners, "apriltag"))
    side_length = int(round(_average_side_length(source_points.tolist())))
    if side_length <= 0:
        raise ValueError("AprilTag destination square side length must be positive.")

    destination_points = np.array(
        [[0.0, 0.0], [float(side_length), 0.0], [float(side_length), float(side_length)], [0.0, float(side_length)]],
        dtype=np.float32,
    )
    tag_homography = cv2.getPerspectiveTransform(source_points, destination_points)
    image_height, image_width = image.shape[:2]
    image_corners = np.array(
        [[0.0, 0.0], [float(image_width - 1), 0.0], [float(image_width - 1), float(image_height - 1)], [0.0, float(image_height - 1)]],
        dtype=np.float32,
    ).reshape(-1, 1, 2)
    warped_corners = cv2.perspectiveTransform(image_corners, tag_homography).reshape(-1, 2)
    min_x, min_y = float(np.min(warped_corners[:, 0])), float(np.min(warped_corners[:, 1]))
    max_x, max_y = float(np.max(warped_corners[:, 0])), float(np.max(warped_corners[:, 1]))
    width, height = int(np.ceil(max_x - min_x)), int(np.ceil(max_y - min_y))
    if width <= 0 or height <= 0:
        raise ValueError("Full warped canvas dimensions must be positive.")

    translation_matrix = np.array(
        [[1.0, 0.0, -min_x], [0.0, 1.0, -min_y], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    return {
        "tag_homography_np": tag_homography,
        "translation_matrix_np": translation_matrix,
        "full_homography_np": translation_matrix @ tag_homography,
        "source_apriltag_corners": _round_points(source_points),
        "destination_square_points": _round_points(destination_points),
        "warped_canvas_size": [width, height],
    }


def _rectify_damages(
    damages: list[dict[str, Any]],
    homography_matrix: np.ndarray,
    width: int,
    height: int,
    output_dir: Path,
    image_stem: str,
) -> list[dict[str, Any]]:
    rectified_damages = []
    for damage in damages:
        rectified_polygon = _warp_polygon_points(damage.get("polygon_points", []), homography_matrix)
        rectified_mask = _polygon_to_mask(rectified_polygon, width, height)
        rectified_mask_path = None
        if rectified_mask is not None:
            rectified_mask_path = output_dir / f"{image_stem}_damage_{damage['damage_id']}_rectified_mask.png"
            cv2.imwrite(str(rectified_mask_path), rectified_mask * 255)
        rectified_damages.append(
            {
                "damage_id": damage.get("damage_id"),
                "class_name": damage.get("class_name"),
                "confidence": damage.get("confidence"),
                "source": damage.get("source"),
                "warnings": damage.get("warnings", []),
                "original_pixel_area": damage.get("mask_pixel_area"),
                "rectified_polygon_points": rectified_polygon,
                "rectified_mask_path": str(rectified_mask_path) if rectified_mask_path else None,
                "rectified_mask_pixel_area": int(np.count_nonzero(rectified_mask)) if rectified_mask is not None else None,
            }
        )
    return rectified_damages


def _homography_failure(image_name: str, status: str) -> dict[str, Any]:
    return {
        "image_name": image_name,
        "homography_used": False,
        "status": status,
        "mode": "apriltag_full_image_homography",
        "full_image_warp_used": False,
        "damages": [],
        "scale": {"scale_mm_per_pixel": None},
        "failure_reason": status,
        "required_user_action": "provide_valid_apriltag_or_recapture"
        if status == APRILTAG_NOT_DETECTED
        else "check_apriltag_detection_or_manual_plane_debug",
    }


def _order_quad_points(points: list[list[float]]) -> np.ndarray:
    point_array = np.array(points, dtype=np.float32)
    coordinate_sums = point_array.sum(axis=1)
    coordinate_diffs = np.diff(point_array, axis=1).reshape(4)
    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = point_array[np.argmin(coordinate_sums)]
    ordered[2] = point_array[np.argmax(coordinate_sums)]
    ordered[1] = point_array[np.argmin(coordinate_diffs)]
    ordered[3] = point_array[np.argmax(coordinate_diffs)]
    return ordered


def _manual_destination_rectangle(ordered_points: np.ndarray) -> tuple[np.ndarray, int, int]:
    top_left, top_right, bottom_right, bottom_left = ordered_points
    width = int(round(max(np.linalg.norm(top_right - top_left), np.linalg.norm(bottom_right - bottom_left))))
    height = int(round(max(np.linalg.norm(bottom_left - top_left), np.linalg.norm(bottom_right - top_right))))
    if width <= 0 or height <= 0:
        raise ValueError("Manual homography output width and height must be positive.")
    destination_points = np.array(
        [[0.0, 0.0], [float(width - 1), 0.0], [float(width - 1), float(height - 1)], [0.0, float(height - 1)]],
        dtype=np.float32,
    )
    return destination_points, width, height


def _validate_quad_points(points: Any, label: str) -> list[list[float]]:
    if not isinstance(points, list) or len(points) != 4:
        raise ValueError(f"{label} points must contain exactly 4 points.")
    return [[float(point[0]), float(point[1])] for point in points]


def _warp_polygon_points(points: list[list[float]], homography_matrix: np.ndarray) -> list[list[float]]:
    if not points:
        return []
    point_array = np.array(points, dtype=np.float32).reshape(-1, 1, 2)
    return _round_points(cv2.perspectiveTransform(point_array, homography_matrix).reshape(-1, 2))


def _polygon_to_mask(points: list[list[float]], width: int, height: int) -> np.ndarray | None:
    if len(points) < 3:
        return None
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(mask, [np.array(points, dtype=np.int32)], 1)
    return mask


def _calculate_rectified_or_original_scale(
    apriltag: dict[str, Any],
    rectified_apriltag_corners: list[list[float]],
) -> dict[str, Any]:
    tag_real_size_mm = apriltag.get("tag_real_size_mm")
    if apriltag.get("apriltag_detected") and isinstance(tag_real_size_mm, (int, float)) and len(rectified_apriltag_corners) == 4:
        rectified_pixel_size = _average_side_length(rectified_apriltag_corners)
        if rectified_pixel_size > 0:
            return {
                "scale_source": "rectified_apriltag",
                "tag_id": apriltag.get("tag_id"),
                "tag_real_size_mm": float(tag_real_size_mm),
                "rectified_tag_pixel_size_avg": round(float(rectified_pixel_size), 4),
                "original_tag_pixel_size_avg": apriltag.get("tag_pixel_size_avg"),
                "scale_mm_per_pixel": round(float(tag_real_size_mm / rectified_pixel_size), 8),
            }
    return {
        "scale_source": "original_image_apriltag" if apriltag.get("apriltag_detected") else None,
        "tag_id": apriltag.get("tag_id"),
        "tag_real_size_mm": apriltag.get("tag_real_size_mm"),
        "rectified_tag_pixel_size_avg": None,
        "original_tag_pixel_size_avg": apriltag.get("tag_pixel_size_avg"),
        "scale_mm_per_pixel": apriltag.get("scale_mm_per_pixel"),
    }


def _validate_rectified_apriltag_square(corners: list[list[float]]) -> dict[str, Any]:
    if len(corners) != 4:
        return {"passed": False, "side_lengths_px": [], "angle_check": {"angles_deg": [], "passed": False}}
    points = np.array(corners, dtype=np.float64)
    side_lengths = [float(np.linalg.norm(points[index] - points[(index + 1) % 4])) for index in range(4)]
    angles = []
    for index in range(4):
        vector_a = points[(index - 1) % 4] - points[index]
        vector_b = points[(index + 1) % 4] - points[index]
        denominator = float(np.linalg.norm(vector_a) * np.linalg.norm(vector_b))
        angles.append(float(np.degrees(np.arccos(np.clip(float(np.dot(vector_a, vector_b) / denominator), -1.0, 1.0)))) if denominator else 0.0)
    mean_side = float(np.mean(side_lengths)) if side_lengths else 0.0
    side_passed = bool(mean_side > 0 and max(abs(side - mean_side) for side in side_lengths) <= mean_side * 0.03)
    angle_passed = all(abs(angle - 90.0) <= 3.0 for angle in angles)
    return {
        "passed": bool(side_passed and angle_passed),
        "side_lengths_px": [round(float(side), 4) for side in side_lengths],
        "angle_check": {"angles_deg": [round(float(angle), 4) for angle in angles], "passed": bool(angle_passed)},
    }


def _render_rectified_overlay(
    rectified_image: np.ndarray,
    damages: list[dict[str, Any]],
    apriltag_corners: list[list[float]],
) -> np.ndarray:
    overlay = rectified_image.copy()
    mask_layer = rectified_image.copy()
    for damage in damages:
        points = damage.get("rectified_polygon_points", [])
        if points:
            contour = np.array(points, dtype=np.int32)
            cv2.fillPoly(mask_layer, [contour], (0, 0, 255))
            cv2.polylines(overlay, [contour], True, (0, 0, 255), 2)
    if apriltag_corners:
        cv2.polylines(overlay, [np.array(apriltag_corners, dtype=np.int32)], True, (0, 255, 0), 2)
    return cv2.addWeighted(mask_layer, 0.25, overlay, 0.75, 0) if damages else overlay


def _average_side_length(points: list[list[float]]) -> float:
    point_array = np.array(points, dtype=np.float32)
    return float(np.mean([np.linalg.norm(point_array[index] - point_array[(index + 1) % 4]) for index in range(4)]))


def _round_points(points: np.ndarray) -> list[list[float]]:
    return [[round(float(point[0]), 2), round(float(point[1]), 2)] for point in points]


def _index_by_image(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {result["image_name"]: result for result in results}


def _load_manual_homography_inputs(
    config: dict[str, Any] | None,
    project_root: Path | None,
) -> dict[str, list[list[float]]]:
    if not config or project_root is None:
        return {}
    manual_values_dir = _resolve_path(
        project_root,
        str(
            config.get("hitl", {}).get(
                "manual_values_dir",
                config.get("paths", {}).get("manual_img_values_dir", ""),
            )
        ),
    )
    if not manual_values_dir.exists():
        return {}

    manual_inputs: dict[str, list[list[float]]] = {}
    for path in manual_values_dir.glob("*.json"):
        data = _safe_read_json(path)
        if not isinstance(data, dict):
            continue
        image_name = data.get("image_name")
        points = data.get("manual_homography_plane_points", [])
        if isinstance(image_name, str) and isinstance(points, list) and len(points) == 4:
            manual_inputs[image_name] = [
                [float(point[0]), float(point[1])]
                for point in points
                if isinstance(point, list) and len(point) == 2
            ]
    return {
        image_name: points
        for image_name, points in manual_inputs.items()
        if len(points) == 4
    }


def _resolve_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path


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
