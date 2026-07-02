"""CLI entry point for main_pipeline_1."""

import argparse
from pathlib import Path

from orchestrator import run_main_pipeline_1


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for main_pipeline_1."""
    parser = argparse.ArgumentParser(
        description="Run the main_pipeline_1 production-candidate pipeline."
    )
    parser.add_argument(
        "--config",
        default="production_ready/main_pipeline_1/config/main_pipeline_1_config.yaml",
        help="Path to main_pipeline_1_config.yaml.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the CLI entry point."""
    args = parse_args()
    run_main_pipeline_1(Path(args.config))


if __name__ == "__main__":
    main()
