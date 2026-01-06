/**
 * Main initialization and utility functions
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize based on page type
    if (typeof studyData !== 'undefined') {
        initStudyReport();
    } else if (typeof subjectData !== 'undefined') {
        initSubjectReport();
    }
});

/**
 * Study report initialization
 */
function initStudyReport() {
    // Set up metric toggles for distributions
    const toggles = document.querySelectorAll('.metric-toggle');
    toggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            this.classList.toggle('active');
            updateDistributions();
        });
    });

    // Initialize violin plots
    updateDistributions();

    // Initialize scatter plot
    updateScatterPlot();

    // Set up scatter controls
    const scatterControls = document.querySelectorAll('.scatter-controls select');
    scatterControls.forEach(select => {
        select.addEventListener('change', updateScatterPlot);
    });
}

/**
 * Update distribution violin plots based on active toggles
 * Uses grouped box plots when there are multiple subjects
 */
function updateDistributions() {
    const activeMetrics = [];
    document.querySelectorAll('.metric-toggle.active').forEach(toggle => {
        activeMetrics.push(toggle.dataset.metric);
    });

    const grid = document.getElementById('distributions-grid');
    if (!grid) return;

    grid.innerHTML = '';

    // Check if we have multiple subjects - use grouped box plots if so
    const subjects = studyData.subjects || [];
    const useGrouped = subjects.length > 1;

    activeMetrics.forEach(metricKey => {
        const metricInfo = studyData.metricInfo[metricKey];
        if (!metricInfo) return;

        const container = document.createElement('div');
        container.className = 'distribution-plot';
        grid.appendChild(container);

        if (useGrouped && typeof createGroupedBoxPlot === 'function') {
            // Use grouped box plot with subjects on x-axis
            createGroupedBoxPlot(container, studyData.runs, {
                metric: metricKey,
                threshold: metricInfo.threshold,
                thresholdDirection: metricInfo.direction
            });
        } else {
            // Single subject - use simple violin plot
            createViolinPlot(container, studyData.distributions[metricKey] || [], {
                metric: metricInfo.label,
                threshold: metricInfo.threshold,
                thresholdDirection: metricInfo.direction
            });
        }
    });
}

/**
 * Update scatter plot based on selected metrics
 */
function updateScatterPlot() {
    const xMetric = document.getElementById('x-metric')?.value || 'tsnr_median';
    const yMetric = document.getElementById('y-metric')?.value || 'fd_median';
    const colorBy = document.getElementById('color-by')?.value || 'subject';

    const container = document.getElementById('scatter-plot');
    if (!container) return;

    const result = createScatterPlot(container, studyData.runs, {
        xMetric,
        yMetric,
        colorBy,
        onClick: showRunDetails
    });

    // Update legend
    const legend = document.getElementById('scatter-legend');
    if (legend && result) {
        legend.innerHTML = '';
        result.colorGroups.forEach(group => {
            const item = document.createElement('div');
            item.className = 'legend-item';
            item.innerHTML = `<div class="legend-dot" style="background: ${result.colorScale(group)}"></div> ${group}`;
            legend.appendChild(item);
        });
    }
}

// Track current run index for navigation
let currentRunIndex = -1;

/**
 * Show run details in a panel or modal
 */
function showRunDetails(run) {
    const panel = document.getElementById('run-details-panel');
    if (!panel) return;

    // Find index of current run
    const runs = studyData.runs || [];
    currentRunIndex = runs.findIndex(r => r.id === run.id);

    // Update header with navigation
    const headerEl = panel.querySelector('.run-details-header') || createDetailsHeader(panel);
    const titleEl = headerEl.querySelector('.run-details-title');
    if (titleEl) titleEl.textContent = run.id;

    // Update navigation buttons
    updateNavButtons();

    const grid = document.getElementById('run-details-grid');
    grid.innerHTML = '';

    // Show metrics compactly
    Object.entries(run.metrics).forEach(([key, value]) => {
        if (value == null) return;
        const metricInfo = studyData.metricInfo[key] || { label: key };

        const item = document.createElement('div');
        item.className = 'detail-item';

        // Check if flagged
        const isFlagged = run.flags && Object.entries(run.flags).some(([fk, fv]) =>
            fv && fk.toLowerCase().includes(key.split('_')[0].toLowerCase())
        );
        if (isFlagged) item.classList.add('flagged');

        item.innerHTML = `
            <span class="label">${metricInfo.label}</span>
            <span class="value">${typeof value === 'number' ? value.toFixed(3) : value}</span>
        `;
        grid.appendChild(item);
    });

    // Show flags compactly if any
    if (run.flags) {
        const activeFlags = Object.entries(run.flags).filter(([k, v]) => v);
        if (activeFlags.length > 0) {
            const flagsItem = document.createElement('div');
            flagsItem.className = 'detail-item flagged';
            flagsItem.style.gridColumn = '1 / -1';
            flagsItem.innerHTML = `
                <span class="label">Flags</span>
                <span class="value">${activeFlags.map(([k]) => k).join(', ')}</span>
            `;
            grid.appendChild(flagsItem);
        }
    }

    panel.classList.add('active');
}

/**
 * Create the details header with navigation buttons
 */
function createDetailsHeader(panel) {
    const header = document.createElement('div');
    header.className = 'run-details-header';
    header.innerHTML = `
        <h4 class="run-details-title"></h4>
        <div class="run-nav-buttons">
            <button class="run-nav-btn" onclick="navigateRun(-1)" title="Previous run (←)">←</button>
            <button class="run-nav-btn" onclick="navigateRun(1)" title="Next run (→)">→</button>
        </div>
    `;

    // Insert header before the grid
    const grid = document.getElementById('run-details-grid');
    panel.insertBefore(header, grid);
    return header;
}

/**
 * Update navigation button states
 */
function updateNavButtons() {
    const runs = studyData.runs || [];
    const prevBtn = document.querySelector('.run-nav-buttons .run-nav-btn:first-child');
    const nextBtn = document.querySelector('.run-nav-buttons .run-nav-btn:last-child');

    if (prevBtn) prevBtn.disabled = currentRunIndex <= 0;
    if (nextBtn) nextBtn.disabled = currentRunIndex >= runs.length - 1;
}

/**
 * Navigate to previous/next run
 */
function navigateRun(direction) {
    const runs = studyData.runs || [];
    const newIndex = currentRunIndex + direction;

    if (newIndex >= 0 && newIndex < runs.length) {
        showRunDetails(runs[newIndex]);
    }
}

/**
 * Close details panel
 */
function closeDetailsPanel() {
    const panel = document.getElementById('run-details-panel');
    if (panel) panel.classList.remove('active');
    currentRunIndex = -1;
}

// Keyboard navigation for run details
document.addEventListener('keydown', function(e) {
    if (currentRunIndex === -1) return;
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

    if (e.key === 'ArrowLeft') {
        e.preventDefault();
        navigateRun(-1);
    } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        navigateRun(1);
    } else if (e.key === 'Escape') {
        closeDetailsPanel();
    }
});

/**
 * Subject report initialization
 */
function initSubjectReport() {
    // Load thumbnails into rows
    loadRowThumbnails();

    // Initialize timeline
    updateTimeline();

    // Set up metric toggles
    const toggles = document.querySelectorAll('.metric-toggle');
    toggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            this.classList.toggle('active');
            updateTimeline();
        });
    });

    // Initialize review system
    initReviewSystem();
}

/**
 * Load thumbnails into table rows
 */
function loadRowThumbnails() {
    document.querySelectorAll('.row-thumbnail').forEach(img => {
        const runId = img.dataset.runId;
        const run = subjectData.runs.find(r => r.id === runId);
        if (run && run.thumbnailPath) {
            img.src = run.thumbnailPath;
            img.alt = runId;
        } else {
            // Hide if no thumbnail
            img.style.display = 'none';
        }
    });
}

/**
 * Update the vertical timeline visualization
 */
function updateTimeline() {
    const activeMetrics = [];
    document.querySelectorAll('.metric-toggle.active').forEach(toggle => {
        const key = toggle.dataset.metric;
        const metricInfo = subjectData.metricInfo[key];
        if (metricInfo) {
            activeMetrics.push(metricInfo);
        }
    });

    // Get actual dimensions from the table
    const tableRows = document.querySelectorAll('.run-info-table tbody tr');
    const tableHead = document.querySelector('.run-info-table thead');
    const rowHeight = tableRows.length > 0 ? tableRows[0].offsetHeight : 45;
    const theadHeight = tableHead ? tableHead.offsetHeight : 35;

    // Update timeline visualization
    const container = document.getElementById('timeline-viz');
    if (container && activeMetrics.length > 0) {
        createVerticalTimeline(container, subjectData.runs, activeMetrics, {
            rowHeight: rowHeight,
            minColWidth: 130,
            maxColWidth: 280,
            headerHeight: theadHeight,  // Match table header height
            axisHeight: 28
        });
    } else if (container) {
        container.innerHTML = '<div style="padding: 2rem; color: #94a3b8; text-align: center;">Select metrics above to view timeline</div>';
    }
}

// Modal handling
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add('active');
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('active');
}

// Close modal on overlay click
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
    }
});

// Close modal on escape
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(modal => {
            modal.classList.remove('active');
        });
    }
});
