# main_pipeline_1

`main_pipeline_1` is a clean production-candidate pipeline for single-plane ship damage area estimation. It is built from the successful learnings of the V2.1.1 and V2.1.2 experiments, but it is not a copy of either experiment folder.

## Current Status

- Pipeline name: `main_pipeline_1`
- Status: Experimental production candidate
- Location: `production_ready/main_pipeline_1`
- Deployed: No
- Production default: No
- Approval required before deployment: Yes
- Depth/V2.1.3: Not included

## Why This Exists

V2.1.1 proved useful manual/HITL workflows. V2.1.2 proved the automated AprilTag full-image homography route for single-plane area estimation. This pipeline takes those successful ideas and rebuilds them as one owned pipeline with its own folders, module names, config, outputs, and status.

## Folder Structure

```text
production_ready/main_pipeline_1/
  README.md
  STATUS.md
  config/
    main_pipeline_1_config.yaml
  code/
    __init__.py
    config.py
    image_io.py
    damage_resolution.py
    apriltag_detection.py
    homography.py
    area_estimation.py
    routing.py
    overlay_writer.py
    output_writer.py
    orchestrator.py
    run_main_pipeline_1.py
  data/
    input_images/
    input_frames/
    manual_damage_polygons/
    manual_img_values/
    apriltag_inputs/
  outputs/
    final_json/
    overlays/
    debug/
    hitl_required/
```

## Workflow

```text
input image/frame
-> load image/frame
-> resolve damage geometry from automatic or manual source
-> request damage HITL if damage geometry is missing
-> detect AprilTag
-> fail safely if AprilTag is missing
-> compute full-image AprilTag homography
-> fail safely if homography cannot be computed
-> transform damage geometry with the full-image homography
-> calculate rectified damage area
-> write overlay
-> write final JSON
-> bucket failed/manual-required cases
```

## Inputs

- `data/input_images/`: still images for processing.
- `data/input_frames/`: extracted frames for future frame-based runs.
- `data/manual_damage_polygons/`: manual damage geometry inputs.
- `data/manual_img_values/`: per-image manual/HITL correction values.
- `data/apriltag_inputs/`: optional AprilTag support inputs.

## Adding New AprilTags

AprilTag IDs are configured in `config/main_pipeline_1_config.yaml`. Add each usable tag under `apriltag.tag_options`:

```yaml
apriltag:
  tag_family: "tag36h11"
  selection_policy: "config_priority"
  tag_options:
    - tag_id: 1
      tag_size_mm: 148.0
      label: "primary_148mm"
      enabled: true
    - tag_id: 2
      tag_size_mm: 148.0
      label: "secondary_148mm"
      enabled: true
```

The pipeline detects all visible tags, keeps only enabled configured IDs, and selects the first matching tag from the `tag_options` list. Move a tag higher in the list when it should be preferred if multiple configured tags appear in the same image.

## Outputs

- Final JSON: `outputs/final_json/final_area_estimation_main_pipeline_1_results.json`
- Overlays: `outputs/overlays/`
- Debug artifacts: `outputs/debug/`
- Manual-required cases: `outputs/hitl_required/`

## Run Command

```powershell
.\.ros\Scripts\python.exe production_ready\main_pipeline_1\code\run_main_pipeline_1.py --config production_ready\main_pipeline_1\config\main_pipeline_1_config.yaml
```

## HITL Correction Window

Run the HITL annotation window after a pipeline run when images need manual damage or homography correction:

```powershell
.\.ros\Scripts\python.exe production_ready\main_pipeline_1\code\hitl_annotation_tool.py --config production_ready\main_pipeline_1\config\main_pipeline_1_config.yaml --mode both
```

Modes:

- `--mode damage`: collect damage polygons only.
- `--mode homography`: collect 4 manual homography plane points only.
- `--mode both`: collect both homography points and damage polygons in one session.

Useful options:

```powershell
.\.ros\Scripts\python.exe production_ready\main_pipeline_1\code\hitl_annotation_tool.py --config production_ready\main_pipeline_1\config\main_pipeline_1_config.yaml --list-only
.\.ros\Scripts\python.exe production_ready\main_pipeline_1\code\hitl_annotation_tool.py --config production_ready\main_pipeline_1\config\main_pipeline_1_config.yaml --image "example.jpeg" --mode damage
```

Window controls:

- Left click: add point.
- `H`: homography mode.
- `D`: damage mode.
- `B`: both mode.
- `T`: switch active target when in both mode.
- `Enter`: save.
- `U` or Backspace: undo last point.
- `R` or Delete: reset current image.
- `S`: skip current image.
- `Q` or Esc: quit.

Saved HITL files are written to:

```text
data/manual_img_values/
```

The pipeline reads these JSON files on the next run. Damage polygons are used for damage geometry resolution. Manual homography plane points are used as a fallback when the AprilTag full-image homography route cannot complete cleanly.

## Promotion Rule

This pipeline stays an experimental production candidate until it is validated against the successful V2.1.2 area outputs and approved for deployment. Deployed versions should be placed under `Deployed/` in a future promotion step.
