"""Final JSON writing for main_pipeline_1."""

import json
from pathlib import Path
from typing import Any

from routing import classify_result_route


FINAL_JSON_FILENAME = "final_area_estimation_main_pipeline_1_results.json"


def build_final_results(
    *,
    images_processed: int,
    apriltag_results: list[dict[str, Any]],
    homography_results: list[dict[str, Any]],
    area_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the final main_pipeline_1 JSON object."""
    apriltag_by_image = _index_by_image(apriltag_results)
    homography_by_image = _index_by_image(homography_results)
    area_by_image = _group_by_image(area_results)
    image_names = _ordered_image_names(apriltag_results, homography_results, area_results)
    results = [
        _build_image_result(
            image_name=image_name,
            apriltag=apriltag_by_image.get(image_name, {}),
            homography=homography_by_image.get(image_name, {}),
            area_results=area_by_image.get(image_name, []),
        )
        for image_name in image_names
    ]

    return {
        "pipeline_name": "main_pipeline_1",
        "pipeline_status": "experimental_production_candidate",
        "production_default": False,
        "deployed": False,
        "reference_type": "AprilTag",
        "homography_mode": "apriltag_full_image",
        "experiment_sources": ["v2_1_1", "v2_1_2"],
        "depth_diagnostic_merged": False,
        "images_processed": images_processed,
        "successful_area_estimations": sum(
            1
            for result in results
            if result.get("status")
            in {"area_estimated_with_apriltag_homography", "area_estimated_with_manual_homography"}
        ),
        "results": results,
    }


def write_final_results(final_results: dict[str, Any], output_path: str | Path) -> None:
    """Write the final main_pipeline_1 JSON object."""
    resolved_output_path = Path(output_path).resolve()
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    with resolved_output_path.open("w", encoding="utf-8") as json_file:
        json.dump(final_results, json_file, indent=2)
    print(f"main_pipeline_1 final JSON saved to: {resolved_output_path}")


def _build_image_result(
    image_name: str,
    apriltag: dict[str, Any],
    homography: dict[str, Any],
    area_results: list[dict[str, Any]],
) -> dict[str, Any]:
    successful_areas = [
        area
        for area in area_results
        if area.get("status")
        in {"area_estimated_with_apriltag_homography", "area_estimated_with_manual_homography"}
    ]
    representative_area = successful_areas[0] if successful_areas else (area_results[0] if area_results else {})
    status = _derive_status(apriltag, homography, area_results)
    result = {
        "pipeline_name": "main_pipeline_1",
        "pipeline_status": "experimental_production_candidate",
        "image_name": image_name,
        "status": status,
        "apriltag": {
            "detected": bool(apriltag.get("apriltag_detected")),
            "tag_id": apriltag.get("tag_id"),
            "tag_label": apriltag.get("tag_label"),
            "tag_family": apriltag.get("tag_family"),
            "tag_size_mm": apriltag.get("tag_real_size_mm"),
            "scale_mm_per_pixel": representative_area.get("scale_mm_per_pixel")
            or apriltag.get("scale_mm_per_pixel"),
            "configured_tag_ids": apriltag.get("configured_tag_ids", []),
            "detected_tag_ids": apriltag.get("detected_tag_ids", []),
            "selection_policy": apriltag.get("selection_policy"),
            "selected_by": apriltag.get("selected_by"),
            "selection_status": apriltag.get("selection_status"),
        },
        "homography": {
            "used": bool(homography.get("homography_used")),
            "mode": homography.get("mode", "apriltag_full_image_homography"),
            "full_image_warp_used": bool(homography.get("full_image_warp_used")),
            "full_homography": homography.get("full_homography"),
            "source_apriltag_corners": homography.get("source_apriltag_corners", []),
            "destination_square_points": homography.get("destination_square_points", []),
            "rectified_image_path": homography.get("rectified_image_path"),
            "rectified_overlay_path": homography.get("main_pipeline_1_overlay_path")
            or homography.get("rectified_overlay_path"),
            "warped_canvas_size": homography.get("warped_canvas_size"),
            "rectification_check": homography.get("apriltag_rectification_check", {}),
        },
        "damage": {
            "source": representative_area.get("damage_source")
            or homography.get("damage_source", "unavailable"),
            "hitl_used": bool(
                representative_area.get("damage_hitl_used")
                or homography.get("damage_hitl_used", False)
            ),
            "hitl_required": bool(
                representative_area.get("damage_hitl_required")
                or homography.get("damage_hitl_required", False)
            ),
            "items": [
                {
                    "damage_id": area.get("damage_id"),
                    "damage_class": area.get("damage_class"),
                    "area_source": area.get("area_source"),
                    "original_pixel_area": area.get("original_pixel_area"),
                    "rectified_pixel_area": area.get("rectified_pixel_area"),
                    "area_mm2": area.get("area_mm2"),
                    "area_cm2": area.get("area_cm2"),
                    "area_m2": area.get("area_m2"),
                    "status": area.get("status"),
                    "warnings": area.get("warnings", []),
                }
                for area in area_results
                if area.get("damage_id") is not None
            ],
        },
        "area": {
            "area_source": representative_area.get("area_source"),
            "original_pixel_area": _sum_numeric_field(successful_areas, "original_pixel_area"),
            "rectified_pixel_area": _sum_numeric_field(successful_areas, "rectified_pixel_area"),
            "scale_mm_per_pixel": representative_area.get("scale_mm_per_pixel"),
            "area_mm2": _sum_numeric_field(successful_areas, "area_mm2"),
            "area_cm2": _sum_numeric_field(successful_areas, "area_cm2"),
            "area_m2": _sum_numeric_field(successful_areas, "area_m2"),
        },
        "fallback_reason": representative_area.get("failure_reason") or homography.get("failure_reason"),
        "required_user_action": representative_area.get("required_user_action")
        or homography.get("required_user_action"),
        "depth_diagnostic_merged": False,
        "experiment_sources": ["v2_1_1", "v2_1_2"],
    }
    return {**result, **classify_result_route(result)}


def _derive_status(
    apriltag: dict[str, Any],
    homography: dict[str, Any],
    area_results: list[dict[str, Any]],
) -> str:
    statuses = [str(area.get("status")) for area in area_results if area.get("status")]
    if "area_estimated_with_apriltag_homography" in statuses:
        return "area_estimated_with_apriltag_homography"
    if "area_estimated_with_manual_homography" in statuses:
        return "area_estimated_with_manual_homography"
    for status in statuses:
        if status in {
            "manual_damage_polygon_required",
            "invalid_damage_geometry",
            "apriltag_not_detected",
            "homography_failed",
        }:
            return status
    if not apriltag.get("apriltag_detected"):
        return "apriltag_not_detected"
    if homography.get("status") and homography.get("status") != "homography_success":
        return str(homography.get("status"))
    return "manual_review_required"


def _ordered_image_names(*result_sets: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    seen = set()
    for result_set in result_sets:
        for result in result_set:
            image_name = result.get("image_name")
            if isinstance(image_name, str) and image_name not in seen:
                names.append(image_name)
                seen.add(image_name)
    return names


def _index_by_image(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        result["image_name"]: result
        for result in results
        if isinstance(result.get("image_name"), str)
    }


def _group_by_image(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        image_name = result.get("image_name")
        if isinstance(image_name, str):
            grouped.setdefault(image_name, []).append(result)
    return grouped


def _sum_numeric_field(records: list[dict[str, Any]], field_name: str) -> float | None:
    values = [
        float(record[field_name])
        for record in records
        if isinstance(record.get(field_name), (int, float))
    ]
    if not values:
        return None
    return round(float(sum(values)), 8 if field_name == "area_m2" else 4)
