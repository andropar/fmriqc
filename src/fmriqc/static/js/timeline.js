/**
 * Inline Metrics Visualization for fMRI QA Reports
 *
 * Renders metrics directly alongside each run card in thumbnail and detail views.
 * Clinical data aesthetic with metric scales and positioned dots.
 */

class InlineMetricsRenderer {
    constructor(data) {
        this.data = data;
        this.selectedMetrics = [...data.default_metrics];
        this.metricConfigs = {};

        // Build metric configs map
        data.available_metrics.forEach(m => {
            this.metricConfigs[m.key] = m;
        });

        // Bind methods
        this.render = this.render.bind(this);
    }

    init() {
        // Initialize metric selector chips
        this.renderMetricSelector();

        // Initial render of inline metrics
        this.render();

        // Listen for view changes (thumbnail <-> detail)
        this.watchViewChanges();
    }

    renderMetricSelector() {
        const chipsContainer = document.getElementById('metric-chips-inline');
        const optionsContainer = document.getElementById('metric-options');

        if (!chipsContainer || !optionsContainer) return;

        // Render chips for selected metrics
        chipsContainer.innerHTML = '';
        this.selectedMetrics.forEach(metricKey => {
            const config = this.metricConfigs[metricKey];
            if (!config) return;

            const chip = document.createElement('div');
            chip.className = 'metric-chip active';
            chip.textContent = config.label;
            chip.onclick = () => this.removeMetric(metricKey);
            chip.title = `Click to remove ${config.label}`;
            chipsContainer.appendChild(chip);
        });

        // Add "+" button to add more metrics
        const addBtn = document.createElement('div');
        addBtn.className = 'metric-chip';
        addBtn.textContent = '+ Add';
        addBtn.onclick = openMetricSelector;
        chipsContainer.appendChild(addBtn);

        // Render options in modal
        optionsContainer.innerHTML = '';
        this.data.available_metrics.forEach(config => {
            const isSelected = this.selectedMetrics.includes(config.key);

            const option = document.createElement('label');
            option.className = 'metric-option';
            option.innerHTML = `
                <input type="checkbox"
                       value="${config.key}"
                       ${isSelected ? 'checked' : ''}
                       onchange="inlineMetrics.toggleMetric('${config.key}', this.checked)">
                <span class="metric-option-label">
                    <strong>${config.label}</strong>
                    ${config.unit ? ` (${config.unit})` : ''}
                    ${config.threshold !== null ?
                        `<br><small>Threshold: ${config.threshold} (${config.direction} is better)</small>` :
                        ''}
                </span>
            `;
            optionsContainer.appendChild(option);
        });
    }

    toggleMetric(metricKey, isSelected) {
        if (isSelected && !this.selectedMetrics.includes(metricKey)) {
            this.selectedMetrics.push(metricKey);
        } else if (!isSelected) {
            this.selectedMetrics = this.selectedMetrics.filter(k => k !== metricKey);
        }

        // Save to localStorage
        localStorage.setItem('inline_metrics_selected', JSON.stringify(this.selectedMetrics));

        // Re-render
        this.renderMetricSelector();
        this.render();
    }

    removeMetric(metricKey) {
        this.selectedMetrics = this.selectedMetrics.filter(k => k !== metricKey);

        // Save to localStorage
        localStorage.setItem('inline_metrics_selected', JSON.stringify(this.selectedMetrics));

        // Re-render
        this.renderMetricSelector();
        this.render();
    }

    render() {
        // Find all run cards
        const runCards = document.querySelectorAll('.run-card-inline');

        runCards.forEach(card => {
            const runId = card.dataset.runId;
            const container = card.querySelector('.metrics-inline-container');

            if (!container) return;

            // Find run data
            const runData = this.findRunData(runId);
            if (!runData) {
                container.innerHTML = '';
                return;
            }

            // Render metrics for this run
            container.innerHTML = '';

            if (this.selectedMetrics.length === 0) {
                container.style.display = 'none';
                return;
            }

            container.style.display = 'flex';

            this.selectedMetrics.forEach(metricKey => {
                const metricColumn = this.createMetricColumn(metricKey, runData);
                if (metricColumn) {
                    container.appendChild(metricColumn);
                }
            });
        });
    }

    findRunData(runId) {
        // Search through sessions for the run
        for (const session of this.data.sessions || []) {
            const run = session.runs.find(r => r.run_id === runId);
            if (run) return run;
        }

        // If data is flat (not nested by sessions)
        if (this.data.runs) {
            return this.data.runs.find(r => r.run_id === runId);
        }

        return null;
    }

    createMetricColumn(metricKey, runData) {
        const config = this.metricConfigs[metricKey];
        if (!config) return null;

        const metricValue = runData.metrics[metricKey];
        if (metricValue === null || metricValue === undefined) return null;

        const column = document.createElement('div');
        column.className = 'metric-column';

        // Label
        const label = document.createElement('div');
        label.className = 'metric-label';
        label.textContent = config.label;
        column.appendChild(label);

        // Visualization box
        const viz = document.createElement('div');
        viz.className = 'metric-viz';

        // Scale with dot
        const scale = document.createElement('div');
        scale.className = 'metric-scale';

        const dot = document.createElement('div');
        dot.className = 'metric-dot';

        // Calculate dot position
        const min = config.min;
        const max = config.max;
        const range = max - min;
        const valuePercent = ((metricValue - min) / range) * 100;
        const clampedPercent = Math.max(0, Math.min(100, valuePercent));

        dot.style.left = `${clampedPercent}%`;

        // Check if outlier
        const isOutlier = this.isOutlier(runData, metricKey, metricValue, config);
        if (isOutlier) {
            dot.classList.add('danger');
            dot.title = `${config.label}: ${metricValue.toFixed(2)} (outlier)`;
        } else {
            dot.title = `${config.label}: ${metricValue.toFixed(2)}`;
        }

        scale.appendChild(dot);
        viz.appendChild(scale);

        // Range labels
        const range_div = document.createElement('div');
        range_div.className = 'metric-range';
        range_div.innerHTML = `<span>${min}</span><span>${max}</span>`;
        viz.appendChild(range_div);

        column.appendChild(viz);

        // Value display
        const value = document.createElement('div');
        value.className = 'metric-value';
        value.textContent = metricValue.toFixed(1);
        column.appendChild(value);

        return column;
    }

    isOutlier(runData, metricKey, metricValue, config) {
        // Check flags
        if (runData.flags) {
            if (metricKey === 'tsnr_median' && runData.flags.low_tsnr) return true;
            if (metricKey === 'fd_median' && runData.flags.high_motion) return true;
            if (metricKey === 'dvars_std_median' && runData.flags.high_dvars) return true;
        }

        // Check threshold
        if (config.threshold !== null) {
            if (config.direction === 'higher' && metricValue < config.threshold) return true;
            if (config.direction === 'lower' && metricValue > config.threshold) return true;
        }

        return false;
    }

    watchViewChanges() {
        // Watch for view changes between thumbnail and detail
        const observer = new MutationObserver(() => {
            // Re-render when view changes
            setTimeout(() => this.render(), 100);
        });

        const thumbnailView = document.getElementById('thumbnail-view');
        const detailView = document.getElementById('detail-view');

        if (thumbnailView) {
            observer.observe(thumbnailView, { attributes: true, attributeFilter: ['class'] });
        }
        if (detailView) {
            observer.observe(detailView, { attributes: true, attributeFilter: ['class'] });
        }
    }
}

// Global instance
let inlineMetrics = null;

// UI Functions
function openMetricSelector() {
    const modal = document.getElementById('metric-modal');
    if (modal) {
        modal.classList.remove('hidden');
    }
}

function closeMetricSelector() {
    const modal = document.getElementById('metric-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Load longitudinal data
    const dataElement = document.getElementById('longitudinal-data');
    if (!dataElement) {
        console.warn('No longitudinal data found');
        return;
    }

    try {
        const data = JSON.parse(dataElement.textContent);

        // Load saved preferences
        const savedMetrics = localStorage.getItem('inline_metrics_selected');
        if (savedMetrics) {
            try {
                data.default_metrics = JSON.parse(savedMetrics);
            } catch (e) {
                console.warn('Failed to parse saved metrics, using defaults');
            }
        }

        // Initialize inline metrics
        inlineMetrics = new InlineMetricsRenderer(data);
        inlineMetrics.init();

    } catch (error) {
        console.error('Failed to initialize inline metrics:', error);
    }
});
