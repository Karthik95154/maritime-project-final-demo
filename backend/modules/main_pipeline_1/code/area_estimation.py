"""Rectified damage area estimation for main_pipeline_1."""

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


AREA_ESTIMATED = "area_estimated_with_apriltag_homography"
APRILTAG_NOT_DETECTED = "apriltag_not_detected"
HOMOGRAPHY_FAILED = "homography_failed"
INVALID_DAMAGE_GEOMETRY = "invalid_damage_geometry"
MANUAL_DAMAGE_POLYGON_REQUIRED = "manual_damage_polygon_required"


def calculate_rectified_damage_areas(
    homography_results: list[dict[str, Any]],
    output_dir: str | Path,
) -> list[dict[str, Any]]:
    """Calculate real-world damage area from rectified damage geometry."""
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for homography in homography_results:
        image_name = str(homography.get("image_name"))
        if not homography.get("homography_used"):
            results.append(_empty_area_result(image_name, str(homography.get("status") or HOMOGRAPHY_FAILED), homography))
            continue

        scale = homography.get("scale", {})
        scale_mm_per_pixel = scale.get("scale_mm_per_pixel") if isinstance(scale, dict) else None
        if not isinstance(scale_mm_per_pixel, (int, float)) or scale_mm_per_pixel <= 0:
            results.append(_empty_area_result(image_name, APRILTAG_NOT_DETECTED, homography))
            continue

        damages = homography.get("damages", [])
        if not damages:
            results.append(_empty_area_result(image_name, MANUAL_DAMAGE_POLYGON_REQUIRED, homography, float(scale_mm_per_pixel)))
            continue

        for damage in damages:
            area_source, rectified_pixel_area = _extract_rectified_pixel_area(damage)
            base = {
                "image_name": image_name,
                "damage_id": damage.get("damage_id"),
                "damage_class": damage.get("class_name"),
                "area_source": area_source,
                "original_pixel_area": damage.get("original_pixel_area"),
                "rectified_pixel_area": rectified_pixel_area,
                "pixel_area": rectified_pixel_area,
                "scale_source": scale.get("scale_source"),
                "scale_mm_per_pixel": float(scale_mm_per_pixel),
                "damage_source": damage.get("source") or homography.get("damage_source", "unavailable"),
                "damage_hitl_used": bool(homography.get("damage_hitl_used", False)),
                "damage_hitl_required": bool(homography.get("damage_hitl_required", False)),
                "warnings": damage.get("warnings", []) or homography.get("warnings", []),
                "failure_reason": homography.get("failure_reason"),
                "required_user_action": homography.get("required_user_action"),
                "damage_hitl_request_path": homography.get("damage_hitl_request_path"),
                "area_mm2": None,
                "area_cm2": None,
                "area_m2": None,
            }
            if rectified_pixel_area is None or rectified_pixel_area <= 0:
                results.append({**base, "status": INVALID_DAMAGE_GEOMETRY})
                continue

            area_status = (
                "area_estimated_with_manual_homography"
                if homography.get("mode") == "manual_plane_homography"
                else AREA_ESTIMATED
            )
            area_mm2 = float(rectified_pixel_area) * (float(scale_mm_per_pixel) ** 2)
            results.append(
                {
                    **base,
                    "rectified_pixel_area": round(float(rectified_pixel_area), 4),
                    "pixel_area": round(float(rectified_pixel_area), 4),
                    "area_mm2": round(float(area_mm2), 4),
                    "area_cm2": round(float(area_mm2 / 100), 4),
                    "area_m2": round(float(area_mm2 / 1_000_000), 8),
                    "status": area_status,
                }
            )

    _write_json(output_path / "area_results.json", results)
    return results


def _empty_area_result(
    image_name: str,
    status: str,
    homography: dict[str, Any],
    scale_mm_per_pixel: float | None = None,
) -> dict[str, Any]:
    return {
        "image_name": image_name,
        "damage_id": None,
        "damage_class": None,
        "area_source": None,
        "original_pixel_area": None,
        "rectified_pixel_area": None,
        "pixel_area": None,
        "scale_source": None,
        "scale_mm_per_pixel": scale_mm_per_pixel,
        "damage_source": homography.get("damage_source", "unavailable"),
        "damage_hitl_used": bool(homography.get("damage_hitl_used", False)),
        "damage_hitl_required": bool(homography.get("damage_hitl_required", False)),
        "warnings": homography.get("warnings", []),
        "failure_reason": homography.get("failure_reason"),
        "required_user_action": homography.get("required_user_action"),
        "damage_hitl_request_path": homography.get("damage_hitl_request_path"),
        "area_mm2": None,
        "area_cm2": None,
        "area_m2": None,
        "status": status,
    }


def _extract_rectified_pixel_area(damage: dict[str, Any]) -> tuple[str | None, float | None]:
    rectified_mask_area = damage.get("rectified_mask_pixel_area")
    if isinstance(rectified_mask_area, (int, float)) and rectified_mask_area > 0:
        return "rectified_segmentation_mask", float(rectified_mask_area)
    rectified_polygon_points = damage.get("rectified_polygon_points") or []
    if len(rectified_polygon_points) >= 3:
        contour = np.array(rectified_polygon_points, dtype=np.float32)
        return "rectified_segmentation_polygon", float(cv2.contourArea(contour))
    return None, None


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as json_file:
        json.dump(data, json_file, indent=2)
