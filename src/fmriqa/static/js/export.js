/**
 * Data export functionality (CSV, JSON, flagged runs)
 */

function openExportModal() {
  const modal = document.getElementById('exportModal');
  const overlay = document.getElementById('exportOverlay');
  if (modal) modal.classList.add('active');
  if (overlay) overlay.classList.add('active');
}

function closeExportModal() {
  const modal = document.getElementById('exportModal');
  const overlay = document.getElementById('exportOverlay');
  if (modal) modal.classList.remove('active');
  if (overlay) overlay.classList.remove('active');
}

function downloadFile(content, filename, type) {
  const blob = new Blob([content], { type: type });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
  closeExportModal();
}

function getQAData() {
  const dataEl = document.getElementById('qa-export-data');
  return dataEl ? JSON.parse(dataEl.textContent) : null;
}

function exportJSON() {
  const data = getQAData();
  if (!data) { alert('No data available'); return; }
  const json = JSON.stringify(data, null, 2);
  const filename = 'qa_' + data.subject + '_' + new Date().toISOString().split('T')[0] + '.json';
  downloadFile(json, filename, 'application/json');
}

function exportCSV() {
  const data = getQAData();
  if (!data) { alert('No data available'); return; }

  const rows = [];
  // Collect all metric keys
  const metricKeys = new Set();
  const flagKeys = new Set();
  data.sessions.forEach(function(sess) {
    sess.runs.forEach(function(run) {
      Object.keys(run.metrics).forEach(function(k) { metricKeys.add(k); });
      Object.keys(run.flags).forEach(function(k) { flagKeys.add(k); });
    });
  });

  const metricList = Array.from(metricKeys).sort();
  const flagList = Array.from(flagKeys).sort();

  // Header row
  const header = ['subject', 'session', 'run', 'task', 'echo'].concat(metricList).concat(flagList.map(function(f) {
    return 'flag_' + f;
  }));
  rows.push(header);

  // Data rows
  data.sessions.forEach(function(sess) {
    sess.runs.forEach(function(run) {
      const row = [data.subject, sess.session, run.run, run.task || '', run.echo || ''];
      metricList.forEach(function(k) {
        row.push(run.metrics[k] !== undefined ? run.metrics[k] : '');
      });
      flagList.forEach(function(k) {
        row.push(run.flags[k] !== undefined ? (run.flags[k] ? 1 : 0) : '');
      });
      rows.push(row);
    });
  });

  const csv = rows.map(function(row) {
    return row.map(function(cell) {
      return '"' + String(cell).replace(/"/g, '""') + '"';
    }).join(',');
  }).join('\n');

  const filename = 'qa_' + data.subject + '_' + new Date().toISOString().split('T')[0] + '.csv';
  downloadFile(csv, filename, 'text/csv');
}

function exportFlagged() {
  const data = getQAData();
  if (!data) { alert('No data available'); return; }

  const rows = [];
  rows.push(['subject', 'session', 'run', 'task', 'echo', 'flags', 'flag_count']);

  data.sessions.forEach(function(sess) {
    sess.runs.forEach(function(run) {
      const activeFlags = Object.entries(run.flags).filter(function(e) {
        return e[1];
      }).map(function(e) {
        return e[0];
      });
      if (activeFlags.length > 0) {
        rows.push([data.subject, sess.session, run.run, run.task || '', run.echo || '', activeFlags.join('; '), activeFlags.length]);
      }
    });
  });

  if (rows.length === 1) {
    alert('No flagged runs found!');
    closeExportModal();
    return;
  }

  const csv = rows.map(function(row) {
    return row.map(function(cell) {
      return '"' + String(cell).replace(/"/g, '""') + '"';
    }).join(',');
  }).join('\n');

  const filename = 'qa_' + data.subject + '_flagged_' + new Date().toISOString().split('T')[0] + '.csv';
  downloadFile(csv, filename, 'text/csv');
}
