"""Core constants for fMRI QA pipeline.

This module centralizes all magic numbers, thresholds, and configuration
constants used throughout the fmriqa package. All constants are organized
into logical groups and documented with references where applicable.
"""

from dataclasses import dataclass
from typing import Tuple


# === QUALITY THRESHOLDS ===

class QualityThresholds:
    """Quality metric thresholds for QA assessment.

    These thresholds define acceptable ranges for various quality metrics.
    Values are based on literature recommendations and community standards.
    """

    # Temporal SNR thresholds
    TSNR_MINIMUM_ACCEPTABLE = 30.0
    """Minimum acceptable tSNR value (Parrish et al., 2000)."""

    TSNR_THRESHOLD_GOOD = 40.0
    """tSNR threshold for 'good' quality data."""

    # Framewise displacement thresholds
    FD_THRESHOLD_DEFAULT = 0.5
    """Default FD threshold in mm (Power et al., 2012)."""

    FD_THRESHOLD_STRICT = 0.3
    """Strict FD threshold for pediatric or high-precision studies."""

    FD_THRESHOLD_LENIENT = 0.7
    """Lenient FD threshold for naturalistic or clinical studies."""

    # DVARS threshold
    DVARS_THRESHOLD = 1.5
    """DVARS standardized threshold (Nichols, 2017)."""

    # Brain coverage thresholds
    COVERAGE_MINIMUM = 0.85
    """Minimum acceptable brain coverage (85%)."""

    COVERAGE_EXCELLENT = 0.95
    """Excellent brain coverage (95%)."""


# === STATISTICAL CONSTANTS ===

class StatisticalConstants:
    """Statistical analysis constants.

    Constants for outlier detection, robust statistics, and numerical stability.
    """

    MAD_TO_STD_FACTOR = 1.4826
    """Conversion factor from Median Absolute Deviation (MAD) to standard deviation.

    For normally distributed data, MAD * 1.4826 ≈ standard deviation.
    Reference: Rousseeuw & Croux (1993).
    """

    EPSILON = 1e-6
    """Small positive value to prevent division by zero."""

    NUMERICAL_STABILITY = 1e-10
    """Very small value for numerical stability in matrix operations."""

    Z_SCORE_THRESHOLD = 3.0
    """Default z-score threshold for univariate outlier detection (3 sigma rule)."""

    Z_SCORE_STRICT = 2.5
    """Strict z-score threshold for conservative outlier detection."""

    MAHALANOBIS_THRESHOLD = 3.0
    """Mahalanobis distance threshold for multivariate outlier detection."""

    OUTLIER_PERCENTILE_LOW = 5
    """Lower percentile for outlier detection (5th percentile)."""

    OUTLIER_PERCENTILE_HIGH = 95
    """Upper percentile for outlier detection (95th percentile)."""


# === MOTION PARAMETERS ===

class MotionConstants:
    """Motion correction and analysis constants.

    Constants for motion parameter computation and quality assessment.
    """

    MC_ROT_RADIUS_MM = 50.0
    """Effective brain radius in mm for converting rotation to displacement.

    Used to convert angular rotations to linear displacement at cortical surface.
    Reference: Power et al. (2012), Friston et al. (1996).
    """

    EXTREME_MOTION_FD = 5.0
    """FD threshold in mm for flagging extreme motion events."""

    EXTREME_MOTION_ROTATION_DEG = 3.0
    """Rotation threshold in degrees for flagging extreme motion."""

    SPIN_HISTORY_FRAMES = 1
    """Number of frames after motion event to flag (spin history effect)."""


# === PHYSIOLOGICAL NOISE ===

class PhysiologicalBands:
    """Frequency bands for physiological noise detection.

    Defines typical frequency ranges for cardiac and respiratory artifacts
    in fMRI data.
    """

    CARDIAC_LOW = 0.67
    """Lower bound of cardiac frequency band in Hz (~40 bpm)."""

    CARDIAC_HIGH = 1.25
    """Upper bound of cardiac frequency band in Hz (~75 bpm)."""

    RESPIRATORY_LOW = 0.15
    """Lower bound of respiratory frequency band in Hz (~9 breaths/min)."""

    RESPIRATORY_HIGH = 0.4
    """Upper bound of respiratory frequency band in Hz (~24 breaths/min)."""

    SAMPLING_RATE_DEFAULT = 0.5
    """Default sampling rate in Hz (TR = 2.0 seconds)."""


# === VISUALIZATION ===

class PlotStyle:
    """Plotting constants and style configuration.

    Defines consistent styling for all QA visualizations including figure sizes,
    colors, fonts, and layout parameters.
    """

    # Figure sizes (width, height) in inches
    THUMBNAIL_SIZE: Tuple[float, float] = (4.5, 4.5)
    """Size for thumbnail/preview figures."""

    FULL_FIGURE_SIZE: Tuple[float, float] = (18, 11)
    """Size for full detailed QA figures."""

    CARPETPLOT_SIZE: Tuple[float, float] = (13, 8)
    """Size for carpet plot figures."""

    # Colors (hex codes)
    COLOR_SUCCESS = '#27ae60'
    """Green color for success/good quality indicators."""

    COLOR_WARNING = '#e74c3c'
    """Red color for warnings/poor quality indicators."""

    COLOR_INFO = '#3498db'
    """Blue color for informational elements."""

    COLOR_NEUTRAL = '#9b59b6'
    """Purple color for neutral elements."""

    # Font sizes (points)
    FONT_TITLE = 18
    """Font size for main titles."""

    FONT_SUBTITLE = 13
    """Font size for subtitles and section headers."""

    FONT_LABEL = 11
    """Font size for axis labels and legends."""

    FONT_SMALL = 8
    """Font size for small annotations and ticks."""

    # Layout spacing
    SUBPLOT_SPACING = 0.25
    """Space between subplots (in figure fraction)."""

    MARGIN_HORIZONTAL = 0.035
    """Horizontal margin (left/right) in figure fraction."""

    MARGIN_VERTICAL = 0.2
    """Vertical margin (top/bottom) in figure fraction."""

    # Mosaic parameters
    MOSAIC_ROWS = 4
    """Number of rows in mosaic display."""

    MOSAIC_COLS = 6
    """Number of columns in mosaic display."""


# === FILE I/O ===

class IOConstants:
    """File I/O and serialization constants.

    Constants for caching, serialization, and file operations.
    """

    NAMESPACE_MAPS = "maps::"
    """Namespace prefix for map data in serialized files."""

    NAMESPACE_SERIES = "series::"
    """Namespace prefix for time series data in serialized files."""

    NAMESPACE_SLICE_QC = "slice_qc::"
    """Namespace prefix for slice QC data in serialized files."""

    MAX_INLINE_ARRAY_SIZE = 256
    """Maximum array size to store inline (vs. as external file)."""

    CACHE_VERSION = "1.0"
    """Cache format version for compatibility checking."""


# === PROCESSING ===

class ProcessingDefaults:
    """Default processing parameters.

    Default values for various processing operations throughout the pipeline.
    """

    DETREND_ORDER = 2
    """Polynomial order for temporal detrending."""

    SMOOTHING_FWHM = 5
    """Spatial smoothing FWHM in mm."""

    BANDPASS_LOW = 0.01
    """Lower bound for bandpass filter in Hz."""

    BANDPASS_HIGH = 0.1
    """Upper bound for bandpass filter in Hz."""

    MIN_VOLUMES = 10
    """Minimum number of volumes required for analysis."""

    MIN_VOXELS_BRAIN = 1000
    """Minimum number of brain voxels required."""


# === EXCLUSION PROFILES ===

@dataclass(frozen=True)
class ExclusionProfile:
    """Exclusion threshold profile for different stringency levels.

    Defines quality thresholds for determining whether a run should be
    excluded from analysis. Three profiles are provided: strict, moderate, lenient.
    """

    fd_threshold: float
    """Mean FD threshold in mm."""

    tsnr_threshold: float
    """Minimum acceptable tSNR."""

    coverage_threshold: float
    """Minimum brain coverage (0-1 range)."""

    dvars_threshold: float
    """Maximum acceptable standardized DVARS."""

    data_loss_threshold: float
    """Maximum acceptable proportion of censored volumes (0-1 range)."""


# Predefined stringency profiles
STRINGENCY_PROFILES = {
    'strict': ExclusionProfile(
        fd_threshold=0.3,
        tsnr_threshold=40.0,
        coverage_threshold=0.90,
        dvars_threshold=1.3,
        data_loss_threshold=0.10,
    ),
    'moderate': ExclusionProfile(
        fd_threshold=0.5,
        tsnr_threshold=30.0,
        coverage_threshold=0.85,
        dvars_threshold=1.5,
        data_loss_threshold=0.20,
    ),
    'lenient': ExclusionProfile(
        fd_threshold=0.7,
        tsnr_threshold=20.0,
        coverage_threshold=0.75,
        dvars_threshold=2.0,
        data_loss_threshold=0.30,
    ),
}
"""Predefined exclusion threshold profiles for different quality standards."""


__all__ = [
    'QualityThresholds',
    'StatisticalConstants',
    'MotionConstants',
    'PhysiologicalBands',
    'PlotStyle',
    'IOConstants',
    'ProcessingDefaults',
    'ExclusionProfile',
    'STRINGENCY_PROFILES',
]
