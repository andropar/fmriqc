"""Constants for QA report generation.

This module contains metric tooltips, standard values, flag descriptions,
and other constants used throughout the reporting system.
"""

# Metric tooltips - short explanations for hover
METRIC_TOOLTIPS = {
    "tsnr_median": "Temporal signal-to-noise ratio (median). Higher is better. Typical range: 20-100+.",
    "fd_median": "Framewise displacement median (mm). Lower is better. <0.2mm is excellent, >0.5mm is concerning.",
    "dvars_percent_above": "Percentage of volumes with high DVARS (signal change). Lower is better. <5% is good.",
    "dvars_std_median": "Standardized DVARS median. Measures signal variability. Lower is better.",
    "dvars_vstd_median": "Voxelwise standardized DVARS median. Lower is better.",
    "outlier_percent_above": "Percentage of volumes flagged as outliers. Lower is better. <2% is good.",
    "fd_percent_above": "Percentage of volumes with FD > threshold. Lower is better. <5% is good.",
    "coverage": "Brain mask coverage fraction. Higher is better. Should be >0.9.",
    "smoothness_fwhm": "Spatial smoothness (FWHM in mm). Should match expected smoothing kernel.",
    "gcor": "Global correlation. Measures global signal strength. Higher is generally better.",
    "ar1_median": "Lag-1 autocorrelation (median). Measures temporal correlation. Typical range: 0.1-0.5.",
    "global_mean": "Mean global signal intensity. Should be stable across runs.",
    "n_hyperintense_slices": "Number of hyperintense slices detected. Lower is better. Should be 0.",
    "slice_outlier_max": "Maximum slice outlier fraction. Lower is better. <0.1 is good.",
    "physiological_power_ratio": "Ratio of physiological noise power. Lower is better. <0.3 is good.",
    "mask_components": "Number of disconnected mask components. Should be 1.",
    "mask_largest_component_fraction": "Fraction of mask in largest component. Should be >0.95.",
    "mask_voxel_count": "Total number of voxels in the brain mask.",
    "mask_volume_fraction": "Fraction of image volume covered by the brain mask.",
    "signal_outside_mask_ratio": "Ratio of signal outside mask to inside mask. Lower is better.",
    "cardiac_freq_peak": "Peak frequency of cardiac noise (Hz). Typical range: 0.8-1.5 Hz. Requires TR < 0.67s to detect.",
    "cardiac_power": "Power at cardiac frequency peak.",
    "cardiac_detectable": "Whether cardiac band (0.8-1.5 Hz) is below Nyquist frequency. Requires TR < 0.67s.",
    "respiratory_freq_peak": "Peak frequency of respiratory noise (Hz). Typical range: 0.15-0.4 Hz.",
    "respiratory_power": "Power at respiratory frequency peak.",
    "respiratory_detectable": "Whether respiratory band (0.15-0.4 Hz) is below Nyquist frequency. Requires TR < 1.25s.",
    "nyquist_freq": "Nyquist frequency (0.5/TR). Physiological signals above this cannot be detected.",
    "fieldmap_present": "Whether a fieldmap is available for susceptibility distortion correction.",
    "fieldmap_type": "Type of fieldmap: phasediff, pepolar, or epi_single.",
}

# Good standard values for metrics (for reference in tables)
METRIC_STANDARDS = {
    "tsnr_median": ">30",
    "fd_median": "<0.2 mm",
    "dvars_percent_above": "<5%",
    "dvars_std_median": "<1.5",
    "dvars_vstd_median": "<1.5",
    "outlier_percent_above": "<2%",
    "fd_percent_above": "<5%",
    "coverage": ">0.9",
    "smoothness_fwhm": "~6-8 mm",
    "gcor": ">0.1",
    "ar1_median": "0.1-0.5",
    "global_mean": "stable",
    "n_hyperintense_slices": "0",
    "slice_outlier_max": "<0.1",
    "physiological_power_ratio": "<0.3",
    "mask_components": "1",
    "mask_largest_component_fraction": ">0.95",
    "mask_voxel_count": "varies",
    "mask_volume_fraction": "varies",
    "signal_outside_mask_ratio": "<0.1",
    "cardiac_freq_peak": "0.8-1.5 Hz",
    "cardiac_power": "varies",
    "cardiac_detectable": "depends on TR",
    "respiratory_freq_peak": "0.15-0.4 Hz",
    "respiratory_power": "varies",
    "respiratory_detectable": "depends on TR",
    "nyquist_freq": "0.5/TR Hz",
    "fieldmap_present": "yes",
    "fieldmap_type": "varies",
}

# Flag descriptions for display
FLAG_DESCRIPTIONS = {
    "tsnr_low": "Low temporal signal-to-noise ratio",
    "tsnr_drop": "Low temporal signal-to-noise ratio",
    "dvars_high": "High percentage of volumes with elevated DVARS",
    "dvars": "High percentage of volumes with elevated DVARS",
    "outliers_high": "High percentage of outlier volumes",
    "outliers": "High percentage of outlier volumes",
    "motion_high": "High framewise displacement (motion)",
    "fd_high": "High framewise displacement (motion)",
    "hyperintense_slices": "Hyperintense slices detected",
    "slice_outliers": "High slice outlier fraction",
    "mask_fragmented": "Brain mask has multiple disconnected components",
    "physiological_noise_high": "High physiological noise power ratio",
}

# Key metrics for interactive comparison
COMPARISON_METRICS = [
    ("tsnr_median", "tSNR", "Temporal SNR"),
    ("fd_median", "FD (mm)", "Framewise Displacement"),
    ("dvars_std_median", "DVARS", "Standardized DVARS"),
    ("gcor", "GCOR", "Global Correlation"),
    ("smoothness_fwhm", "FWHM (mm)", "Smoothness"),
    ("ar1_median", "AR(1)", "Autocorrelation"),
    ("coverage", "Coverage", "Brain Coverage"),
    ("outlier_percent_above", "Outliers (%)", "Outlier Percentage"),
]

# Metrics to display in summary cards
SUMMARY_METRICS = [
    "tsnr_median",
    "fd_median",
    "dvars_std_median",
    "gcor",
    "smoothness_fwhm",
    "ar1_median",
]

# Metrics to hide from detailed tables (internal or redundant)
HIDDEN_METRICS = {
    "global_mean",
    "mask_volume_fraction",
}
