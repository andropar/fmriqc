# QA Metrics Reference

Detailed descriptions of all computed quality metrics.

## Temporal Metrics

### tSNR (Temporal Signal-to-Noise Ratio)

**Description**: Ratio of mean signal to temporal standard deviation.

**Formula**: `tSNR = mean(signal) / std(signal)` for each voxel, then median across brain.

**Good values**: > 50 (depends on field strength, sequence, preprocessing)

**References**:
- Murphy et al. (2007). "How long to scan? The relationship between fMRI temporal signal to noise ratio and necessary scan duration."

---

### DVARS (D referring to temporal derivative)

**Description**: Spatial root mean square of temporal derivative.

**Formula**: RMS of frame-to-frame differences, standardized by median absolute deviation.

**Good values**: < 1.5 (standardized)

**References**:
- Power et al. (2012). "Spurious but systematic correlations in functional connectivity MRI networks arise from subject motion."

---

### Framewise Displacement (FD)

**Description**: Scalar measure of head motion between volumes.

**Formula**: Sum of absolute values of 6 motion parameters (3 rotations + 3 translations).

**Good values**: < 0.3 mm (strict), < 0.5 mm (lenient)

**References**:
- Power et al. (2012). "Spurious but systematic correlations in functional connectivity MRI networks arise from subject motion."

---

## Spatial Metrics

### Coverage

**Description**: Percentage of brain covered by valid (non-zero) signal.

**Good values**: > 85%

---

### Smoothness (FWHM)

**Description**: Spatial smoothness estimated from residuals.

**Units**: mm (full-width at half-maximum)

**Interpretation**: Data-dependent. Lower = less smooth (more detail), higher = more smooth.

---

### GCOR (Global Correlation)

**Description**: Average correlation between all voxel pairs.

**Good values**: < 0.2

**References**:
- Saad et al. (2013). "Correcting brain-wide correlation differences in resting-state fMRI."

---

### AR(1) (First-order Autoregression)

**Description**: Temporal autocorrelation at lag 1.

**Good values**: 0.2 - 0.6

**Interpretation**: Too low suggests over-aggressive preprocessing, too high suggests insufficient temporal filtering.

---

## Outlier Metrics

### Outlier Timepoints

**Description**: Volumes flagged as outliers based on DVARS and FD thresholds.

**Threshold**: DVARS > 2.5 SD OR FD > 0.5 mm

**Good values**: < 5% of volumes

---

### Mahalanobis Distance

**Description**: Multivariate distance from center of quality metric distribution.

**Usage**: Identifies runs that are outliers across multiple metrics simultaneously.

**Threshold**: > 3.0

---

For implementation details, see `src/fmriqa/core/metrics.py`.
