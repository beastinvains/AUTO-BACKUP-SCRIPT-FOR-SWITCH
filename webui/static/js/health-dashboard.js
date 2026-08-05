/* Build the health dashboard from daily_report.json data supplied by the page. */
window.healthDashboard = (() => {
  const SCRIPT_VERSION = '2';
  const limits = { cpuWarning: 75, cpuCritical: 90, memoryWarning: 80, temperatureWarning: 60, temperatureCritical: 70 };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
  console.debug(`health-dashboard.js loaded version ${SCRIPT_VERSION}`);
  const number = (match) => match ? Number(match[1]) : null;
  const commandText = (device) => (device.commands || []).map((item) => `${item.command || ''}\n${item.output || ''}\n${item.error || ''}`).join('\n');

  function firstNumber(text, expressions) {
    for (const expression of expressions) {
      const value = number(text.match(expression));
      if (value !== null) return value;
    }
    return null;
  }

  function componentSummary(text, label) {
    const lines = text.split('\n').filter((line) => line.toLowerCase().includes(label));
    if (!lines.length) return null;
    const failed = lines.filter((line) => /fail|not ok|fault|down|critical/i.test(line)).length;
    return { total: lines.length, failed };
  }

  function powerSummary(text) {
    const lines = text.split('\n').filter((line) =>
      /power supply/i.test(line)
      && /\bis ok\b|\bok\b|not present|absent|not installed|not available|fail|not ok|fault|down|critical|\bpresent\b/i.test(line)
    );
    if (!lines.length) return null;
    const summary = { total: lines.length, ok: 0, absent: 0, failed: 0, unknown: 0, warning: 0 };
    for (const line of lines) {
      if (/not present|absent|not installed|not available/i.test(line)) summary.absent += 1;
      else if (/\bis ok\b|\bok\b/i.test(line)) summary.ok += 1;
      else if (/fail|not ok|fault|down|critical/i.test(line)) summary.failed += 1;
      else summary.unknown += 1;
    }
    summary.warning = summary.total - summary.ok - summary.failed;
    return summary;
  }

  function powerFromMetadata(metadata) {
    if (!metadata || typeof metadata !== 'object') return null;
    const items = Array.isArray(metadata.items) ? metadata.items : [];
    const total = items.length ? items.length : Number(metadata.total) || 0;
    const ok = items.length ? items.filter((item) => item.status === 'OK').length : Number(metadata.ok) || 0;
    const failed = items.length ? items.filter((item) => item.status === 'Failed').length : Number(metadata.failed) || 0;
    const warning = items.length ? total - ok - failed : Number(metadata.warning) || 0;
    const absent = items.filter((item) => item.status === 'Absent').length;
    const unknown = items.filter((item) => item.status === 'Unknown').length;
    return { total, ok, failed, warning, absent, unknown };
  }

  function interfaceSummary(text) {
    const lines = text.split('\n');
    const connected = [];
    let down = 0;
    let known = false;
    for (const line of lines) {
      const match = line.match(/^\s*((?:Gi|GigabitEthernet|Te|TenGigabitEthernet|Fa|FastEthernet)\S*)\s+.*?\b(up|down)\s+(up|down)\s*$/i);
      if (!match) continue;
      known = true;
      if (match[2].toLowerCase() === 'up' && match[3].toLowerCase() === 'up') connected.push(match[1]);
      if (match[2].toLowerCase() === 'down' && !/administratively down/i.test(line)) down += 1;
    }
    return { connected, down, known };
  }

  function analyze(device) {
    const text = commandText(device);
    const lower = text.toLowerCase();
    const cpu = firstNumber(text, [/CPU utilization[^:\n]*:\s*(\d+(?:\.\d+)?)%/i, /CPU[^\n]*?(\d+(?:\.\d+)?)%/i]);
    const memory = firstNumber(text, [/memory utilization[^:\n]*:\s*(\d+(?:\.\d+)?)%/i, /memory[^\n]*?(\d+(?:\.\d+)?)%/i]);
    const temperature = firstNumber(text, [/(\d+(?:\.\d+)?)\s*(?:°\s*C|degrees?\s*C|Celsius)/i]);
    const powerText = powerSummary(text);
    const meta = device.metadata?.power_supplies ? powerFromMetadata(device.metadata.power_supplies) : null;
    // Prefer the more detailed source: if the metadata appears to summarize fewer
    // items than the parsed command output, use the parsed output instead so
    // stack devices with many FPCs are represented correctly.
    let power = null;
    if (meta && powerText) {
      const metaItems = Array.isArray(device.metadata?.power_supplies?.items) ? device.metadata.power_supplies.items.length : 0;
      // Prefer metadata only when it contains itemized data and that
      // item count is at least as large as the parsed command output.
      power = (metaItems && metaItems >= powerText.total) ? meta : powerText;
    } else {
      power = meta || powerText || null;
    }
    const fans = componentSummary(text, 'fan');
    const interfaces = interfaceSummary(text);
    const alerts = [];
    const backupFailed = String(device.status || '').toLowerCase() !== 'success';
    const authenticationFailed = /authentication failed|login failed|invalid password/i.test(`${device.error || ''}\n${text}`);
    if (backupFailed) alerts.push('Backup failed');
    if (authenticationFailed) alerts.push('Authentication failure');
    if (power?.failed) alerts.push(`${power.failed} power supply failure${power.failed > 1 ? 's' : ''}`);
    if (power?.absent) alerts.push(`${power.absent} power supply ${power.absent > 1 ? 'units are' : 'is'} absent`);
    // Only add the generic "warning" alert when there are no specific absent/failed counts.
    if (power?.warning && !power?.absent && !power?.failed) alerts.push(`${power.warning} power supply warning${power.warning > 1 ? 's' : ''}`);
    if (fans?.failed) alerts.push(`${fans.failed} fan failure${fans.failed > 1 ? 's' : ''}`);
    if (cpu !== null && cpu >= limits.cpuCritical) alerts.push(`CPU ${cpu}%`);
    else if (cpu !== null && cpu >= limits.cpuWarning) alerts.push(`High CPU ${cpu}%`);
    if (memory !== null && memory >= limits.memoryWarning) alerts.push(`High memory ${memory}%`);
    if (temperature !== null && temperature >= limits.temperatureCritical) alerts.push(`Temperature ${temperature}°C`);
    else if (temperature !== null && temperature >= limits.temperatureWarning) alerts.push(`High temperature ${temperature}°C`);
    if (interfaces.down) alerts.push(`${interfaces.down} interface${interfaces.down > 1 ? 's' : ''} down`);
    let health = 'healthy';
    if (backupFailed) health = 'failed';
    else if (authenticationFailed || power?.failed || fans?.failed || (cpu !== null && cpu >= limits.cpuCritical) || (temperature !== null && temperature >= limits.temperatureCritical)) health = 'critical';
    else if (alerts.length) health = 'warning';
    return { ...device, text, cpu, memory, temperature, power, fans, interfaces, alerts, health };
  }

  function average(items, key) {
    const values = items.map((item) => item[key]).filter((value) => value !== null);
    return values.length ? `${Math.round(values.reduce((sum, value) => sum + value, 0) / values.length)}${key === 'temperature' ? '°C' : '%'}` : 'Not Available';
  }

  function summary(items, reports) {
    const totals = { devices: items.length, healthy: 0, warning: 0, critical: 0, failed: 0 };
    items.forEach((item) => { totals[item.health] += 1; });
    const history = reports.map((report) => {
      const day = report.report_date || report.generated_at || 'Unknown date';
      const analysed = (report.devices || []).map(analyze);
      return `${escapeHtml(day)}: ${analysed.filter((item) => item.health === 'healthy').length} healthy, ${analysed.filter((item) => item.health === 'warning').length} warning, ${analysed.filter((item) => item.health === 'critical').length} critical, ${analysed.filter((item) => item.health === 'failed').length} failed`;
    });
    const cards = [
      ['Devices', totals.devices, 'primary', null],
      ['Healthy', totals.healthy, 'success', 'healthy'],
      ['Warnings', totals.warning, 'warning', 'warning'],
      ['Critical', totals.critical, 'danger', 'critical'],
      ['Failed Backups', totals.failed, 'secondary', 'failed'],
      ['Average CPU', average(items, 'cpu'), 'info', 'high-cpu'],
      ['Average Temp', average(items, 'temperature'), 'info', 'high-temperature'],
    ];
    document.querySelector('#health-summary').innerHTML = cards.map(([label, value, color, filter]) => `
      <div class="col-sm-6 col-lg">
        <div class="card h-100 border-${color} health-summary-card${filter ? ' clickable' : ''}"${filter ? ` data-filter="${filter}" tabindex="0"` : ''} style="${filter ? 'cursor:pointer;' : ''}">
          <div class="card-body py-3">
            <div class="small text-muted">${label}</div>
            <div class="h4 mb-0 text-${color}">${value}</div>
          </div>
        </div>
      </div>
    `).join('') + (history.length ? `<div class="col-12"><div class="small text-muted">Last ${history.length} report day${history.length === 1 ? '' : 's'}: ${history.join(' · ')}</div></div>` : '');
  }

  function csvEscape(value) {
    if (value == null) return '';
    const text = String(value).replace(/"/g, '""');
    return text.includes(',') || text.includes('"') || text.includes('\n') ? `"${text}"` : text;
  }

  function exportCsv(items, selectedFilters) {
    const header = ['Hostname', 'IP', 'Status', 'Problem'];
    const rows = items.map((item) => [
      csvEscape(item.hostname),
      csvEscape(item.ip),
      csvEscape(item.health),
      csvEscape(item.alerts.length ? item.alerts.join(' · ') : 'No issues'),
    ].join(','));
    const csv = [header.join(','), ...rows].join('\r\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const filename = `${selectedFilters.join('_') || 'devices'}_export.csv`;
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  function renderFilteredList(items, selectedFilters) {
    const container = document.querySelector('#health-filtered-list');
    if (!selectedFilters || !selectedFilters.length || !items.length) {
      container.innerHTML = '';
      return;
    }
    const title = selectedFilters.length === 1 ? selectedFilters[0].replace(/-/g, ' ') : selectedFilters.map((filter) => filter.replace(/-/g, ' ')).join(' + ');
    const rows = items.map((item) => {
      const problem = item.alerts.length ? item.alerts.join(' · ') : 'No issues';
      return `<li class="list-group-item py-2"><strong>${escapeHtml(item.hostname)}</strong> (${escapeHtml(item.ip)}) — ${escapeHtml(problem)}</li>`;
    }).join('');
    container.innerHTML = `
      <div class="card border-info">
        <div class="card-body py-3">
          <div class="d-flex justify-content-between align-items-start mb-3">
            <div>
              <h5 class="card-title mb-1">Showing ${items.length} device${items.length === 1 ? '' : 's'} for ${escapeHtml(title)}</h5>
              <div class="small text-muted">Export current filtered list to CSV</div>
            </div>
            <button type="button" class="btn btn-sm btn-outline-primary" id="export-filtered-csv">Export CSV</button>
          </div>
          <ul class="list-group list-group-flush">${rows}</ul>
        </div>
      </div>
    `;
    const exportButton = document.querySelector('#export-filtered-csv');
    if (exportButton) {
      exportButton.addEventListener('click', () => exportCsv(items, selectedFilters));
    }
  }

  function attachSummaryCardEvents(update) {
    document.querySelectorAll('.health-summary-card[data-filter]').forEach((card) => {
      const filter = card.dataset.filter;
      card.addEventListener('click', () => {
        const checkboxes = document.querySelectorAll('.health-filter');
        checkboxes.forEach((input) => { input.checked = input.value === filter; });
        update();
        const filtered = document.querySelector('#health-filtered-list');
        if (filtered) filtered.scrollIntoView({ behavior: 'smooth' });
      });
      card.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          card.click();
        }
      });
    });
  }

  function metric(label, value) { return `<div><span class="text-muted">${label}</span><strong class="d-block">${value ?? 'Not Available'}</strong></div>`; }
  function healthBadge(health) {
    const data = { healthy: ['success', '🟢 Healthy'], warning: ['warning', '🟡 Warning'], critical: ['danger', '🔴 Critical'], failed: ['secondary', 'Backup Failed'] }[health];
    return `<span class="badge text-bg-${data[0]}">${data[1]}</span>`;
  }

  function renderCards(items, detailUrl) {
    const container = document.querySelector('#health-cards');
    if (!items.length) { container.innerHTML = document.querySelector('#no-results').innerHTML; return; }
    container.innerHTML = items.map((item) => {
      const metadata = item.metadata || {};
      const connected = item.interfaces.connected.length ? `${item.interfaces.connected.slice(0, 3).map(escapeHtml).join(', ')}${item.interfaces.connected.length > 3 ? ` +${item.interfaces.connected.length - 3} more` : ''}` : 'Not Available';
      const duration = metadata.backup_duration ?? 'Not Available';
      const configChanged = metadata.config_changed === undefined ? 'Not Available' : metadata.config_changed ? 'Yes' : 'No';
      const backupSize = metadata.backup_size ?? 'Not Available';
      let power = 'Not Available';
      if (item.power) {
        const parts = [];
        parts.push(`${item.power.ok} / ${item.power.total} OK`);
        if (item.power.failed) parts.push(`${item.power.failed} Failed`);
        if (item.power.absent) parts.push(`${item.power.absent} Absent`);
        else if (item.power.warning) parts.push(`${item.power.warning} Warning`);
        power = parts.join(' · ');
      }
      const fans = item.fans ? `${item.fans.total - item.fans.failed} / ${item.fans.total} OK` : 'Not Available';
      let alertBlock = '';
      if (item.alerts && item.alerts.length) {
        const compact = item.alerts.map((a) => escapeHtml(a)).join(' · ');
        alertBlock = `<div class="health-alert mt-3"><strong>⚠ Alerts</strong><div class="small text-muted mt-1">${compact}</div></div>`;
      }
      const href = detailUrl.replace('__HOSTNAME__', encodeURIComponent(item.hostname));
      const interfacesDown = item.interfaces.known ? item.interfaces.down : 'Not Available';
      return `<div class="col-md-6 col-xl-4"><a class="card health-card border-${item.health} h-100 text-decoration-none text-reset" href="${href}"><div class="card-body"><div class="d-flex justify-content-between gap-2"><div><h2 class="h5 mb-1">${escapeHtml(item.hostname)}</h2><div class="text-muted small">${escapeHtml(item.ip)} · ${escapeHtml(item.vendor || 'Not Available')}</div></div>${healthBadge(item.health)}</div><hr><div class="row row-cols-2 g-3 small">${metric('Backup status', escapeHtml(item.status || 'Not Available'))}${metric('Last backup', escapeHtml(item.generated_at || 'Not Available'))}${metric('Backup duration', escapeHtml(duration))}${metric('CPU', item.cpu === null ? null : `${item.cpu}%`)}${metric('Memory', item.memory === null ? null : `${item.memory}%`)}${metric('Temperature', item.temperature === null ? null : `${item.temperature}°C`)}${metric('Power supplies', power)}${metric('Fans', fans)}${metric('Interfaces down', interfacesDown)}${metric('Config changed', configChanged)}${metric('Backup size', escapeHtml(backupSize))}</div><div class="connected-interfaces mt-3"><strong class="small">Connected Interfaces</strong><div class="small text-muted">${connected}</div></div>${alertBlock}</div></a></div>`;
    }).join('');
  }

  function init({ devices, reports, detailUrl, query }) {
    const items = devices.map((device) => ({ ...analyze(device), generated_at: reports[0]?.generated_at || 'Not Available' }));
    summary(items, reports);
    const search = document.querySelector('#health-search');
    const filters = [
      ['healthy', 'Healthy'], ['warning', 'Warning'], ['critical', 'Critical'], ['cisco', 'Cisco'], ['juniper', 'Juniper'], ['hp', 'HP'], ['failed', 'Backup Failed'], ['high-cpu', 'High CPU'], ['high-temperature', 'High Temperature'],
    ];
    document.querySelector('#health-filters').innerHTML = filters.map(([value, label]) => `<div class="form-check form-check-inline"><input class="form-check-input health-filter" type="checkbox" value="${value}" id="filter-${value}"><label class="form-check-label" for="filter-${value}">${label}</label></div>`).join('');
    const update = () => {
      const selected = [...document.querySelectorAll('.health-filter:checked')].map((input) => input.value);
      const needle = search.value.trim().toLowerCase();
      const filtered = items.filter((item) => {
        const searchMatch = !needle || item.text.toLowerCase().includes(needle) || [item.hostname, item.ip, item.vendor].some((value) => String(value || '').toLowerCase().includes(needle));
        const filterMatch = !selected.length || selected.some((filter) => filter === item.health || filter === String(item.vendor || '').toLowerCase() || (filter === 'high-cpu' && item.cpu !== null && item.cpu >= limits.cpuWarning) || (filter === 'high-temperature' && item.temperature !== null && item.temperature >= limits.temperatureWarning));
        return searchMatch && filterMatch;
      });
      renderCards(filtered, detailUrl);
      renderFilteredList(filtered, selected);
    };
    search.addEventListener('input', update);
    document.querySelectorAll('.health-filter').forEach((input) => input.addEventListener('change', update));
    update();
    attachSummaryCardEvents(update);
  }
  return { init };
})();
