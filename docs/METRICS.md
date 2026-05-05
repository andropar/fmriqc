# QA Metrics Reference

`fmriqc` computes compact run-level and volume-level diagnostics for one
fMRI time-series snapshot. Metric interpretation depends on acquisition,
preprocessing, mask, and motion provenance.

## Temporal Metrics

### tSNR

Temporal signal-to-noise ratio is the temporal mean divided by temporal
standard deviation in each mask voxel, summarized across the mask.

Higher values are often preferable, but smoothing and denoising can increase
tSNR while also changing the data.

### DVARS

DVARS is a frame-to-frame RMS signal-change diagnostic. The standardized DVARS
used by `fmriqc` is an approximate QA summary and should not be assumed to
exactly match every external implementation.

### FD

Framewise displacement depends on the motion source:

- fMRIPrep confounds with `framewise_displacement`
- FD computed from six fMRIPrep motion columns
- FD computed from FSL/MCFLIRT `.par` files
- optional generated MCFLIRT motion fallback

Generated motion from raw BOLD can be useful as a fallback acquisition-motion
estimate. Generated motion from already-preprocessed BOLD is a residual
realignment estimate.

### Global Signal PSD

The report can show a global-signal PSD diagnostic. It is informational only;
`fmriqc` does not infer cardiac or respiratory physiology from BOLD alone.

### AR(1)

Lag-1 temporal autocorrelation after simple detrending. Interpretation is
contextual and depends on preprocessing and temporal filtering.

## Spatial Metrics

### Signal Coverage Fraction

Fraction of mask voxels with positive mean signal. This is not a full
anatomical field-of-view coverage estimate.

### Low-Signal Map

Map of the lowest-signal percentile within the mask. It is a review aid, not a
formal susceptibility-loss measurement.

### Apparent Smoothness

Estimated from demeaned time-series data. This is not formal GLM residual
smoothness and should be interpreted as contextual.

### GCOR

Global correlation summary across mask voxels. High values can reflect global
structure, preprocessing, motion, or other shared signal sources.

## Flags and Candidate Censor Vectors

Run flags are threshold-based QA indicators. Candidate censor vectors use FD
and DVARS series to identify volumes that may need project-specific handling.

Automatic flags are not final scientific exclusions.
