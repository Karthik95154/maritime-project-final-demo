"""Interactive HITL annotation tool for main_pipeline_1."""

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from config import load_main_pipeline_config, resolve_pipeline_path


HOMOGRAPHY_MODE = "homography"
DAMAGE_MODE = "damage"
BOTH_MODE = "both"
VALID_MODES = {HOMOGRAPHY_MODE, DAMAGE_MODE, BOTH_MODE}
POINT_RADIUS = 18
POINT_OUTLINE_RADIUS = 24
POINT_LABEL_SCALE = 1.35
POINT_LABEL_THICKNESS = 4
DETAIL_FONT_SCALE = 1.85
DETAIL_FONT_THICKNESS = 5
DETAIL_LINE_HEIGHT = 76
DETAIL_PANEL_PADDING = 30
MANUAL_REVIEW_STATUSES = {
    "main_pipeline_1_damage_hitl_required",
    "main_pipeline_1_homography_failed",
    "main_pipeline_1_manual_fallback",
}


def parse_args() -> argparse.Namespace:
    """Parse HITL annotation tool arguments."""
    parser = argparse.ArgumentParser(
        description="Annotate manual damage and homography values for main_pipeline_1."
    )
    parser.add_argument(
        "--config",
        default="production_ready/main_pipeline_1/config/main_pipeline_1_config.yaml",
        help="Path to main_pipeline_1_config.yaml.",
    )
    parser.add_argument(
        "--mode",
        choices=tuple(sorted(VALID_MODES)),
        default=None,
        help="Annotation mode: damage, homography, or both.",
    )
    parser.add_argument(
        "--image",
        default=None,
        help="Optional image filename to annotate. Defaults to unresolved/manual-required queue.",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List queued images without opening the annotation window.",
    )
    parser.add_argument(
        "--include-corrected",
        action="store_true",
        help="Include images that already have manual values JSON.",
    )
    return parser.parse_args()


def main() -> None:
    """Open queued images, collect HITL values, and save per-image JSON files."""
    args = parse_args()
    config_path = Path(args.config).resolve()
    project_root = config_path.parents[3]
    config = load_main_pipeline_config(config_path)
    paths = config["paths"]
    hitl_config = config.get("hitl", {})

    input_images_dir = resolve_pipeline_path(project_root, paths["input_images_dir"])
    manual_values_dir = resolve_pipeline_path(
        project_root,
        str(hitl_config.get("manual_values_dir", paths["manual_img_values_dir"])),
    )
    final_json_path = resolve_pipeline_path(
        project_root,
        str(hitl_config.get("final_json_path", paths["final_json_output_path"])),
    )
    hitl_required_dir = resolve_pipeline_path(
        project_root,
        str(hitl_config.get("hitl_required_dir", paths["hitl_required_dir"])),
    )
    mode = args.mode or str(hitl_config.get("default_mode", BOTH_MODE))
    if mode not in VALID_MODES:
        mode = BOTH_MODE

    manual_values_dir.mkdir(parents=True, exist_ok=True)
    manual_values = load_manual_image_values(manual_values_dir)
    image_paths = _queued_image_paths(
        input_images_dir=input_images_dir,
        final_json_path=final_json_path,
        hitl_required_dir=hitl_required_dir,
        requested_image=args.image,
    )

    if not args.include_corrected:
        image_paths = [
            image_path
            for image_path in image_paths
            if image_path.name not in manual_values
        ]

    if args.list_only:
        print(f"main_pipeline_1 HITL queued images: {len(image_paths)}")
        for image_path in image_paths:
            existing = manual_values.get(image_path.name)
            status = "corrected" if existing else "not corrected"
            print(f"- {image_path.name}: {status}")
        return

    reviewed = 0
    corrected = 0
    skipped = 0
    for image_path in image_paths:
        image = cv2.imread(str(image_path))
        if image is None:
            skipped += 1
            continue

        reviewed += 1
        print(f"Opening main_pipeline_1 HITL window for: {image_path.name}")
        annotation = collect_hitl_annotation(
            image=image,
            image_name=image_path.name,
            mode=mode,
        )
        if annotation is None:
            skipped += 1
            continue

        save_manual_image_values(
            manual_values_dir=manual_values_dir,
            image_name=image_path.name,
            annotation=annotation,
        )
        corrected += 1

    print()
    print("main_pipeline_1 HITL Annotation Completed")
    print(f"Images reviewed: {reviewed}")
    print(f"Images corrected: {corrected}")
    print(f"Images skipped: {skipped}")
    print(f"Manual values directory: {manual_values_dir.resolve()}")


def collect_hitl_annotation(
    image: np.ndarray,
    image_name: str,
    mode: str,
) -> dict[str, Any] | None:
    """Collect homography points and/or damage polygon points for one image."""
    state: dict[str, Any] = {
        "mode": mode if mode in VALID_MODES else BOTH_MODE,
        "active_target": HOMOGRAPHY_MODE if mode in {HOMOGRAPHY_MODE, BOTH_MODE} else DAMAGE_MODE,
        "homography_points": [],
        "damage_points": [],
    }
    window_name = f"main_pipeline_1 HITL - {image_name}"

    def on_mouse(event: int, x: int, y: int, _flags: int, _param: object) -> None:
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        points = _active_points(state)
        if state["active_target"] == HOMOGRAPHY_MODE and len(points) >= 4:
            return
        points.append([int(x), int(y)])

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setMouseCallback(window_name, on_mouse)

    while True:
        display_image = _draw_annotation_overlay(image, image_name, state)
        cv2.imshow(window_name, display_image)
        key = cv2.waitKey(20) & 0xFF

        if key in (13, 10):
            cv2.destroyWindow(window_name)
            if _annotation_valid(state, image.shape):
                return {
                    "mode": state["mode"],
                    "manual_homography_plane_points": state["homography_points"],
                    "manual_damage_polygon_points": state["damage_points"],
                }
            print("Annotation not saved: required points are missing or invalid.")
            return None

        if key in (ord("s"), ord("S")):
            cv2.destroyWindow(window_name)
            return None

        if key in (ord("q"), ord("Q"), 27):
            cv2.destroyWindow(window_name)
            raise SystemExit

        if key in (8, ord("u"), ord("U")):
            points = _active_points(state)
            if points:
                points.pop()

        if key in (127, ord("r"), ord("R")):
            state["homography_points"].clear()
            state["damage_points"].clear()

        if key in (ord("h"), ord("H")):
            state["mode"] = HOMOGRAPHY_MODE
            state["active_target"] = HOMOGRAPHY_MODE

        if key in (ord("d"), ord("D")):
            state["mode"] = DAMAGE_MODE
            state["active_target"] = DAMAGE_MODE

        if key in (ord("b"), ord("B")):
            state["mode"] = BOTH_MODE
            state["active_target"] = (
                DAMAGE_MODE if len(state["homography_points"]) == 4 else HOMOGRAPHY_MODE
            )

        if state["mode"] == BOTH_MODE and key in (ord("t"), ord("T")):
            state["active_target"] = (
                DAMAGE_MODE if state["active_target"] == HOMOGRAPHY_MODE else HOMOGRAPHY_MODE
            )


def save_manual_image_values(
    manual_values_dir: str | Path,
    image_name: str,
    annotation: dict[str, Any],
) -> Path:
    """Save one manual values JSON file for an annotated image."""
    output_dir = Path(manual_values_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    homography_points = annotation.get("manual_homography_plane_points", [])
    damage_points = annotation.get("manual_damage_polygon_points", [])

    manual_damage_polygons: list[dict[str, Any]] = []
    if isinstance(damage_points, list) and damage_points:
        manual_damage_polygons.append(
            {
                "damage_id": "manual_1",
                "damage_class": "damage",
                "points": damage_points,
            }
        )

    values = validate_manual_image_values(
        {
            "image_name": image_name,
            "manual_homography_plane_points": homography_points
            if isinstance(homography_points, list)
            else [],
            "manual_damage_polygons": manual_damage_polygons,
            "annotation_source": "main_pipeline_1_hitl_window",
            "hitl_status": "corrected",
        },
        output_dir / f"{Path(image_name).stem}.json",
    )
    output_path = output_dir / f"{Path(image_name).stem}.json"
    with output_path.open("w", encoding="utf-8") as json_file:
        json.dump(values, json_file, indent=2)
    return output_path


def load_manual_image_values(manual_values_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Load existing per-image manual values JSON files."""
    values_dir = Path(manual_values_dir).resolve()
    if not values_dir.exists():
        return {}
    values: dict[str, dict[str, Any]] = {}
    for path in sorted(values_dir.glob("*.json")):
        values_path = Path(path)
        values_data = _safe_read_json(values_path)
        if not isinstance(values_data, dict):
            continue
        validated = validate_manual_image_values(values_data, values_path)
        values[validated["image_name"]] = validated
    return values


def validate_manual_image_values(data: Any, source_path: str | Path) -> dict[str, Any]:
    """Validate the main_pipeline_1 per-image manual values JSON shape."""
    if not isinstance(data, dict):
        raise ValueError(f"Manual values must contain an object: {source_path}")
    image_name = data.get("image_name")
    if not isinstance(image_name, str) or not image_name:
        raise ValueError(f"Manual values missing image_name: {source_path}")

    homography_points = data.get("manual_homography_plane_points", [])
    damage_polygons = data.get("manual_damage_polygons", [])
    if not isinstance(homography_points, list):
        raise ValueError(f"manual_homography_plane_points must be a list: {source_path}")
    if homography_points and len(homography_points) != 4:
        raise ValueError(f"manual_homography_plane_points must contain exactly 4 points: {source_path}")
    _validate_points(homography_points, source_path, minimum_points=0)

    if not isinstance(damage_polygons, list):
        raise ValueError(f"manual_damage_polygons must be a list: {source_path}")
    for polygon in damage_polygons:
        if not isinstance(polygon, dict):
            raise ValueError(f"Each manual damage polygon must be an object: {source_path}")
        points = polygon.get("points", [])
        if not isinstance(points, list) or len(points) < 3:
            raise ValueError(f"Manual damage polygon must contain at least 3 points: {source_path}")
        _validate_points(points, source_path, minimum_points=3)

    return {
        "image_name": image_name,
        "manual_homography_plane_points": homography_points,
        "manual_damage_polygons": damage_polygons,
        "annotation_source": data.get("annotation_source", "main_pipeline_1_hitl_window"),
        "hitl_status": data.get("hitl_status", "corrected"),
    }


def _queued_image_paths(
    input_images_dir: Path,
    final_json_path: Path,
    hitl_required_dir: Path,
    requested_image: str | None,
) -> list[Path]:
    if requested_image:
        image_path = input_images_dir / requested_image
        if not image_path.exists():
            raise FileNotFoundError(f"Requested image not found: {image_path}")
        return [image_path]

    queued_names = _queued_names_from_final_json(final_json_path)
    queued_names.update(_queued_names_from_hitl_requests(hitl_required_dir))
    if not queued_names:
        return sorted(path for path in input_images_dir.iterdir() if path.is_file())
    return [
        input_images_dir / image_name
        for image_name in sorted(queued_names)
        if (input_images_dir / image_name).exists()
    ]


def _queued_names_from_final_json(final_json_path: Path) -> set[str]:
    if not final_json_path.exists():
        return set()
    data = _safe_read_json(final_json_path)
    if not isinstance(data, dict):
        return set()
    names = set()
    for result in data.get("results", []):
        if not isinstance(result, dict):
            continue
        route_used = result.get("route_used")
        if route_used in MANUAL_REVIEW_STATUSES or bool(result.get("fallback_used")):
            image_name = result.get("image_name")
            if isinstance(image_name, str):
                names.add(image_name)
    return names


def _queued_names_from_hitl_requests(hitl_required_dir: Path) -> set[str]:
    if not hitl_required_dir.exists():
        return set()
    names = set()
    for request_path in hitl_required_dir.glob("*.json"):
        request = _safe_read_json(request_path)
        if isinstance(request, dict) and isinstance(request.get("image_name"), str):
            names.add(request["image_name"])
    return names


def _annotation_valid(state: dict[str, Any], image_shape: tuple[int, ...]) -> bool:
    if state["mode"] == HOMOGRAPHY_MODE:
        return _valid_local_homography_points(state["homography_points"], image_shape)
    if state["mode"] == DAMAGE_MODE:
        return len(state["damage_points"]) >= 3
    return (
        _valid_local_homography_points(state["homography_points"], image_shape)
        and len(state["damage_points"]) >= 3
    )


def _valid_local_homography_points(points: list[list[int]], image_shape: tuple[int, ...]) -> bool:
    if len(points) != 4 or len(image_shape) < 2:
        return False
    image_height, image_width = image_shape[:2]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return not (
        max(xs) - min(xs) >= image_width * 0.9
        and max(ys) - min(ys) >= image_height * 0.9
    )


def _active_points(state: dict[str, Any]) -> list[list[int]]:
    if state["active_target"] == DAMAGE_MODE:
        return state["damage_points"]
    return state["homography_points"]


def _draw_annotation_overlay(
    image: np.ndarray,
    image_name: str,
    state: dict[str, Any],
) -> np.ndarray:
    display_image = image.copy()
    homography_points = state["homography_points"]
    damage_points = state["damage_points"]
    _draw_points(display_image, homography_points, (255, 0, 255), close=len(homography_points) == 4)
    _draw_points(display_image, damage_points, (0, 255, 255), close=len(damage_points) >= 3)
    lines = [
        f"main_pipeline_1 HITL: {image_name}",
        f"Mode: {state['mode']} | Active: {state['active_target']}",
        f"Homography: {len(homography_points)}/4 | Damage polygon points: {len(damage_points)}",
        "Click add | H homography | D damage | B both | T switch target | Enter save",
        "U/Backspace undo | R/Delete reset | S skip | Q/Esc quit",
    ]
    _draw_text_panel(display_image, lines)
    return display_image


def _draw_points(
    image: np.ndarray,
    points: list[list[int]],
    color: tuple[int, int, int],
    close: bool,
) -> None:
    for index, point in enumerate(points):
        x, y = point
        cv2.circle(image, (x, y), POINT_OUTLINE_RADIUS, (0, 0, 0), -1)
        cv2.circle(image, (x, y), POINT_RADIUS, color, -1)
        cv2.circle(image, (x, y), POINT_OUTLINE_RADIUS, (255, 255, 255), 2)
        cv2.putText(
            image,
            str(index + 1),
            (x + POINT_OUTLINE_RADIUS + 8, y - POINT_OUTLINE_RADIUS),
            cv2.FONT_HERSHEY_SIMPLEX,
            POINT_LABEL_SCALE,
            (0, 0, 0),
            POINT_LABEL_THICKNESS + 2,
            cv2.LINE_AA,
        )
        cv2.putText(
            image,
            str(index + 1),
            (x + POINT_OUTLINE_RADIUS + 8, y - POINT_OUTLINE_RADIUS),
            cv2.FONT_HERSHEY_SIMPLEX,
            POINT_LABEL_SCALE,
            color,
            POINT_LABEL_THICKNESS,
            cv2.LINE_AA,
        )
    if len(points) >= 2:
        contour = np.array(points, dtype=np.int32)
        cv2.polylines(image, [contour], close, (0, 0, 0), 7)
        cv2.polylines(image, [contour], close, color, 4)


def _draw_text_panel(image: np.ndarray, lines: list[str]) -> None:
    text_sizes = [
        cv2.getTextSize(
            line,
            cv2.FONT_HERSHEY_SIMPLEX,
            DETAIL_FONT_SCALE,
            DETAIL_FONT_THICKNESS,
        )[0]
        for line in lines
    ]
    panel_width = min(
        image.shape[1] - 20,
        max((size[0] for size in text_sizes), default=900) + DETAIL_PANEL_PADDING * 2,
    )
    panel_height = DETAIL_PANEL_PADDING * 2 + DETAIL_LINE_HEIGHT * len(lines)
    overlay = image.copy()
    cv2.rectangle(overlay, (10, 10), (10 + panel_width, 10 + panel_height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.72, image, 0.28, 0, image)
    cv2.rectangle(image, (10, 10), (10 + panel_width, 10 + panel_height), (255, 255, 255), 2)
    y = 10 + DETAIL_PANEL_PADDING + 28
    for line in lines:
        cv2.putText(
            image,
            line,
            (10 + DETAIL_PANEL_PADDING, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            DETAIL_FONT_SCALE,
            (0, 0, 0),
            DETAIL_FONT_THICKNESS + 2,
            cv2.LINE_AA,
        )
        cv2.putText(
            image,
            line,
            (10 + DETAIL_PANEL_PADDING, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            DETAIL_FONT_SCALE,
            (255, 255, 255),
            DETAIL_FONT_THICKNESS,
            cv2.LINE_AA,
        )
        y += DETAIL_LINE_HEIGHT


def _validate_points(points: list[Any], source_path: str | Path, minimum_points: int) -> None:
    if len(points) < minimum_points:
        raise ValueError(f"Not enough points in manual values: {source_path}")
    for point in points:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError(f"Each point must be [x, y]: {source_path}")
        x, y = point
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise ValueError(f"Point coordinates must be numeric: {source_path}")


def _safe_read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as json_file:
            return json.load(json_file)
    except (OSError, json.JSONDecodeError):
        return {}


if __name__ == "__main__":
    main()
