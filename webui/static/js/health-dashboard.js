/* Build the health dashboard from daily_report.json data supplied by the page. */
window.healthDashboard = (() => {
  const limits = { cpuWarning: 75, cpuCritical: 90, memoryWarning: 80, temperatureWarning: 60, temperatureCritical: 70 };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
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
    const lines = text.split('\n').filter((line) => /power supply|\bpsu\b/i.test(line));
    if (!lines.length) return null;
    const summary = { total: lines.length, ok: 0, absent: 0, failed: 0, unknown: 0 };
    for (const line of lines) {
      if (/not present|absent|not installed|not available/i.test(line)) summary.absent += 1;
      else if (/\bis ok\b|\bok\b/i.test(line)) summary.ok += 1;
      else if (/fail|not ok|fault|down|critical/i.test(line)) summary.failed += 1;
      else summary.unknown += 1;
    }
    return summary;
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
    const power = powerSummary(text);
    const fans = componentSummary(text, 'fan');
    const interfaces = interfaceSummary(text);
    const alerts = [];
    const backupFailed = String(device.status || '').toLowerCase() !== 'success';
    const authenticationFailed = /authentication failed|login failed|invalid password/i.test(`${device.error || ''}\n${text}`);
    if (backupFailed) alerts.push('Backup failed');
    if (authenticationFailed) alerts.push('Authentication failure');
    if (power?.failed) alerts.push(`${power.failed} power supply failure${power.failed > 1 ? 's' : ''}`);
    if (power?.absent) alerts.push(`${power.absent} power supply ${power.absent > 1 ? 'units are' : 'is'} absent`);
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
      ['Devices', totals.devices, 'primary'], ['Healthy', totals.healthy, 'success'], ['Warnings', totals.warning, 'warning'],
      ['Critical', totals.critical, 'danger'], ['Failed Backups', totals.failed, 'secondary'], ['Average CPU', average(items, 'cpu'), 'info'], ['Average Temp', average(items, 'temperature'), 'info'],
    ];
    document.querySelector('#health-summary').innerHTML = cards.map(([label, value, color]) => `<div class="col-sm-6 col-lg"><div class="card h-100 border-${color}"><div class="card-body py-3"><div class="small text-muted">${label}</div><div class="h4 mb-0 text-${color}">${value}</div></div></div></div>`).join('') + (history.length ? `<div class="col-12"><div class="small text-muted">Last ${history.length} report day${history.length === 1 ? '' : 's'}: ${history.join(' · ')}</div></div>` : '');
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
      const power = item.power ? `${item.power.ok} / ${item.power.total} OK${item.power.absent ? ` · ${item.power.absent} absent` : ''}${item.power.failed ? ` · ${item.power.failed} failed` : ''}${item.power.unknown ? ` · ${item.power.unknown} unknown` : ''}` : 'Not Available';
      const fans = item.fans ? `${item.fans.total - item.fans.failed} / ${item.fans.total} OK` : 'Not Available';
      const alertBlock = item.alerts.length ? `<div class="health-alert mt-3"><strong>⚠ Alerts</strong><ul class="mb-0 mt-1">${item.alerts.map((alert) => `<li>${escapeHtml(alert)}</li>`).join('')}</ul></div>` : '';
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
      renderCards(items.filter((item) => {
        const searchMatch = !needle || item.text.toLowerCase().includes(needle) || [item.hostname, item.ip, item.vendor].some((value) => String(value || '').toLowerCase().includes(needle));
        const filterMatch = !selected.length || selected.some((filter) => filter === item.health || filter === String(item.vendor || '').toLowerCase() || (filter === 'high-cpu' && item.cpu !== null && item.cpu >= limits.cpuWarning) || (filter === 'high-temperature' && item.temperature !== null && item.temperature >= limits.temperatureWarning));
        return searchMatch && filterMatch;
      }), detailUrl);
    };
    search.addEventListener('input', update);
    document.querySelectorAll('.health-filter').forEach((input) => input.addEventListener('change', update));
    update();
  }
  return { init };
})();
