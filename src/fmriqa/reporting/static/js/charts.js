/**
 * D3.js chart components for fmriqa reports
 */

// Color palette for subjects/sessions
const colorPalette = [
    '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6',
    '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16'
];

/**
 * Create a simple box plot with individual data points
 * Cleaner alternative to violin plots
 * Now responsive to container size
 */
function createViolinPlot(container, data, config) {
    const {
        width = 180,
        height = 220,
        margin = { top: 35, right: 15, bottom: 35, left: 45 },
        metric,
        threshold = null,
        thresholdDirection = 'lower'  // 'lower' means values below threshold are bad
    } = config;

    // Clear previous
    d3.select(container).selectAll('*').remove();

    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .style('overflow', 'visible');

    const g = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

    // Filter valid data
    const values = data.filter(d => d != null && !isNaN(d));
    if (values.length === 0) {
        g.append('text')
            .attr('x', innerWidth / 2)
            .attr('y', innerHeight / 2)
            .attr('text-anchor', 'middle')
            .attr('fill', '#999')
            .attr('font-size', '12px')
            .text('No data');
        return;
    }

    // Compute statistics
    const sorted = [...values].sort((a, b) => a - b);
    const min = d3.min(values);
    const max = d3.max(values);
    const q1 = d3.quantile(sorted, 0.25);
    const median = d3.quantile(sorted, 0.5);
    const q3 = d3.quantile(sorted, 0.75);
    const iqr = q3 - q1;
    const lowerWhisker = Math.max(min, q1 - 1.5 * iqr);
    const upperWhisker = Math.min(max, q3 + 1.5 * iqr);

    // Y scale with padding
    const yPadding = (max - min) * 0.15 || 0.1;
    const yScale = d3.scaleLinear()
        .domain([min - yPadding, max + yPadding])
        .range([innerHeight, 0]);

    // Center X position
    const centerX = innerWidth / 2;
    const boxWidth = 30;

    // Draw threshold zone if provided
    if (threshold != null) {
        const threshY = yScale(threshold);
        if (threshY >= 0 && threshY <= innerHeight) {
            // Shade the "bad" zone
            const badZoneY = thresholdDirection === 'lower' ? threshY : 0;
            const badZoneHeight = thresholdDirection === 'lower' ? innerHeight - threshY : threshY;

            g.append('rect')
                .attr('x', 0)
                .attr('y', badZoneY)
                .attr('width', innerWidth)
                .attr('height', badZoneHeight)
                .attr('fill', '#fef2f2')
                .attr('opacity', 0.5);

            // Threshold line
            g.append('line')
                .attr('x1', 0)
                .attr('x2', innerWidth)
                .attr('y1', threshY)
                .attr('y2', threshY)
                .attr('stroke', '#ef4444')
                .attr('stroke-width', 1.5)
                .attr('stroke-dasharray', '4,3');

            // Threshold label
            g.append('text')
                .attr('x', innerWidth)
                .attr('y', threshY - 4)
                .attr('text-anchor', 'end')
                .attr('font-size', '9px')
                .attr('fill', '#ef4444')
                .text(threshold);
        }
    }

    // Draw whiskers
    g.append('line')
        .attr('x1', centerX)
        .attr('x2', centerX)
        .attr('y1', yScale(lowerWhisker))
        .attr('y2', yScale(upperWhisker))
        .attr('stroke', '#94a3b8')
        .attr('stroke-width', 1);

    // Whisker caps
    g.append('line')
        .attr('x1', centerX - 8)
        .attr('x2', centerX + 8)
        .attr('y1', yScale(lowerWhisker))
        .attr('y2', yScale(lowerWhisker))
        .attr('stroke', '#94a3b8')
        .attr('stroke-width', 1);

    g.append('line')
        .attr('x1', centerX - 8)
        .attr('x2', centerX + 8)
        .attr('y1', yScale(upperWhisker))
        .attr('y2', yScale(upperWhisker))
        .attr('stroke', '#94a3b8')
        .attr('stroke-width', 1);

    // Draw box
    g.append('rect')
        .attr('x', centerX - boxWidth / 2)
        .attr('y', yScale(q3))
        .attr('width', boxWidth)
        .attr('height', yScale(q1) - yScale(q3))
        .attr('fill', '#e0f2fe')
        .attr('stroke', '#3b82f6')
        .attr('stroke-width', 1.5)
        .attr('rx', 2);

    // Median line
    g.append('line')
        .attr('x1', centerX - boxWidth / 2)
        .attr('x2', centerX + boxWidth / 2)
        .attr('y1', yScale(median))
        .attr('y2', yScale(median))
        .attr('stroke', '#1d4ed8')
        .attr('stroke-width', 2);

    // Individual points with jitter
    const jitterWidth = 20;
    g.selectAll('.point')
        .data(values)
        .enter()
        .append('circle')
        .attr('class', 'point')
        .attr('cx', () => centerX + (Math.random() - 0.5) * jitterWidth)
        .attr('cy', d => yScale(d))
        .attr('r', 4)
        .attr('fill', d => {
            if (threshold == null) return '#3b82f6';
            const isBad = thresholdDirection === 'lower' ? d < threshold : d > threshold;
            return isBad ? '#ef4444' : '#3b82f6';
        })
        .attr('stroke', '#fff')
        .attr('stroke-width', 1)
        .attr('opacity', 0.8)
        .style('cursor', 'pointer')
        .on('mouseover', function(event, d) {
            d3.select(this).attr('r', 6).attr('opacity', 1);
            showTooltip(event, `${d.toFixed(3)}`);
        })
        .on('mouseout', function() {
            d3.select(this).attr('r', 4).attr('opacity', 0.8);
            hideTooltip();
        });

    // Y axis
    const yAxis = d3.axisLeft(yScale)
        .ticks(5)
        .tickSize(-innerWidth)
        .tickFormat(d => d.toFixed(1));

    g.append('g')
        .attr('class', 'y-axis')
        .call(yAxis)
        .call(g => g.select('.domain').remove())
        .call(g => g.selectAll('.tick line')
            .attr('stroke', '#e5e7eb')
            .attr('stroke-dasharray', '2,2'))
        .call(g => g.selectAll('.tick text')
            .attr('font-size', '10px')
            .attr('fill', '#64748b'));

    // Title
    svg.append('text')
        .attr('x', width / 2)
        .attr('y', 16)
        .attr('text-anchor', 'middle')
        .attr('font-size', '12px')
        .attr('font-weight', '600')
        .attr('fill', '#1e293b')
        .text(metric);

    // Stats below
    svg.append('text')
        .attr('x', width / 2)
        .attr('y', height - 8)
        .attr('text-anchor', 'middle')
        .attr('font-size', '10px')
        .attr('fill', '#64748b')
        .text(`median: ${median.toFixed(2)}, n=${values.length}`);
}

/**
 * Create an interactive scatter plot - responsive to container
 */
function createScatterPlot(container, data, config) {
    const {
        xMetric,
        yMetric,
        colorBy = 'subject',
        onClick = null
    } = config;

    // Clear previous
    d3.select(container).selectAll('*').remove();

    // Get container dimensions
    const containerRect = container.getBoundingClientRect();
    const width = containerRect.width || 500;
    const height = Math.max(300, containerRect.height || 350);
    const margin = { top: 20, right: 30, bottom: 50, left: 60 };

    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(container)
        .append('svg')
        .attr('width', '100%')
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMidYMid meet');

    const g = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

    // Filter valid data
    const validData = data.filter(d =>
        d.metrics[xMetric] != null &&
        d.metrics[yMetric] != null &&
        !isNaN(d.metrics[xMetric]) &&
        !isNaN(d.metrics[yMetric])
    );

    if (validData.length === 0) {
        g.append('text')
            .attr('x', innerWidth / 2)
            .attr('y', innerHeight / 2)
            .attr('text-anchor', 'middle')
            .attr('fill', '#999')
            .text('No data available');
        return { colorScale: null, colorGroups: [] };
    }

    // Scales
    const xExtent = d3.extent(validData, d => d.metrics[xMetric]);
    const yExtent = d3.extent(validData, d => d.metrics[yMetric]);
    const xPadding = (xExtent[1] - xExtent[0]) * 0.1 || 0.1;
    const yPadding = (yExtent[1] - yExtent[0]) * 0.1 || 0.1;

    const xScale = d3.scaleLinear()
        .domain([xExtent[0] - xPadding, xExtent[1] + xPadding])
        .range([0, innerWidth]);

    const yScale = d3.scaleLinear()
        .domain([yExtent[0] - yPadding, yExtent[1] + yPadding])
        .range([innerHeight, 0]);

    // Color scale
    const colorGroups = [...new Set(validData.map(d => d[colorBy]))].sort();
    const colorScale = d3.scaleOrdinal()
        .domain(colorGroups)
        .range(colorPalette);

    // Grid lines
    g.append('g')
        .attr('class', 'grid')
        .selectAll('line.h')
        .data(yScale.ticks(6))
        .enter()
        .append('line')
        .attr('x1', 0)
        .attr('x2', innerWidth)
        .attr('y1', d => yScale(d))
        .attr('y2', d => yScale(d))
        .attr('stroke', '#e5e7eb')
        .attr('stroke-dasharray', '2,2');

    g.append('g')
        .attr('class', 'grid')
        .selectAll('line.v')
        .data(xScale.ticks(6))
        .enter()
        .append('line')
        .attr('x1', d => xScale(d))
        .attr('x2', d => xScale(d))
        .attr('y1', 0)
        .attr('y2', innerHeight)
        .attr('stroke', '#e5e7eb')
        .attr('stroke-dasharray', '2,2');

    // Points
    g.selectAll('.point')
        .data(validData)
        .enter()
        .append('circle')
        .attr('class', 'point')
        .attr('cx', d => xScale(d.metrics[xMetric]))
        .attr('cy', d => yScale(d.metrics[yMetric]))
        .attr('r', 7)
        .attr('fill', d => colorScale(d[colorBy]))
        .attr('stroke', '#fff')
        .attr('stroke-width', 1.5)
        .attr('cursor', onClick ? 'pointer' : 'default')
        .attr('opacity', 0.85)
        .on('mouseover', function(event, d) {
            d3.select(this).attr('r', 10).attr('opacity', 1);
            showTooltip(event, `<strong>${d.id}</strong><br>${xMetric}: ${d.metrics[xMetric].toFixed(3)}<br>${yMetric}: ${d.metrics[yMetric].toFixed(3)}`);
        })
        .on('mouseout', function() {
            d3.select(this).attr('r', 7).attr('opacity', 0.85);
            hideTooltip();
        })
        .on('click', function(event, d) {
            if (onClick) onClick(d);
        });

    // X Axis
    g.append('g')
        .attr('transform', `translate(0,${innerHeight})`)
        .call(d3.axisBottom(xScale).ticks(6))
        .call(g => g.select('.domain').attr('stroke', '#cbd5e1'))
        .call(g => g.selectAll('.tick line').attr('stroke', '#cbd5e1'))
        .call(g => g.selectAll('.tick text').attr('fill', '#64748b').attr('font-size', '11px'));

    // Y Axis
    g.append('g')
        .call(d3.axisLeft(yScale).ticks(6))
        .call(g => g.select('.domain').attr('stroke', '#cbd5e1'))
        .call(g => g.selectAll('.tick line').attr('stroke', '#cbd5e1'))
        .call(g => g.selectAll('.tick text').attr('fill', '#64748b').attr('font-size', '11px'));

    // Axis labels
    svg.append('text')
        .attr('x', margin.left + innerWidth / 2)
        .attr('y', height - 8)
        .attr('text-anchor', 'middle')
        .attr('font-size', '12px')
        .attr('fill', '#64748b')
        .text(xMetric);

    svg.append('text')
        .attr('transform', 'rotate(-90)')
        .attr('x', -(margin.top + innerHeight / 2))
        .attr('y', 16)
        .attr('text-anchor', 'middle')
        .attr('font-size', '12px')
        .attr('fill', '#64748b')
        .text(yMetric);

    return { colorScale, colorGroups };
}

/**
 * Create vertical timeline with connected dots - properly column-aligned
 * Now includes integrated header in SVG for perfect alignment
 * Columns expand to fill available container width
 */
function createVerticalTimeline(container, runs, metrics, config = {}) {
    const {
        rowHeight = 45,
        minColWidth = 120,
        maxColWidth = 250,
        headerHeight = 30,
        axisHeight = 25,
        margin = { left: 12, right: 12 }
    } = config;

    // Clear previous
    d3.select(container).selectAll('*').remove();

    if (metrics.length === 0 || runs.length === 0) return { colWidth: minColWidth, headerHeight };

    // Get container width and calculate dynamic column width
    const containerWidth = container.getBoundingClientRect().width || 600;
    const naturalColWidth = containerWidth / metrics.length;
    const colWidth = Math.max(minColWidth, Math.min(maxColWidth, naturalColWidth));
    const width = metrics.length * colWidth;

    const contentHeight = runs.length * rowHeight;
    const totalHeight = headerHeight + contentHeight + axisHeight;

    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', totalHeight);

    // For each metric column
    metrics.forEach((metric, colIndex) => {
        const colLeft = colIndex * colWidth;
        const plotLeft = colLeft + margin.left;
        const plotRight = colLeft + colWidth - margin.right;
        const plotWidth = plotRight - plotLeft;

        // Get values for this metric
        const values = runs.map(r => r.metrics[metric.key]).filter(v => v != null && !isNaN(v));

        if (values.length === 0) return;

        // Compute range with padding - handle case where all values are same
        const minVal = d3.min(values);
        const maxVal = d3.max(values);
        const range = maxVal - minVal;
        const padding = range > 0 ? range * 0.15 : Math.abs(maxVal) * 0.1 || 0.1;

        // X scale for this metric (horizontal position within column)
        const xScale = d3.scaleLinear()
            .domain([minVal - padding, maxVal + padding])
            .range([plotLeft, plotRight]);

        // Create column group
        const colGroup = svg.append('g')
            .attr('class', `metric-col-${colIndex}`);

        // Draw column background (alternating)
        colGroup.append('rect')
            .attr('x', colLeft)
            .attr('y', headerHeight)
            .attr('width', colWidth)
            .attr('height', contentHeight + axisHeight)
            .attr('fill', colIndex % 2 === 0 ? '#fafafa' : '#ffffff');

        // Draw column border
        colGroup.append('rect')
            .attr('x', colLeft)
            .attr('y', 0)
            .attr('width', colWidth)
            .attr('height', totalHeight)
            .attr('fill', 'none')
            .attr('stroke', '#e5e7eb')
            .attr('stroke-width', 0.5);

        // Draw header label
        colGroup.append('text')
            .attr('x', colLeft + colWidth / 2)
            .attr('y', headerHeight / 2 + 3)
            .attr('text-anchor', 'middle')
            .attr('font-size', '10px')
            .attr('font-weight', '500')
            .attr('fill', '#64748b')
            .text(metric.label);

        // Draw threshold line if exists (vertical line at threshold value)
        if (metric.threshold != null) {
            const threshX = xScale(metric.threshold);
            // Only draw if within plot area
            if (threshX >= plotLeft && threshX <= plotRight) {
                // Threshold zone shading (bad side)
                const badX = metric.direction === 'lower' ? plotLeft : threshX;
                const badWidth = metric.direction === 'lower' ? (threshX - plotLeft) : (plotRight - threshX);

                if (badWidth > 0) {
                    colGroup.append('rect')
                        .attr('x', badX)
                        .attr('y', headerHeight)
                        .attr('width', badWidth)
                        .attr('height', contentHeight)
                        .attr('fill', '#fef2f2')
                        .attr('opacity', 0.5);
                }

                // Threshold line
                colGroup.append('line')
                    .attr('x1', threshX)
                    .attr('x2', threshX)
                    .attr('y1', headerHeight)
                    .attr('y2', headerHeight + contentHeight)
                    .attr('stroke', '#ef4444')
                    .attr('stroke-width', 2)
                    .attr('stroke-dasharray', '6,3')
                    .attr('opacity', 0.8);

                // Threshold label at top
                colGroup.append('text')
                    .attr('x', threshX)
                    .attr('y', headerHeight + 12)
                    .attr('text-anchor', 'middle')
                    .attr('font-size', '9px')
                    .attr('fill', '#ef4444')
                    .attr('font-weight', '500')
                    .text(metric.threshold);
            }
        }

        // Draw x-axis at bottom edge (ticks point up, labels inside)
        const xAxis = d3.axisTop(xScale)
            .ticks(3)
            .tickSize(4)
            .tickFormat(d => {
                if (Math.abs(d) >= 100) return d.toFixed(0);
                if (Math.abs(d) >= 1) return d.toFixed(1);
                return d.toFixed(2);
            });

        colGroup.append('g')
            .attr('class', 'x-axis')
            .attr('transform', `translate(0, ${totalHeight})`)
            .call(xAxis)
            .call(g => g.select('.domain').attr('stroke', '#94a3b8'))
            .call(g => g.selectAll('.tick line').attr('stroke', '#94a3b8'))
            .call(g => g.selectAll('.tick text')
                .attr('font-size', '9px')
                .attr('fill', '#64748b'));

        // Prepare line data - only valid values
        const lineData = [];
        runs.forEach((run, rowIndex) => {
            const value = run.metrics[metric.key];
            if (value != null && !isNaN(value)) {
                lineData.push({
                    x: xScale(value),
                    y: headerHeight + rowIndex * rowHeight + rowHeight / 2,
                    value,
                    run,
                    rowIndex
                });
            }
        });

        // Draw connecting line
        if (lineData.length > 1) {
            const line = d3.line()
                .x(d => d.x)
                .y(d => d.y)
                .curve(d3.curveMonotoneY);

            colGroup.append('path')
                .datum(lineData)
                .attr('d', line)
                .attr('fill', 'none')
                .attr('stroke', '#94a3b8')
                .attr('stroke-width', 1)
                .attr('opacity', 0.4);
        }

        // Draw dots
        colGroup.selectAll('.dot')
            .data(lineData)
            .enter()
            .append('circle')
            .attr('class', 'dot')
            .attr('cx', d => d.x)
            .attr('cy', d => d.y)
            .attr('r', 5)
            .attr('fill', d => {
                if (metric.threshold == null) return '#3b82f6';
                // Check if bad based on direction
                // 'lower' means lower values are worse (e.g., tSNR) - values BELOW threshold are bad
                // 'higher' direction with threshold means values ABOVE threshold are bad (e.g., FD)
                let isBad;
                if (metric.direction === 'lower') {
                    // Bad if value is ABOVE threshold (e.g., FD > 0.5 is bad)
                    isBad = d.value > metric.threshold;
                } else {
                    // Bad if value is BELOW threshold (e.g., tSNR < 30 is bad)
                    isBad = d.value < metric.threshold;
                }
                return isBad ? '#ef4444' : '#22c55e';
            })
            .attr('stroke', '#fff')
            .attr('stroke-width', 1.5)
            .style('cursor', 'pointer')
            .on('mouseover', function(event, d) {
                d3.select(this).attr('r', 7);
                let statusText = '';
                if (metric.threshold != null) {
                    let isBad;
                    if (metric.direction === 'lower') {
                        isBad = d.value > metric.threshold;
                        statusText = isBad ? ` ⚠️ > ${metric.threshold}` : ' ✓';
                    } else {
                        isBad = d.value < metric.threshold;
                        statusText = isBad ? ` ⚠️ < ${metric.threshold}` : ' ✓';
                    }
                }
                showTooltip(event, `<strong>${metric.label}</strong><br>${d.value.toFixed(3)}${metric.unit ? ' ' + metric.unit : ''}${statusText}`);
            })
            .on('mouseout', function() {
                d3.select(this).attr('r', 5);
                hideTooltip();
            })
            .on('click', function(event, d) {
                // Open run detail on click
                if (typeof openRunDetail === 'function') {
                    openRunDetail(d.run.id);
                }
            });
    });

    return { colWidth, headerHeight };
}

// Tooltip helper
let tooltip = null;

function showTooltip(event, html) {
    if (!tooltip) {
        tooltip = d3.select('body')
            .append('div')
            .attr('class', 'chart-tooltip')
            .style('position', 'absolute')
            .style('background', 'rgba(15, 23, 42, 0.9)')
            .style('color', '#fff')
            .style('padding', '8px 12px')
            .style('border-radius', '6px')
            .style('font-size', '12px')
            .style('line-height', '1.4')
            .style('pointer-events', 'none')
            .style('z-index', '10000')
            .style('box-shadow', '0 4px 6px -1px rgba(0, 0, 0, 0.1)');
    }

    tooltip
        .html(html)
        .style('left', (event.pageX + 12) + 'px')
        .style('top', (event.pageY - 12) + 'px')
        .style('opacity', 1);
}

function hideTooltip() {
    if (tooltip) {
        tooltip.style('opacity', 0);
    }
}

// Export functions
window.createViolinPlot = createViolinPlot;
window.createScatterPlot = createScatterPlot;
window.createVerticalTimeline = createVerticalTimeline;
