"""Result routing and fallback status classification for main_pipeline_1."""

from typing import Any


AUTOMATED_ROUTE = "main_pipeline_1_automated_apriltag_homography"
DAMAGE_HITL_ROUTE = "main_pipeline_1_damage_hitl_required"
APRILTAG_MISSING_ROUTE = "main_pipeline_1_apriltag_missing"
HOMOGRAPHY_FAILED_ROUTE = "main_pipeline_1_homography_failed"
MANUAL_FALLBACK_ROUTE = "main_pipeline_1_manual_fallback"


def classify_result_route(
    image_result: dict[str, Any],
) -> dict[str, Any]:
    """Classify one image result into the main_pipeline_1 route taxonomy."""
    status = str(image_result.get("status", ""))
    apriltag = image_result.get("apriltag", {})
    homography = image_result.get("homography", {})
    area = image_result.get("area", {})

    if (
        status == "area_estimated_with_apriltag_homography"
        and isinstance(apriltag, dict)
        and bool(apriltag.get("detected"))
        and isinstance(homography, dict)
        and bool(homography.get("used"))
        and isinstance(area, dict)
        and area.get("area_m2") is not None
    ):
        return {
            "route_used": AUTOMATED_ROUTE,
            "fallback_used": False,
            "fallback_reason": None,
            "required_user_action": None,
        }

    if status == "area_estimated_with_manual_homography":
        return {
            "route_used": MANUAL_FALLBACK_ROUTE,
            "fallback_used": True,
            "fallback_reason": "manual_homography_fallback_used",
            "required_user_action": None,
        }

    if status in {"manual_damage_polygon_required", "invalid_damage_geometry"}:
        return {
            "route_used": DAMAGE_HITL_ROUTE,
            "fallback_used": True,
            "fallback_reason": "damage_missing_or_needs_manual_correction",
            "required_user_action": "provide_or_correct_damage_polygon",
        }

    if status == "apriltag_not_detected" or not bool(apriltag.get("detected")):
        return {
            "route_used": APRILTAG_MISSING_ROUTE,
            "fallback_used": True,
            "fallback_reason": "apriltag_missing",
            "required_user_action": "provide_valid_apriltag_or_recapture",
        }

    if status == "homography_failed" or not bool(homography.get("used")):
        return {
            "route_used": HOMOGRAPHY_FAILED_ROUTE,
            "fallback_used": True,
            "fallback_reason": "homography_failed",
            "required_user_action": "check_apriltag_detection_or_manual_plane_debug",
        }

    return {
        "route_used": MANUAL_FALLBACK_ROUTE,
        "fallback_used": True,
        "fallback_reason": status or "manual_review_required",
        "required_user_action": image_result.get("required_user_action")
        or "review_main_pipeline_1_result",
    }
