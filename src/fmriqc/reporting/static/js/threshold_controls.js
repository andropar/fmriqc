/**
 * Threshold controls for fMRI QA reports
 * Allows users to adjust quality thresholds and re-evaluate data
 */

// Default thresholds (matches METRIC_INFO in reporting.py)
const DEFAULT_THRESHOLDS = {
    tsnr_median: 30.0,
    fd_median: 0.5,
    dvars_std_median: 1.5,
    coverage: 0.85,
    outlier_percent_above: 5.0,
    fd_percent_above: 10.0
};

// Threshold presets
const THRESHOLD_PRESETS = {
    strict: {
        tsnr_median: 40.0,
        fd_median: 0.3,
        dvars_std_median: 1.3,
        coverage: 0.90,
        outlier_percent_above: 3.0,
        fd_percent_above: 5.0
    },
    moderate: {
        tsnr_median: 30.0,
        fd_median: 0.5,
        dvars_std_median: 1.5,
        coverage: 0.85,
        outlier_percent_above: 5.0,
        fd_percent_above: 10.0
    },
    lenient: {
        tsnr_median: 20.0,
        fd_median: 0.7,
        dvars_std_median: 2.0,
        coverage: 0.75,
        outlier_percent_above: 10.0,
        fd_percent_above: 20.0
    }
};

// Current active thresholds
let activeThresholds = { ...DEFAULT_THRESHOLDS };

/**
 * Initialize threshold controls
 */
function initThresholdControls() {
    // Load saved thresholds from localStorage
    const saved = localStorage.getItem('fmriqa_thresholds');
    if (saved) {
        try {
            const parsed = JSON.parse(saved);
            activeThresholds = { ...DEFAULT_THRESHOLDS, ...parsed };
        } catch (e) {
            console.warn('Failed to parse saved thresholds');
        }
    }

    // Apply thresholds to metricInfo
    applyThresholds();

    // Set up UI event handlers
    setupThresholdUI();
}

/**
 * Apply current thresholds to studyData.metricInfo
 */
function applyThresholds() {
    if (typeof studyData === 'undefined' || !studyData.metricInfo) return;

    Object.keys(activeThresholds).forEach(key => {
        if (studyData.metricInfo[key]) {
            studyData.metricInfo[key].threshold = activeThresholds[key];
        }
    });
}

/**
 * Set up threshold UI event handlers
 */
function setupThresholdUI() {
    // Populate current values
    populateThresholdInputs();

    // Preset buttons
    document.querySelectorAll('.threshold-preset-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const preset = this.dataset.preset;
            if (THRESHOLD_PRESETS[preset]) {
                activeThresholds = { ...THRESHOLD_PRESETS[preset] };
                populateThresholdInputs();
                updatePresetButtons(preset);
            }
        });
    });

    // Input change handlers
    document.querySelectorAll('.threshold-input').forEach(input => {
        input.addEventListener('change', function() {
            const key = this.dataset.metric;
            const value = parseFloat(this.value);
            if (!isNaN(value) && key) {
                activeThresholds[key] = value;
                updatePresetButtons(null); // Clear preset selection
            }
        });
    });

    // Apply button
    const applyBtn = document.getElementById('apply-thresholds-btn');
    if (applyBtn) {
        applyBtn.addEventListener('click', applyAndRefresh);
    }

    // Reset button
    const resetBtn = document.getElementById('reset-thresholds-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', resetThresholds);
    }

    // Update preset button states
    updatePresetButtons(detectCurrentPreset());
}

/**
 * Populate input fields with current threshold values
 */
function populateThresholdInputs() {
    Object.entries(activeThresholds).forEach(([key, value]) => {
        const input = document.querySelector(`.threshold-input[data-metric="${key}"]`);
        if (input) {
            input.value = value;
        }
    });
}

/**
 * Update preset button active states
 */
function updatePresetButtons(activePreset) {
    document.querySelectorAll('.threshold-preset-btn').forEach(btn => {
        if (btn.dataset.preset === activePreset) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

/**
 * Detect which preset (if any) matches current thresholds
 */
function detectCurrentPreset() {
    for (const [name, preset] of Object.entries(THRESHOLD_PRESETS)) {
        let matches = true;
        for (const [key, value] of Object.entries(preset)) {
            if (activeThresholds[key] !== value) {
                matches = false;
                break;
            }
        }
        if (matches) return name;
    }
    return null;
}

/**
 * Apply thresholds and refresh visualizations
 */
function applyAndRefresh() {
    // Read values from input fields
    const mapping = {
        'thresh-tsnr': 'tsnr_median',
        'thresh-fd': 'fd_median',
        'thresh-dvars': 'dvars_std_median',
        'thresh-coverage': 'coverage'
    };

    Object.entries(mapping).forEach(([inputId, key]) => {
        const input = document.getElementById(inputId);
        if (input) {
            const value = parseFloat(input.value);
            if (!isNaN(value)) {
                activeThresholds[key] = value;
            }
        }
    });

    // Save to localStorage
    localStorage.setItem('fmriqa_thresholds', JSON.stringify(activeThresholds));

    // Apply to metricInfo
    applyThresholds();

    // Refresh visualizations
    if (typeof updateDistributions === 'function') {
        updateDistributions();
    }
    if (typeof updateScatterPlot === 'function') {
        updateScatterPlot();
    }

    // Recalculate quality summary
    recalculateQualitySummary();

    // Close modal
    closeThresholdModal();

    // Show feedback
    showThresholdFeedback('Thresholds applied');
}

/**
 * Reset thresholds to defaults
 */
function resetThresholds() {
    activeThresholds = { ...DEFAULT_THRESHOLDS };
    localStorage.removeItem('fmriqa_thresholds');
    populateThresholdInputsById();
    applyPreset('moderate');
}

/**
 * Recalculate quality summary based on new thresholds
 */
function recalculateQualitySummary() {
    if (typeof studyData === 'undefined' || !studyData.runs) return;

    let good = 0, warning = 0, bad = 0;

    studyData.runs.forEach(run => {
        const flagCount = countFlags(run);
        if (flagCount === 0) good++;
        else if (flagCount <= 2) warning++;
        else bad++;
    });

    const total = studyData.runs.length;

    // Update quality legend (simple template uses .quality-legend spans)
    const goodLegend = document.querySelector('.quality-legend .good');
    const warnLegend = document.querySelector('.quality-legend .warn');
    const badLegend = document.querySelector('.quality-legend .bad');

    if (goodLegend) goodLegend.textContent = `${good} good`;
    if (warnLegend) warnLegend.textContent = `${warning} review`;
    if (badLegend) badLegend.textContent = `${bad} issues`;

    // Also try the badge format (complex template)
    const goodBadge = document.querySelector('.quality-badge-good');
    const warningBadge = document.querySelector('.quality-badge-warning');
    const badBadge = document.querySelector('.quality-badge-bad');

    if (goodBadge) goodBadge.textContent = `${good} good`;
    if (warningBadge) warningBadge.textContent = `${warning} review`;
    if (badBadge) badBadge.textContent = `${bad} issues`;

    // Update quality bar
    updateQualityBar(good, warning, bad, total);

    // Update exclusion callout
    updateExclusionCallout(bad);
}

/**
 * Update the exclusion recommendation callout based on current thresholds
 */
function updateExclusionCallout(excludedCount) {
    const callout = document.getElementById('exclusion-callout');

    if (excludedCount > 0) {
        // Update count and plural
        const countEl = document.getElementById('exclusion-count');
        const pluralEl = document.getElementById('exclusion-plural');
        const reasonsEl = document.getElementById('exclusion-reasons');

        if (countEl) countEl.textContent = excludedCount;
        if (pluralEl) pluralEl.textContent = excludedCount > 1 ? 's' : '';
        if (reasonsEl) reasonsEl.innerHTML = `Based on current threshold settings. <a href="#subjects">View details below</a>`;

        // Show callout if hidden
        if (callout) callout.style.display = '';

        // Create callout if it doesn't exist
        if (!callout) {
            const qualitySection = document.querySelector('.quality-section');
            if (qualitySection) {
                const newCallout = document.createElement('div');
                newCallout.className = 'action-callout collapsible';
                newCallout.id = 'exclusion-callout';
                newCallout.innerHTML = `
                    <div class="callout-header" onclick="toggleExclusionCallout()">
                        <strong><span id="exclusion-count">${excludedCount}</span> run<span id="exclusion-plural">${excludedCount > 1 ? 's' : ''}</span> recommended for exclusion</strong>
                        <span class="callout-toggle">▶</span>
                    </div>
                    <div class="callout-details" style="display: none;">
                        <p id="exclusion-reasons">Based on current threshold settings. <a href="#subjects">View details below</a></p>
                    </div>
                `;
                qualitySection.parentNode.insertBefore(newCallout, qualitySection.nextSibling);
            }
        }
    } else {
        // Hide callout if no exclusions
        if (callout) {
            callout.style.display = 'none';
        }
    }

    // Update subject table statuses
    updateSubjectTableStatus();
}

/**
 * Update subject table status column based on current thresholds
 */
function updateSubjectTableStatus() {
    if (typeof studyData === 'undefined' || !studyData.runs) return;

    // Group runs by subject and count flags
    const subjectStats = {};
    studyData.runs.forEach(run => {
        const subject = run.subject;
        if (!subjectStats[subject]) {
            subjectStats[subject] = { flagged: 0, excluded: 0, total: 0 };
        }
        subjectStats[subject].total++;

        const flagCount = countFlags(run);
        if (flagCount > 0) subjectStats[subject].flagged++;
        if (flagCount >= 3) subjectStats[subject].excluded++;
    });

    // Update table rows
    const tbody = document.querySelector('.table-container tbody');
    if (!tbody) return;

    tbody.querySelectorAll('tr').forEach(row => {
        const subjectLink = row.querySelector('.subject-link');
        if (!subjectLink) return;

        const subjectId = subjectLink.textContent.trim();
        const stats = subjectStats[subjectId];
        if (!stats) return;

        // Find and update status cell (last td)
        const cells = row.querySelectorAll('td');
        const statusCell = cells[cells.length - 1];
        if (!statusCell) return;

        if (stats.flagged === 0) {
            statusCell.innerHTML = '<span class="status-dot good"></span>Good';
        } else if (stats.excluded > 0) {
            statusCell.innerHTML = `<span class="status-dot bad"></span>${stats.excluded} excluded`;
        } else {
            statusCell.innerHTML = `<span class="status-dot warn"></span>${stats.flagged} flagged`;
        }

        // Update metric cell colors (tSNR is column 4, FD is column 5, 0-indexed: 3, 4)
        const tsnrCell = cells[3];
        const fdCell = cells[4];
        const t = activeThresholds;

        if (tsnrCell) {
            const tsnr = parseFloat(tsnrCell.textContent);
            tsnrCell.classList.remove('bad', 'warn');
            if (!isNaN(tsnr)) {
                if (tsnr < t.tsnr_median * 0.67) tsnrCell.classList.add('bad');
                else if (tsnr < t.tsnr_median) tsnrCell.classList.add('warn');
            }
        }

        if (fdCell) {
            const fd = parseFloat(fdCell.textContent);
            fdCell.classList.remove('bad', 'warn');
            if (!isNaN(fd)) {
                if (fd > t.fd_median * 1.5) fdCell.classList.add('bad');
                else if (fd > t.fd_median) fdCell.classList.add('warn');
            }
        }
    });
}

/**
 * Count flags for a run based on current thresholds
 */
function countFlags(run) {
    let flags = 0;
    const m = run.metrics;
    const t = activeThresholds;

    if (m.tsnr_median != null && m.tsnr_median < t.tsnr_median) flags++;
    if (m.fd_median != null && m.fd_median > t.fd_median) flags++;
    if (m.dvars_std_median != null && m.dvars_std_median > t.dvars_std_median) flags++;
    if (m.coverage != null && m.coverage < t.coverage) flags++;
    if (m.outlier_percent_above != null && m.outlier_percent_above > t.outlier_percent_above) flags++;
    if (m.fd_percent_above != null && m.fd_percent_above > t.fd_percent_above) flags++;

    return flags;
}

/**
 * Update the quality distribution bar
 */
function updateQualityBar(good, warning, bad, total) {
    if (total === 0) return;

    const goodPct = (good / total * 100).toFixed(0);
    const warningPct = (warning / total * 100).toFixed(0);
    const badPct = (bad / total * 100).toFixed(0);

    // Try simple template format first (.quality-bar .good)
    let goodSeg = document.querySelector('.quality-bar .good');
    let warningSeg = document.querySelector('.quality-bar .warn');
    let badSeg = document.querySelector('.quality-bar .bad');

    // Fall back to complex template format (.quality-bar .segment.good)
    if (!goodSeg) goodSeg = document.querySelector('.quality-bar .segment.good');
    if (!warningSeg) warningSeg = document.querySelector('.quality-bar .segment.warning');
    if (!badSeg) badSeg = document.querySelector('.quality-bar .segment.bad');

    if (goodSeg) {
        goodSeg.style.width = `${goodPct}%`;
    }
    if (warningSeg) {
        warningSeg.style.width = `${warningPct}%`;
    }
    if (badSeg) {
        badSeg.style.width = `${badPct}%`;
    }
}

/**
 * Show feedback toast
 */
function showThresholdFeedback(message) {
    let toast = document.getElementById('thresholdToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'thresholdToast';
        toast.style.cssText = 'position: fixed; bottom: 20px; right: 20px; padding: 12px 20px; background: #333; color: white; border-radius: 4px; z-index: 1001;';
        document.body.appendChild(toast);
    }

    toast.textContent = message;
    toast.style.display = 'block';

    setTimeout(() => {
        toast.style.display = 'none';
    }, 2000);
}

/**
 * Open threshold settings modal
 */
function openThresholdModal() {
    const modal = document.getElementById('thresholdModal');
    if (modal) {
        modal.style.display = 'flex';
        // Populate current values when opening
        populateThresholdInputsById();
    }
}

/**
 * Close threshold settings modal
 */
function closeThresholdModal() {
    const modal = document.getElementById('thresholdModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Populate input fields by specific IDs (for simpler template)
 */
function populateThresholdInputsById() {
    const mapping = {
        'thresh-tsnr': 'tsnr_median',
        'thresh-fd': 'fd_median',
        'thresh-dvars': 'dvars_std_median',
        'thresh-coverage': 'coverage'
    };

    Object.entries(mapping).forEach(([inputId, key]) => {
        const input = document.getElementById(inputId);
        if (input && activeThresholds[key] != null) {
            input.value = activeThresholds[key];
        }
    });
}

/**
 * Apply a preset from button click
 */
function applyPreset(presetName) {
    if (THRESHOLD_PRESETS[presetName]) {
        activeThresholds = { ...THRESHOLD_PRESETS[presetName] };
        populateThresholdInputsById();

        // Update preset button styles
        document.querySelectorAll('.preset-btn').forEach(btn => {
            btn.style.background = '#f5f5f5';
            btn.style.color = '#333';
            btn.style.borderColor = '#ddd';
        });

        const activeBtn = document.querySelector(`.preset-btn[onclick*="${presetName}"]`);
        if (activeBtn) {
            activeBtn.style.background = '#eff6ff';
            activeBtn.style.color = '#3b82f6';
            activeBtn.style.borderColor = '#3b82f6';
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initThresholdControls();

    // Close modal when clicking outside
    const modal = document.getElementById('thresholdModal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeThresholdModal();
            }
        });
    }
});

// Export for use in other modules and onclick handlers
window.openThresholdModal = openThresholdModal;
window.closeThresholdModal = closeThresholdModal;
window.applyPreset = applyPreset;
window.applyAndRefresh = applyAndRefresh;
window.resetThresholds = resetThresholds;
window.activeThresholds = activeThresholds;
