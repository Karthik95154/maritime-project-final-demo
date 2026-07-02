"""Image and frame loading for main_pipeline_1."""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class PipelineImage:
    """Loaded image record used inside main_pipeline_1."""

    name: str
    path: Path
    image: np.ndarray


def load_pipeline_images(input_dir: str | Path, image_extensions: list[str]) -> list[PipelineImage]:
    """Load still images for the pipeline."""
    resolved_input_dir = Path(input_dir).resolve()
    if not resolved_input_dir.exists() or not resolved_input_dir.is_dir():
        raise FileNotFoundError(f"Input image directory not found: {resolved_input_dir}")

    normalized_extensions = {extension.lower() for extension in image_extensions}
    image_paths = sorted(
        path
        for path in resolved_input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in normalized_extensions
    )

    loaded_images: list[PipelineImage] = []
    skipped_images: list[Path] = []
    for image_path in image_paths:
        image = cv2.imread(str(image_path))
        if image is None:
            skipped_images.append(image_path)
            continue
        loaded_images.append(PipelineImage(name=image_path.name, path=image_path, image=image))

    print(f"main_pipeline_1 images found: {len(image_paths)}")
    print(f"main_pipeline_1 images loaded: {len(loaded_images)}")
    print(f"main_pipeline_1 images skipped: {len(skipped_images)}")
    for skipped_image in skipped_images:
        print(f"Skipped unreadable image: {skipped_image}")
    return loaded_images


def load_pipeline_frames(input_dir: str | Path, image_extensions: list[str]) -> list[PipelineImage]:
    """Load frame inputs when frame-based runs are enabled."""
    return load_pipeline_images(input_dir, image_extensions)
