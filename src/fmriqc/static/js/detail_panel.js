/**
 * Detail Panel - Two-panel view with navigation and timeline visualization
 *
 * Left panel: Session/run navigation tree
 * Right panel: SVG timeline of per-volume metrics
 */

class DetailPanelController {
    constructor() {
        this.seriesData = {};  // Cache for loaded series data
        this.activeMetrics = ['fd', 'dvars_std'];  // Currently displayed metrics
        this.selectedRun = null;
        this.expandedSessions = new Set();
        this.sessionRunsData = null;  // Data from embedded JSON

        // Metric configuration
        this.metricConfig = {
            fd: {
                label: 'FD',
                color: '#e74c3c',
                unit: 'mm',
                threshold: 0.5
            },
            dvars_std: {
                label: 'DVARS',
                color: '#3498db',
                unit: '',
                threshold: 1.5
            },
            global_signal: {
                label: 'Global Signal',
                color: '#9b59b6',
                unit: 'a.u.',
                threshold: null
            },
            outlier_fraction: {
                label: 'Outlier %',
                color: '#f39c12',
                unit: '%',
                threshold: 0.1
            }
        };

        // Chart margins
        this.margin = { top: 20, right: 30, bottom: 40, left: 50 };
    }

    init() {
        // Load embedded session data
        const dataEl = document.getElementById('series-paths-data');
        if (dataEl) {
            try {
                this.sessionRunsData = JSON.parse(dataEl.textContent);
            } catch (e) {
                console.error('Failed to parse series paths data:', e);
            }
        }

        // Set up event listeners
        this.bindEvents();
    }

    bindEvents() {
        // Close modal on escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeCarpetModal();
            }
        });
    }

    // Session navigation toggle
    toggleSession(sessionId) {
        const sessionEl = document.querySelector(`.nav-session[data-session-id="${sessionId}"]`);
        if (!sessionEl) return;

        const header = sessionEl.querySelector('.nav-session-header');
        const isExpanded = sessionEl.classList.contains('expanded');

        if (isExpanded) {
            sessionEl.classList.remove('expanded');
            header.classList.remove('expanded');
            this.expandedSessions.delete(sessionId);
            // Show session summary view
            this.showSessionSummary(sessionId);
        } else {
            sessionEl.classList.add('expanded');
            header.classList.add('expanded');
            this.expandedSessions.add(sessionId);
            // Load and show session timeline
            this.loadSessionTimeline(sessionId);
        }
    }

    // Select a specific run
    selectRun(runId, sessionId) {
        // Update selection UI
        document.querySelectorAll('.nav-run').forEach(el => {
            el.classList.remove('selected');
        });
        const runEl = document.querySelector(`.nav-run[data-run-id="${runId}"]`);
        if (runEl) {
            runEl.classList.add('selected');
        }

        this.selectedRun = runId;

        // Make sure session is expanded
        if (!this.expandedSessions.has(sessionId)) {
            this.toggleSession(sessionId);
        }

        // Load run timeline
        this.loadRunTimeline(runId);
    }

    // Show session summary (run-level metrics as dots/bars)
    showSessionSummary(sessionId) {
        const vizTitle = document.getElementById('viz-title');
        const vizEmpty = document.getElementById('viz-empty');
        const svg = document.getElementById('timeline-svg');

        if (vizTitle) {
            const sessionLabel = sessionId.split('_').pop();
            vizTitle.textContent = `${sessionLabel} - Run Summary`;
        }

        // Find session data
        const sessionData = this.findSessionData(sessionId);
        if (!sessionData || sessionData.runs.length === 0) {
            if (vizEmpty) vizEmpty.style.display = 'flex';
            if (svg) svg.style.display = 'none';
            return;
        }

        // Render run summary view
        this.renderRunSummaryChart(sessionData);
    }

    // Find session data from embedded JSON
    findSessionData(sessionId) {
        if (!this.sessionRunsData) return null;
        return this.sessionRunsData.sessions.find(s => s.session_id === sessionId);
    }

    // Find run data from embedded JSON
    findRunData(runId) {
        if (!this.sessionRunsData) return null;
        for (const session of this.sessionRunsData.sessions) {
            const run = session.runs.find(r => r.run_id === runId);
            if (run) return { run, session };
        }
        return null;
    }

    // Load and display timeline for an expanded session
    async loadSessionTimeline(sessionId) {
        const vizTitle = document.getElementById('viz-title');
        const vizEmpty = document.getElementById('viz-empty');

        const sessionData = this.findSessionData(sessionId);
        if (!sessionData) return;

        if (vizTitle) {
            vizTitle.textContent = `${sessionData.session_label} - Per-Volume Metrics`;
        }

        // Load series data for all runs in session
        const seriesPromises = sessionData.runs.map(run =>
            this.loadSeriesData(run.run_id, run.series_path)
        );

        try {
            await Promise.all(seriesPromises);
            // Render continuous timeline across all runs
            this.renderSessionTimeline(sessionData);
        } catch (e) {
            console.error('Failed to load session timeline:', e);
            if (vizEmpty) {
                vizEmpty.style.display = 'flex';
                vizEmpty.innerHTML = `
                    <div class="detail-viz-empty-icon">⚠️</div>
                    <p>Failed to load timeline data</p>
                `;
            }
        }
    }

    // Load and display timeline for a single run
    async loadRunTimeline(runId) {
        const vizTitle = document.getElementById('viz-title');
        const data = this.findRunData(runId);

        if (!data) return;

        if (vizTitle) {
            vizTitle.textContent = `${data.session.session_label} / ${data.run.run_label}`;
        }

        try {
            await this.loadSeriesData(runId, data.run.series_path);
            this.renderRunTimeline(runId);
        } catch (e) {
            console.error('Failed to load run timeline:', e);
        }
    }

    // Fetch series.json for a run
    async loadSeriesData(runId, seriesPath) {
        if (this.seriesData[runId]) {
            return this.seriesData[runId];
        }

        if (!seriesPath) {
            this.seriesData[runId] = null;
            return null;
        }

        try {
            const response = await fetch(seriesPath);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            this.seriesData[runId] = data;
            return data;
        } catch (e) {
            console.warn(`Failed to load series for ${runId}:`, e);
            this.seriesData[runId] = null;
            return null;
        }
    }

    // Render run summary chart (dots showing metric values per run)
    renderRunSummaryChart(sessionData) {
        const container = document.getElementById('timeline-container');
        const vizEmpty = document.getElementById('viz-empty');
        const svg = document.getElementById('timeline-svg');

        if (vizEmpty) vizEmpty.style.display = 'none';
        if (svg) svg.style.display = 'block';

        const width = container.clientWidth;
        const height = container.clientHeight || 400;
        const chartWidth = width - this.margin.left - this.margin.right;
        const chartHeight = height - this.margin.top - this.margin.bottom;

        // Build SVG
        let svgContent = `
            <g transform="translate(${this.margin.left}, ${this.margin.top})">
        `;

        const runs = sessionData.runs;
        const runWidth = chartWidth / runs.length;

        // For each active metric, draw dots
        this.activeMetrics.forEach((metricKey, metricIdx) => {
            const config = this.metricConfig[metricKey];
            if (!config) return;

            // Get values and compute scale
            const values = runs.map(r => {
                const key = metricKey === 'dvars_std' ? 'dvars_std_median' : `${metricKey}_median`;
                return r.metrics[key] || 0;
            });

            const maxVal = Math.max(...values, config.threshold || 0) * 1.2;
            const minVal = 0;

            runs.forEach((run, i) => {
                const val = values[i];
                const x = i * runWidth + runWidth / 2;
                const y = chartHeight - ((val - minVal) / (maxVal - minVal)) * chartHeight;

                const isAboveThreshold = config.threshold && val > config.threshold;

                svgContent += `
                    <circle
                        cx="${x}"
                        cy="${y}"
                        r="6"
                        fill="${isAboveThreshold ? config.color : config.color + '80'}"
                        stroke="${config.color}"
                        stroke-width="2"
                        data-run="${run.run_id}"
                        style="cursor: pointer;"
                    />
                `;
            });

            // Add threshold line if exists
            if (config.threshold) {
                const threshY = chartHeight - ((config.threshold - minVal) / (maxVal - minVal)) * chartHeight;
                svgContent += `
                    <line
                        x1="0" y1="${threshY}"
                        x2="${chartWidth}" y2="${threshY}"
                        class="threshold-line ${metricKey.replace('_', '-')}"
                    />
                `;
            }
        });

        // X-axis labels (run names)
        runs.forEach((run, i) => {
            const x = i * runWidth + runWidth / 2;
            svgContent += `
                <text
                    x="${x}"
                    y="${chartHeight + 25}"
                    text-anchor="middle"
                    class="timeline-axis"
                >${run.run_label}</text>
            `;
        });

        svgContent += '</g>';

        svg.innerHTML = svgContent;
        svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    }

    // Render continuous timeline for all runs in a session
    renderSessionTimeline(sessionData) {
        const container = document.getElementById('timeline-container');
        const vizEmpty = document.getElementById('viz-empty');
        const svg = document.getElementById('timeline-svg');

        if (vizEmpty) vizEmpty.style.display = 'none';
        if (svg) svg.style.display = 'block';

        const width = container.clientWidth;
        const height = container.clientHeight || 400;
        const chartWidth = width - this.margin.left - this.margin.right;
        const chartHeight = height - this.margin.top - this.margin.bottom;

        // Concatenate all series data
        const allData = [];
        const runBoundaries = [];
        let totalVolumes = 0;

        for (const run of sessionData.runs) {
            const series = this.seriesData[run.run_id];
            if (!series || !series.series) continue;

            runBoundaries.push({
                startIdx: totalVolumes,
                label: run.run_label,
                runId: run.run_id
            });

            const nVols = series.n_volumes || Object.values(series.series)[0]?.length || 0;
            for (let i = 0; i < nVols; i++) {
                const point = { idx: totalVolumes + i, run: run.run_id };
                this.activeMetrics.forEach(key => {
                    point[key] = series.series[key]?.[i] ?? null;
                });
                allData.push(point);
            }
            totalVolumes += nVols;
        }

        if (allData.length === 0) {
            if (vizEmpty) {
                vizEmpty.style.display = 'flex';
                vizEmpty.innerHTML = `
                    <div class="detail-viz-empty-icon">📊</div>
                    <p>No time series data available</p>
                `;
            }
            if (svg) svg.style.display = 'none';
            return;
        }

        // Render SVG
        this.renderTimelineSVG(svg, allData, runBoundaries, chartWidth, chartHeight, width, height);
    }

    // Render timeline for a single run
    renderRunTimeline(runId) {
        const container = document.getElementById('timeline-container');
        const vizEmpty = document.getElementById('viz-empty');
        const svg = document.getElementById('timeline-svg');

        const series = this.seriesData[runId];
        if (!series || !series.series) {
            if (vizEmpty) {
                vizEmpty.style.display = 'flex';
                vizEmpty.innerHTML = `
                    <div class="detail-viz-empty-icon">📊</div>
                    <p>No time series data available for this run</p>
                `;
            }
            if (svg) svg.style.display = 'none';
            return;
        }

        if (vizEmpty) vizEmpty.style.display = 'none';
        if (svg) svg.style.display = 'block';

        const width = container.clientWidth;
        const height = container.clientHeight || 400;
        const chartWidth = width - this.margin.left - this.margin.right;
        const chartHeight = height - this.margin.top - this.margin.bottom;

        // Build data array
        const nVols = series.n_volumes || Object.values(series.series)[0]?.length || 0;
        const allData = [];
        for (let i = 0; i < nVols; i++) {
            const point = { idx: i, run: runId };
            this.activeMetrics.forEach(key => {
                point[key] = series.series[key]?.[i] ?? null;
            });
            allData.push(point);
        }

        this.renderTimelineSVG(svg, allData, [], chartWidth, chartHeight, width, height);
    }

    // Core SVG rendering for timeline
    renderTimelineSVG(svg, data, runBoundaries, chartWidth, chartHeight, width, height) {
        const xScale = (idx) => (idx / (data.length - 1)) * chartWidth;
        const margin = this.margin;

        let svgContent = `<g transform="translate(${margin.left}, ${margin.top})">`;

        // Draw each active metric
        this.activeMetrics.forEach((metricKey, metricIdx) => {
            const config = this.metricConfig[metricKey];
            if (!config) return;

            // Get min/max for this metric
            const values = data.map(d => d[metricKey]).filter(v => v !== null);
            if (values.length === 0) return;

            let maxVal = Math.max(...values);
            let minVal = Math.min(...values);

            // Include threshold in range if present
            if (config.threshold) {
                maxVal = Math.max(maxVal, config.threshold * 1.2);
            }

            // Add padding
            const range = maxVal - minVal;
            maxVal += range * 0.1;
            minVal = Math.max(0, minVal - range * 0.05);

            const yScale = (val) => chartHeight - ((val - minVal) / (maxVal - minVal)) * chartHeight;

            // Build path
            let pathD = '';
            let areaD = '';
            let isFirst = true;

            data.forEach((d, i) => {
                const val = d[metricKey];
                if (val === null) return;

                const x = xScale(i);
                const y = yScale(val);

                if (isFirst) {
                    pathD = `M ${x} ${y}`;
                    areaD = `M ${x} ${chartHeight} L ${x} ${y}`;
                    isFirst = false;
                } else {
                    pathD += ` L ${x} ${y}`;
                    areaD += ` L ${x} ${y}`;
                }
            });

            if (areaD) {
                areaD += ` L ${xScale(data.length - 1)} ${chartHeight} Z`;
            }

            // Area fill
            svgContent += `<path class="timeline-area ${metricKey.replace('_', '-')}" d="${areaD}" />`;

            // Line
            svgContent += `<path class="timeline-line ${metricKey.replace('_', '-')}" d="${pathD}" />`;

            // Threshold line
            if (config.threshold && config.threshold >= minVal && config.threshold <= maxVal) {
                const threshY = yScale(config.threshold);
                svgContent += `
                    <line
                        x1="0" y1="${threshY}"
                        x2="${chartWidth}" y2="${threshY}"
                        class="threshold-line ${metricKey.replace('_', '-')}"
                    />
                    <text x="${chartWidth + 5}" y="${threshY + 4}" class="timeline-axis" font-size="9">
                        ${config.threshold}
                    </text>
                `;
            }
        });

        // Run boundaries
        runBoundaries.forEach((boundary, i) => {
            if (i === 0) return; // Skip first boundary
            const x = xScale(boundary.startIdx);
            svgContent += `
                <line
                    x1="${x}" y1="0"
                    x2="${x}" y2="${chartHeight}"
                    class="run-boundary"
                />
                <text
                    x="${x}"
                    y="-5"
                    class="run-boundary-label"
                >${boundary.label}</text>
            `;
        });

        // X-axis
        svgContent += `
            <line x1="0" y1="${chartHeight}" x2="${chartWidth}" y2="${chartHeight}" stroke="var(--border)" />
            <text x="${chartWidth / 2}" y="${chartHeight + 35}" class="timeline-axis" text-anchor="middle">Volume</text>
        `;

        // Y-axis
        svgContent += `
            <line x1="0" y1="0" x2="0" y2="${chartHeight}" stroke="var(--border)" />
        `;

        svgContent += '</g>';

        svg.innerHTML = svgContent;
        svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    }

    // Toggle metric visibility
    toggleMetric(metricKey) {
        const btn = document.querySelector(`.metric-toggle[data-metric="${metricKey}"]`);
        const idx = this.activeMetrics.indexOf(metricKey);

        if (idx >= 0) {
            this.activeMetrics.splice(idx, 1);
            if (btn) btn.classList.remove('active');
        } else {
            this.activeMetrics.push(metricKey);
            if (btn) btn.classList.add('active');
        }

        // Re-render current view
        this.refreshTimeline();
    }

    // Refresh the current timeline view
    refreshTimeline() {
        if (this.selectedRun) {
            this.renderRunTimeline(this.selectedRun);
        } else if (this.expandedSessions.size > 0) {
            const sessionId = Array.from(this.expandedSessions)[0];
            const sessionData = this.findSessionData(sessionId);
            if (sessionData) {
                this.renderSessionTimeline(sessionData);
            }
        }
    }

    // Open carpet plot modal
    openCarpetModal(runId) {
        const data = this.findRunData(runId);
        if (!data || !data.run.carpet_path) return;

        const modal = document.getElementById('carpet-modal');
        const title = document.getElementById('carpet-modal-title');
        const img = document.getElementById('carpet-modal-img');

        if (title) {
            title.textContent = `${data.session.session_label} / ${data.run.run_label} - Carpet Plot`;
        }
        if (img) {
            img.src = data.run.carpet_path;
        }
        if (modal) {
            modal.classList.add('visible');
        }
    }

    closeCarpetModal(event) {
        if (event && event.target !== event.currentTarget) return;
        const modal = document.getElementById('carpet-modal');
        if (modal) {
            modal.classList.remove('visible');
        }
    }
}

// Global instance
let detailPanel = null;

// Global functions for onclick handlers
function toggleNavSession(sessionId) {
    if (detailPanel) detailPanel.toggleSession(sessionId);
}

function selectRun(runId, sessionId) {
    if (detailPanel) detailPanel.selectRun(runId, sessionId);
}

function toggleMetric(metricKey) {
    if (detailPanel) detailPanel.toggleMetric(metricKey);
}

function openCarpetModal(runId) {
    if (detailPanel) detailPanel.openCarpetModal(runId);
}

function closeCarpetModal(event) {
    if (detailPanel) detailPanel.closeCarpetModal(event);
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    detailPanel = new DetailPanelController();
    detailPanel.init();
});
