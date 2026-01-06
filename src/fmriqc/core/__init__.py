"""Core QA processing modules.

This package contains the fundamental QA processing components:
- processing: Run-level QA processing
- metrics: QA metric computations
- constants: Shared constants and thresholds
"""

# Constants can be imported without circular dependency issues
from .constants import (
    StatisticalConstants,
    MotionConstants,
    IOConstants,
    QualityThresholds,
    PhysiologicalBands,
    PlotStyle,
)

__all__ = [
    "StatisticalConstants",
    "MotionConstants",
    "IOConstants",
    "QualityThresholds",
    "PhysiologicalBands",
    "PlotStyle",
]
