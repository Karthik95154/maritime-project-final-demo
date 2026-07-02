"""End-to-end orchestration for main_pipeline_1."""

from pathlib import Path
from typing import Any

from apriltag_detection import detect_apriltag_scale
from area_estimation import calculate_rectified_damage_areas
from config import load_main_pipeline_config, resolve_pipeline_path
from damage_resolution import resolve_damage_geometry
from homography import compute_full_image_homography
from image_io import load_pipeline_images
from output_writer import build_final_results, write_final_results
from overlay_writer import write_result_overlays


def run_main_pipeline_1(config_path: str | Path) -> dict[str, Any]:
    """Run main_pipeline_1 end to end."""
    resolved_config_path = Path(config_path).resolve()
    project_root = resolved_config_path.parents[3]
    config = load_main_pipeline_config(resolved_config_path)
    paths = config["paths"]

    images = load_pipeline_images(
        input_dir=resolve_pipeline_path(project_root, paths["input_images_dir"]),
        image_extensions=config["inference"]["image_extensions"],
    )
    damage_results = resolve_damage_geometry(
        images=images,
        config=config,
        project_root=project_root,
    )
    apriltag_results = detect_apriltag_scale(
        images=images,
        config=config,
        output_dir=resolve_pipeline_path(project_root, paths["debug_dir"]) / "apriltag_detection",
    )
    homography_results = compute_full_image_homography(
        images=images,
        damage_results=damage_results,
        apriltag_results=apriltag_results,
        output_dir=resolve_pipeline_path(project_root, paths["debug_dir"]) / "homography",
        config=config,
        project_root=project_root,
    )
    area_results = calculate_rectified_damage_areas(
        homography_results=homography_results,
        output_dir=resolve_pipeline_path(project_root, paths["debug_dir"]) / "area_estimation",
    )
    write_result_overlays(
        homography_results=homography_results,
        output_dir=resolve_pipeline_path(project_root, paths["overlays_dir"]),
    )
    final_results = build_final_results(
        images_processed=len(images),
        apriltag_results=apriltag_results,
        homography_results=homography_results,
        area_results=area_results,
    )
    write_final_results(
        final_results=final_results,
        output_path=resolve_pipeline_path(project_root, paths["final_json_output_path"]),
    )

    print()
    print("main_pipeline_1 completed")
    print(f"Images processed: {len(images)}")
    print(f"Area estimated: {final_results['successful_area_estimations']}")
    print("Depth diagnostic merged: False")
    return final_results
