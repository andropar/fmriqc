// Threshold control state
let currentThresholds = {};
let originalThresholds = {};

function initThresholdControls() {
  const sliders = document.querySelectorAll('.threshold-slider');
  sliders.forEach(function(slider) {
    const key = slider.dataset.thresholdKey;
    const value = parseFloat(slider.value);
    currentThresholds[key] = value;
    originalThresholds[key] = value;

    // Sync slider and number input
    const numberInput = document.getElementById(slider.id + '-value');

    slider.addEventListener('input', function() {
      const newValue = parseFloat(this.value);
      numberInput.value = newValue;
      updateThreshold(key, newValue);
    });

    numberInput.addEventListener('input', function() {
      const newValue = parseFloat(this.value);
      if (!isNaN(newValue)) {
        slider.value = newValue;
        updateThreshold(key, newValue);
      }
    });
  });

  // Reset button
  const resetBtn = document.getElementById('reset-thresholds-btn');
  if (resetBtn) {
    resetBtn.addEventListener('click', resetThresholds);
  }

  // Export button
  const exportBtn = document.getElementById('export-exclusions-btn');
  if (exportBtn) {
    exportBtn.addEventListener('click', exportExclusionList);
  }
}

function updateThreshold(key, value) {
  currentThresholds[key] = value;
  recalculateFlags();
}

const FLAG_RULES = {
  'tsnr_low': {metric: 'tsnr_median', operator: '<', staticValue: 25},
  'dvars_high': {metric: 'dvars_percent_above', operator: '>', staticValue: 15.0},
  'outliers_high': {metric: 'outlier_percent_above', operator: '>', staticValue: 10.0},
  'motion_high': {
    composite: true,
    conditions: [
      {metric: 'fd_percent_above', operator: '>', staticValue: 20.0},
      {metric: 'fd_median', operator: '>', thresholdKey: 'fd_median_threshold'}
    ],
    logic: 'OR'
  },
  'hyperintense_slices': {metric: 'n_hyperintense_slices', operator: '>', staticValue: 3},
  'slice_outliers': {metric: 'slice_outlier_max', operator: '>', staticValue: 0.25},
  'mask_fragmented': {metric: 'mask_components', operator: '>', staticValue: 3},
  'physiological_noise_high': {metric: 'physiological_power_ratio', operator: '>', staticValue: 0.5}
};

function evaluateCondition(metricValue, operator, thresholdValue) {
  if (metricValue === null || metricValue === undefined) return false;
  switch(operator) {
    case '>': return metricValue > thresholdValue;
    case '<': return metricValue < thresholdValue;
    case '>=': return metricValue >= thresholdValue;
    case '<=': return metricValue <= thresholdValue;
    case '==': return metricValue === thresholdValue;
    default: return false;
  }
}

function calculateRunFlags(runThresholdMetrics, currentThresholds) {
  const flags = {};
  for (const flagName in FLAG_RULES) {
    const rule = FLAG_RULES[flagName];
    if (rule.composite) {
      const results = rule.conditions.map(cond => {
        const thresholdValue = cond.thresholdKey ? currentThresholds[cond.thresholdKey] : cond.staticValue;
        const metricValue = runThresholdMetrics[cond.metric];
        return evaluateCondition(metricValue, cond.operator, thresholdValue);
      });
      flags[flagName] = rule.logic === 'OR' ? results.some(r => r) : results.every(r => r);
    } else {
      const thresholdValue = rule.thresholdKey ? currentThresholds[rule.thresholdKey] : rule.staticValue;
      const metricValue = runThresholdMetrics[rule.metric];
      flags[flagName] = evaluateCondition(metricValue, rule.operator, thresholdValue);
    }
  }
  return flags;
}

function recalculateFlags() {
  const exportDataEl = document.getElementById('qa-export-data');
  if (!exportDataEl) return;
  const data = JSON.parse(exportDataEl.textContent);
  if (!data || !data.sessions) return;

  let totalRuns = 0;
  let totalFlagged = 0;

  data.sessions.forEach(session => {
    let sessionFlagged = 0;
    session.runs.forEach(run => {
      if (!run.threshold_metrics) return;
      totalRuns++;
      const newFlags = calculateRunFlags(run.threshold_metrics, currentThresholds);
      run.flags = newFlags;
      const flagCount = Object.values(newFlags).filter(Boolean).length;
      if (flagCount > 0) {
        totalFlagged++;
        sessionFlagged++;
      }
    });
  });

  // Update export button
  const hasChanges = Object.keys(currentThresholds).some(key => {
    return Math.abs(currentThresholds[key] - originalThresholds[key]) > 0.001;
  });
  const exportBtn = document.getElementById('export-exclusions-btn');
  if (exportBtn) {
    exportBtn.textContent = hasChanges ? 'Export Updated Exclusion List (Modified)' : 'Export Exclusion List';
    exportBtn.style.fontWeight = hasChanges ? 'bold' : '500';
  }

  console.log('Recalculated flags: ' + totalFlagged + '/' + totalRuns + ' flagged');
}

function resetThresholds() {
  Object.keys(originalThresholds).forEach(key => {
    const value = originalThresholds[key];
    currentThresholds[key] = value;

    const slider = document.getElementById('threshold-' + key);
    const numberInput = document.getElementById('threshold-' + key + '-value');

    if (slider) slider.value = value;
    if (numberInput) numberInput.value = value;
  });

  recalculateFlags();
}

function exportExclusionList() {
  // Build exclusion list based on current thresholds
  const exclusionData = {
    timestamp: new Date().toISOString(),
    thresholds: currentThresholds,
    exclusions: [],
    note: 'Generated with modified thresholds via QA report interactive controls'
  };

  // TODO: In production, this would analyze actual run metrics against new thresholds
  // For now, provide the thresholds configuration

  const blob = new Blob([JSON.stringify(exclusionData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'exclusion_thresholds_' + new Date().toISOString().split('T')[0] + '.json';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
