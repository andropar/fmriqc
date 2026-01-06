"""Cross-run consistency analysis.

This module provides tools for assessing consistency across multiple fMRI runs
within a session using various statistical approaches.

Key Methods:
-----------
- Intraclass Correlation Coefficient (ICC): Shrout & Fleiss (1979)
- Split-half reliability: Spearman-Brown corrected correlation
- Coefficient of variation (CV): Normalized measure of dispersion
- Linear trend detection: Tests for systematic drift across runs

References:
----------
Shrout, P. E., & Fleiss, J. L. (1979). Intraclass correlations: uses in assessing
rater reliability. Psychological Bulletin, 86(2), 420-428.

McGraw, K. O., & Wong, S. P. (1996). Forming inferences about some intraclass
correlation coefficients. Psychological Methods, 1(1), 30-46.

Koo, T. K., & Li, M. Y. (2016). A guideline of selecting and reporting intraclass
correlation coefficients for reliability research. Journal of Chiropractic
Medicine, 15(2), 155-163.

Spearman, C. (1910). Correlation calculated from faulty data. British Journal
of Psychology, 3(3), 271-295.
"""

from typing import Dict, List, Tuple

import numpy as np
from scipy import stats

from fmriqc.core.constants import StatisticalConstants
from fmriqc.io.structures import RunResult, SessionResults


def compute_icc(data: np.ndarray, icc_type: str = "2,1") -> float:
    """
    Compute Intraclass Correlation Coefficient.

    Implements ICC formulas from Shrout & Fleiss (1979). For fMRI QA, we typically
    have runs (subjects/targets) as rows and voxels (raters/measures) as columns.

    Parameters
    ----------
    data : np.ndarray
        2D array (n x k): n targets/subjects/runs, k measures/raters/voxels
    icc_type : str
        Type of ICC:
        - '1,1': One-way random effects, single rater (Case 1)
        - '2,1': Two-way random effects, single rater, absolute agreement (Case 2)
        - '3,1': Two-way mixed effects, single rater, consistency (Case 3)

    Returns
    -------
    float
        ICC value (clipped to [0, 1] for interpretability)

    Notes
    -----
    Mean square decomposition for two-way ANOVA:
    - MSr: Mean square for rows (between targets/subjects)
    - MSc: Mean square for columns (between raters/measures)
    - MSe: Mean square for error (residual)

    For ICC(1,1): Only MSr and MSw (within) are used (one-way model)
    For ICC(2,1) and ICC(3,1): Full two-way decomposition

    ANOVA Assumptions:
    ------------------
    1. **Independence**: Observations should be independent between subjects/targets
    2. **Normality**: Data should be approximately normally distributed within groups
    3. **Homogeneity of variance**: Variances should be similar across groups
    4. **Random effects**: For ICC(2,1) and ICC(3,1), assumes random selection

    Violations and Robustness:
    -------------------------
    - ICC is relatively robust to moderate violations of normality
    - Large sample sizes (n > 20) provide more robust estimates
    - Severe outliers can strongly affect ICC values
    - Consider using robust alternatives (e.g., robust ANOVA) for heavily skewed data

    References
    ----------
    Shrout, P. E., & Fleiss, J. L. (1979). Intraclass correlations:
    uses in assessing rater reliability. Psychological bulletin, 86(2), 420-428.

    McGraw, K. O., & Wong, S. P. (1996). Forming inferences about some
    intraclass correlation coefficients. Psychological Methods, 1(1), 30-46.
    """
    n, k = data.shape  # n = targets/subjects, k = raters/measures

    if n < 2 or k < 2:
        return 0.0

    # Grand mean
    grand_mean = np.mean(data)

    # Row means (target/subject means)
    row_means = np.mean(data, axis=1)

    # Column means (rater/measure means)
    col_means = np.mean(data, axis=0)

    # Sum of squares
    # SS_total = sum of (x_ij - grand_mean)^2
    ss_total = np.sum((data - grand_mean) ** 2)

    # SS_rows (between targets) = k * sum of (row_mean - grand_mean)^2
    ss_rows = k * np.sum((row_means - grand_mean) ** 2)

    # SS_cols (between raters) = n * sum of (col_mean - grand_mean)^2
    ss_cols = n * np.sum((col_means - grand_mean) ** 2)

    # SS_error (residual) = SS_total - SS_rows - SS_cols
    ss_error = ss_total - ss_rows - ss_cols

    # SS_within (for one-way model) = SS_total - SS_rows
    ss_within = ss_total - ss_rows

    # Degrees of freedom
    df_rows = n - 1
    df_cols = k - 1
    df_error = (n - 1) * (k - 1)
    df_within = n * (k - 1)

    # Mean squares
    ms_rows = ss_rows / df_rows if df_rows > 0 else 0
    ms_cols = ss_cols / df_cols if df_cols > 0 else 0
    ms_error = ss_error / df_error if df_error > 0 else 0
    ms_within = ss_within / df_within if df_within > 0 else 0

    # Compute ICC based on type
    if icc_type == "1,1":
        # ICC(1,1): One-way random effects, single rater
        # Formula: (MSr - MSw) / (MSr + (k-1)*MSw)
        denom = ms_rows + (k - 1) * ms_within
        if denom < StatisticalConstants.NUMERICAL_STABILITY:
            return 0.0
        icc = (ms_rows - ms_within) / denom

    elif icc_type == "2,1":
        # ICC(2,1): Two-way random effects, single rater, absolute agreement
        # Formula: (MSr - MSe) / (MSr + (k-1)*MSe + k*(MSc-MSe)/n)
        denom = ms_rows + (k - 1) * ms_error + k * (ms_cols - ms_error) / n
        if denom < StatisticalConstants.NUMERICAL_STABILITY:
            return 0.0
        icc = (ms_rows - ms_error) / denom

    elif icc_type == "3,1":
        # ICC(3,1): Two-way mixed effects, single rater, consistency
        # Formula: (MSr - MSe) / (MSr + (k-1)*MSe)
        denom = ms_rows + (k - 1) * ms_error
        if denom < StatisticalConstants.NUMERICAL_STABILITY:
            return 0.0
        icc = (ms_rows - ms_error) / denom

    else:
        # Default to ICC(2,1)
        denom = ms_rows + (k - 1) * ms_error + k * (ms_cols - ms_error) / n
        if denom < StatisticalConstants.NUMERICAL_STABILITY:
            return 0.0
        icc = (ms_rows - ms_error) / denom

    return float(np.clip(icc, 0, 1))


class ConsistencyInterpreter:
    """Interpret consistency metrics and provide qualitative assessments."""

    # Thresholds for interpretation
    CONSISTENCY_EXCELLENT = 50.0
    CONSISTENCY_GOOD = 20.0
    CONSISTENCY_FAIR = 10.0

    ICC_EXCELLENT = 0.90
    ICC_GOOD = 0.75
    ICC_MODERATE = 0.50
    ICC_POOR = 0.25

    RELIABILITY_EXCELLENT = 0.90
    RELIABILITY_GOOD = 0.75
    RELIABILITY_ADEQUATE = 0.60

    @staticmethod
    def interpret_consistency_score(score: float) -> str:
        """Interpret overall consistency score.

        Parameters
        ----------
        score : float
            Overall consistency score

        Returns
        -------
        str
            Qualitative interpretation ('excellent', 'good', 'fair', 'poor')
        """
        if score > ConsistencyInterpreter.CONSISTENCY_EXCELLENT:
            return "excellent"
        elif score > ConsistencyInterpreter.CONSISTENCY_GOOD:
            return "good"
        elif score > ConsistencyInterpreter.CONSISTENCY_FAIR:
            return "fair"
        else:
            return "poor"

    @staticmethod
    def interpret_icc(icc: float) -> str:
        """Interpret ICC value.

        Based on Koo & Li (2016) guidelines.

        Parameters
        ----------
        icc : float
            ICC value (0 to 1)

        Returns
        -------
        str
            Qualitative interpretation
        """
        if icc > ConsistencyInterpreter.ICC_EXCELLENT:
            return "excellent"
        elif icc > ConsistencyInterpreter.ICC_GOOD:
            return "good"
        elif icc > ConsistencyInterpreter.ICC_MODERATE:
            return "moderate"
        elif icc > ConsistencyInterpreter.ICC_POOR:
            return "fair"
        else:
            return "poor"

    @staticmethod
    def interpret_reliability(reliability: float) -> str:
        """Interpret split-half reliability value.

        Parameters
        ----------
        reliability : float
            Reliability coefficient (0 to 1)

        Returns
        -------
        str
            Qualitative interpretation
        """
        if reliability > ConsistencyInterpreter.RELIABILITY_EXCELLENT:
            return "excellent"
        elif reliability > ConsistencyInterpreter.RELIABILITY_GOOD:
            return "good"
        elif reliability > ConsistencyInterpreter.RELIABILITY_ADEQUATE:
            return "adequate"
        else:
            return "questionable"

    @staticmethod
    def interpret_cv(cv: float) -> str:
        """Interpret coefficient of variation.

        Parameters
        ----------
        cv : float
            Coefficient of variation (ratio)

        Returns
        -------
        str
            Qualitative interpretation
        """
        if cv < 0.05:
            return "very_low"
        elif cv < 0.10:
            return "low"
        elif cv < 0.20:
            return "moderate"
        elif cv < 0.30:
            return "high"
        else:
            return "very_high"


def compute_split_half_reliability(
    results: List[RunResult], metric_key: str = "tsnr_median"
) -> float:
    """
    Compute split-half reliability for a metric.

    Parameters
    ----------
    results : list
        List of RunResult objects from same session
    metric_key : str
        Metric to compute reliability for

    Returns
    -------
    float
        Correlation between odd and even runs
    """
    if len(results) < 4:
        return np.nan

    values = [r.metrics.get(metric_key, np.nan) for r in results]
    values = [v for v in values if not np.isnan(v)]

    if len(values) < 4:
        return np.nan

    # Split into odd and even
    odd = values[::2]
    even = values[1::2]

    # Make equal length
    min_len = min(len(odd), len(even))
    odd = odd[:min_len]
    even = even[:min_len]

    if min_len < 2:
        return np.nan

    # Compute correlation
    corr, _ = stats.pearsonr(odd, even)

    # Spearman-Brown correction for full-length reliability
    reliability = 2 * corr / (1 + corr)

    return float(reliability)


def assess_run_consistency(results: List[RunResult]) -> Dict[str, float]:
    """
    Assess consistency across runs in a session.

    Parameters
    ----------
    results : list
        List of RunResult objects from same session

    Returns
    -------
    dict
        Consistency metrics
    """
    if len(results) < 2:
        return {}

    metrics = {}

    # Key metrics to assess
    metric_keys = [
        "tsnr_median",
        "fd_median",
        "global_mean",
        "gcor",
        "smoothness_fwhm",
    ]

    for key in metric_keys:
        values = [r.metrics.get(key, np.nan) for r in results]
        values = [v for v in values if not np.isnan(v)]

        if len(values) < 2:
            continue

        # Coefficient of variation
        mean = np.mean(values)
        std = np.std(values, ddof=1)
        cv = std / (mean + StatisticalConstants.EPSILON) if mean != 0 else np.nan

        metrics[f"{key}_cv"] = float(cv)
        metrics[f"{key}_range"] = float(np.max(values) - np.min(values))

        # Linear trend test (systematic drift)
        if len(values) >= 3:
            x = np.arange(len(values))
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, values)
            metrics[f"{key}_drift_slope"] = float(slope)
            metrics[f"{key}_drift_pvalue"] = float(p_value)

    # Split-half reliability for key metrics
    for key in ["tsnr_median", "fd_median"]:
        reliability = compute_split_half_reliability(results, key)
        if not np.isnan(reliability):
            metrics[f"{key}_split_half_reliability"] = float(reliability)

    # ICC for spatial patterns (if we have mean vectors)
    if all(hasattr(r, "mean_vector") and r.mean_vector is not None for r in results):
        # Check that all mean_vectors have the same length
        vector_lengths = [len(r.mean_vector) for r in results]
        if len(set(vector_lengths)) == 1 and vector_lengths[0] > 1:
            # All vectors have same length - safe to stack
            mean_vectors = np.array([r.mean_vector for r in results])
            if mean_vectors.shape[0] >= 2:
                try:
                    # Compute ICC across voxels
                    icc = compute_icc(mean_vectors)
                    metrics["spatial_icc"] = float(icc)
                except Exception:
                    pass

    # Overall consistency score (inverse of average CV)
    cv_values = [v for k, v in metrics.items() if k.endswith("_cv") and not np.isnan(v)]
    if cv_values:
        metrics["overall_consistency"] = float(1.0 / (np.mean(cv_values) + 0.01))

    return metrics


def identify_inconsistent_runs(
    results: List[RunResult], threshold_cv: float = 0.5
) -> List[str]:
    """
    Identify runs that are inconsistent with others in the session.

    Parameters
    ----------
    results : list
        List of RunResult objects from same session
    threshold_cv : float
        Threshold for coefficient of variation

    Returns
    -------
    list
        List of run identifiers that are inconsistent
    """
    if len(results) < 3:
        return []

    inconsistent = []

    # Key metrics
    metric_keys = ["tsnr_median", "fd_median", "global_mean"]

    for key in metric_keys:
        values = []
        identifiers = []

        for r in results:
            if key in r.metrics:
                values.append(r.metrics[key])
                identifiers.append(r.info.get_identifier())

        if len(values) < 3:
            continue

        values = np.array(values)

        # Compute robust z-scores
        median = np.median(values)
        mad = np.median(np.abs(values - median))

        if mad < StatisticalConstants.NUMERICAL_STABILITY:
            continue

        z_scores = np.abs((values - median) / (StatisticalConstants.MAD_TO_STD_FACTOR * mad))

        # Flag runs with z > 2.5
        for i, z in enumerate(z_scores):
            if z > StatisticalConstants.Z_SCORE_STRICT:
                inconsistent.append(identifiers[i])

    return list(set(inconsistent))


def compute_between_run_similarity(results: List[RunResult]) -> np.ndarray:
    """
    Compute pairwise similarity matrix between runs.

    Parameters
    ----------
    results : list
        List of RunResult objects

    Returns
    -------
    np.ndarray
        Similarity matrix (correlation of mean images)
    """
    n_runs = len(results)
    similarity = np.eye(n_runs)

    # Extract mean vectors
    mean_vectors = []
    for r in results:
        if hasattr(r, "mean_vector"):
            mean_vectors.append(r.mean_vector)
        else:
            return np.eye(n_runs)

    if len(mean_vectors) != n_runs:
        return np.eye(n_runs)

    # Compute pairwise correlations
    for i in range(n_runs):
        for j in range(i + 1, n_runs):
            # Ensure same length
            min_len = min(len(mean_vectors[i]), len(mean_vectors[j]))
            v1 = mean_vectors[i][:min_len]
            v2 = mean_vectors[j][:min_len]

            if len(v1) > 1:
                corr, _ = stats.pearsonr(v1, v2)
                similarity[i, j] = corr
                similarity[j, i] = corr

    return similarity


def generate_consistency_report(session_results: SessionResults) -> Dict[str, any]:
    """
    Generate comprehensive consistency report for a session.

    Parameters
    ----------
    session_results : SessionResults
        Results for a single session

    Returns
    -------
    dict
        Consistency report
    """
    results = session_results.runs

    report = {
        "n_runs": len(results),
        "consistency_metrics": {},
        "inconsistent_runs": [],
        "similarity_matrix": None,
        "split_half_reliability": {},
    }

    if len(results) < 2:
        return report

    # Consistency metrics
    report["consistency_metrics"] = assess_run_consistency(results)

    # Identify inconsistent runs
    report["inconsistent_runs"] = identify_inconsistent_runs(results)

    # Similarity matrix
    sim_matrix = compute_between_run_similarity(results)
    if sim_matrix is not None:
        report["similarity_matrix"] = sim_matrix.tolist()
        report["mean_similarity"] = float(
            np.mean(sim_matrix[np.triu_indices_from(sim_matrix, k=1)])
        )

    # Split-half reliability
    for key in ["tsnr_median", "fd_median", "global_mean"]:
        rel = compute_split_half_reliability(results, key)
        if not np.isnan(rel):
            report["split_half_reliability"][key] = float(rel)

    # Use interpreter for qualitative assessment
    interpreter = ConsistencyInterpreter()
    consistency_score = report["consistency_metrics"].get("overall_consistency", 0)
    report["consistency_interpretation"] = interpreter.interpret_consistency_score(
        consistency_score
    )

    # Add ICC interpretation if available
    if "spatial_icc" in report["consistency_metrics"]:
        icc = report["consistency_metrics"]["spatial_icc"]
        report["icc_interpretation"] = interpreter.interpret_icc(icc)

    # Add reliability interpretations
    report["reliability_interpretations"] = {}
    for key, value in report["split_half_reliability"].items():
        report["reliability_interpretations"][key] = interpreter.interpret_reliability(
            value
        )

    return report
