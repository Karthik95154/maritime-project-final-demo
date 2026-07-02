"""Configuration loading and validation for main_pipeline_1."""

from pathlib import Path
from typing import Any

import yaml


REQUIRED_SECTIONS = (
    "pipeline",
    "paths",
    "models",
    "apriltag",
    "inference",
    "damage_resolution",
    "homography",
    "outputs",
)


def load_main_pipeline_config(config_path: str | Path) -> dict[str, Any]:
    """Load and validate the main_pipeline_1 YAML config."""
    resolved_config_path = Path(config_path).resolve()
    if not resolved_config_path.exists():
        raise FileNotFoundError(f"Config file not found: {resolved_config_path}")

    with resolved_config_path.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    if not isinstance(config, dict):
        raise ValueError("main_pipeline_1 config must contain a YAML mapping.")

    _validate_config(config)
    return config


def resolve_pipeline_path(project_root: Path, configured_path: str) -> Path:
    """Resolve a config path relative to the repository root."""
    path = Path(configured_path)
    return path if path.is_absolute() else project_root / path


def _validate_config(config: dict[str, Any]) -> None:
    missing_sections = [section for section in REQUIRED_SECTIONS if section not in config]
    if missing_sections:
        raise KeyError(f"Missing required config sections: {missing_sections}")

    pipeline = config["pipeline"]
    if pipeline.get("name") != "main_pipeline_1":
        raise ValueError("pipeline.name must be main_pipeline_1")
    if bool(pipeline.get("depth_diagnostic_merged", False)):
        raise ValueError("main_pipeline_1 must not merge depth diagnostics yet.")

    _validate_apriltag_config(config["apriltag"])

    image_extensions = config["inference"].get("image_extensions")
    if not isinstance(image_extensions, list) or not image_extensions:
        raise ValueError("inference.image_extensions must be a non-empty list.")


def _validate_apriltag_config(apriltag: dict[str, Any]) -> None:
    selection_policy = apriltag.get("selection_policy", "config_priority")
    if selection_policy != "config_priority":
        raise ValueError("apriltag.selection_policy must be config_priority.")

    tag_options = apriltag.get("tag_options")
    if tag_options is None:
        tag_id = apriltag.get("tag_id")
        tag_size = apriltag.get("tag_size_mm")
        if tag_id is not None and not isinstance(tag_id, int):
            raise ValueError("apriltag.tag_id must be an integer when provided.")
        if not isinstance(tag_size, (int, float)) or tag_size <= 0:
            raise ValueError("apriltag.tag_size_mm must be a positive number.")
        return

    if not isinstance(tag_options, list) or not tag_options:
        raise ValueError("apriltag.tag_options must be a non-empty list.")

    seen_tag_ids: set[int] = set()
    enabled_count = 0
    for index, option in enumerate(tag_options):
        if not isinstance(option, dict):
            raise ValueError(f"apriltag.tag_options[{index}] must be a mapping.")

        tag_id = option.get("tag_id")
        if not isinstance(tag_id, int) or tag_id <= 0:
            raise ValueError(f"apriltag.tag_options[{index}].tag_id must be a positive integer.")
        if tag_id in seen_tag_ids:
            raise ValueError(f"Duplicate AprilTag ID in apriltag.tag_options: {tag_id}")
        seen_tag_ids.add(tag_id)

        tag_size = option.get("tag_size_mm")
        if not isinstance(tag_size, (int, float)) or tag_size <= 0:
            raise ValueError(f"apriltag.tag_options[{index}].tag_size_mm must be a positive number.")

        if bool(option.get("enabled", True)):
            enabled_count += 1

    if enabled_count == 0:
        raise ValueError("apriltag.tag_options must contain at least one enabled tag.")
