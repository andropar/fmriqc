"""Visualization modules.

This package contains visualization and plotting functions:
- visualization: QA visualization creation
"""

from fmriqa.visualization.visualization import (
    create_run_figure,
    create_carpetplot,
    create_run_thumbnail,
    create_aggregate_maps_figure,
    create_subject_comparison_plot,
    create_spatial_map_image,
    create_run_spatial_maps,
    create_mean_mask_overlay,
    encode_image_base64,
    SPATIAL_MAP_CONFIGS,
)

__all__ = [
    "create_run_figure",
    "create_carpetplot",
    "create_run_thumbnail",
    "create_aggregate_maps_figure",
    "create_subject_comparison_plot",
    "create_spatial_map_image",
    "create_run_spatial_maps",
    "create_mean_mask_overlay",
    "encode_image_base64",
    "SPATIAL_MAP_CONFIGS",
]
