"""Visualization modules.

This package contains visualization and plotting functions:
- visualization: QA visualization creation
"""

from fmriqc.visualization.visualization import (
    SPATIAL_MAP_CONFIGS,
    create_aggregate_maps_figure,
    create_carpetplot,
    create_mean_mask_overlay,
    create_run_figure,
    create_run_spatial_maps,
    create_run_thumbnail,
    create_spatial_map_image,
    create_subject_comparison_plot,
    encode_image_base64,
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
