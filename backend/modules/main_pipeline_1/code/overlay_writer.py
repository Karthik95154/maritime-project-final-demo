"""Overlay writing for main_pipeline_1."""

from pathlib import Path
from typing import Any

import cv2


def write_result_overlays(
    homography_results: list[dict[str, Any]],
    output_dir: str | Path,
) -> None:
    """Write visual overlays for final result inspection."""
    resolved_output_dir = Path(output_dir).resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    written_count = 0
    for homography in homography_results:
        overlay_path = homography.get("rectified_overlay_path")
        image_name = homography.get("image_name")
        if not isinstance(overlay_path, str) or not isinstance(image_name, str):
            continue
        overlay = cv2.imread(overlay_path)
        if overlay is None:
            continue
        output_path = resolved_output_dir / f"{Path(image_name).stem}_main_pipeline_1_overlay.jpg"
        cv2.imwrite(str(output_path), overlay)
        homography["main_pipeline_1_overlay_path"] = str(output_path)
        written_count += 1
    print(f"main_pipeline_1 overlays saved: {written_count}")
