"""Numeric constants used throughout fMRI QA processing.

This module centralizes magic numbers and statistical constants used
across the fMRI QA pipeline to improve code maintainability and clarity.
"""

# Statistical conversion factors
MAD_TO_STD_FACTOR = 1.4826
"""float: Conversion factor from Median Absolute Deviation (MAD) to standard deviation.

For normally distributed data, MAD × 1.4826 ≈ standard deviation.
Used for robust outlier detection in fMRI timeseries.

Reference:
    Rousseeuw & Croux (1993). Alternatives to the Median Absolute Deviation.
    Journal of the American Statistical Association, 88(424), 1273-1283.
"""

# Numerical stability
EPSILON = 1e-6
"""float: Small positive value to prevent division by zero.

Used in calculations where denominators could be zero, such as:
- Coefficient of variation (CV) calculations
- Normalization operations
- Signal-to-noise ratio computations
"""

# Outlier detection thresholds
Z_SCORE_THRESHOLD = 3.0
"""float: Default z-score threshold for outlier detection.

Values beyond ±3 standard deviations are typically considered outliers
(corresponds to ~0.3% probability in a normal distribution).
"""

MAHALANOBIS_THRESHOLD = 3.0
"""float: Default Mahalanobis distance threshold for multivariate outlier detection.

Used to identify runs with unusual combinations of QA metrics.
Higher values indicate more lenient outlier criteria.
"""

# Motion correction parameters
MC_ROT_RADIUS_MM = 50.0
"""float: Effective brain radius in mm for motion correction.

Used to convert rotational motion (radians) to translational displacement (mm).
Standard value from Power et al. (2012).

Formula: displacement = rotation_radians × radius_mm

Reference:
    Power et al. (2012). Spurious but systematic correlations in functional
    connectivity MRI networks arise from subject motion.
    NeuroImage, 59(3), 2142-2154.
"""

# Signal quality thresholds
TSNR_MINIMUM_ACCEPTABLE = 30.0
"""float: Minimum acceptable temporal signal-to-noise ratio (tSNR).

Below this threshold, data quality is considered poor for most fMRI analyses.
Typical good quality: >40, Excellent: >50.
"""

FD_THRESHOLD_DEFAULT = 0.5
"""float: Default framewise displacement (FD) threshold in mm.

Volumes with FD > this value are typically flagged as high motion.
Common thresholds: 0.2 mm (stringent), 0.5 mm (moderate), 0.9 mm (lenient).

Reference:
    Power et al. (2012). Spurious but systematic correlations in functional
    connectivity MRI networks arise from subject motion.
    NeuroImage, 59(3), 2142-2154.
"""

COVERAGE_MINIMUM = 0.85
"""float: Minimum acceptable brain coverage fraction.

Proportion of expected brain voxels that must be present in the mask.
Below this threshold indicates significant signal dropout or acquisition issues.
"""
