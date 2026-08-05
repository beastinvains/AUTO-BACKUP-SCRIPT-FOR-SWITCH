window.dashboardUI = (() => {
  const selectors = {
    runBackupButton: '#run-backup',
    startScheduleButton: '#start-schedule',
    stopScheduleButton: '#stop-schedule',
    backupStatus: '#backup-status',
    scheduleStatus: '#schedule-status',
  };

  const api = {
    backupStatus: '/api/backup-status',
    scheduleStatus: '/api/schedule-status',
    runBackup: '/backup/run',
    startSchedule: '/schedule/start',
    stopSchedule: '/schedule/stop',
  };

  const refreshIntervalMs = 2000;

  const fetchJson = async (url, options = {}) => {
    const response = await fetch(url, options);
    return response.json();
  };

  const query = (selector) => document.querySelector(selector);

  const updateText = (selector, text) => {
    const element = query(selector);
    if (element) element.textContent = text;
  };

  const toggleHidden = (selector, hidden) => {
    const element = query(selector);
    if (element) element.classList.toggle('d-none', hidden);
  };

  const initBackupControls = () => {
    const runButton = query(selectors.runBackupButton);
    const statusElement = query(selectors.backupStatus);
    if (!runButton || !statusElement) return;

    let wasRunning = false;

    const refreshStatus = async () => {
      const data = await fetchJson(api.backupStatus);
      runButton.disabled = Boolean(data.running);
      updateText(selectors.backupStatus, data.running ? `${data.message} (${data.elapsed_seconds}s)` : data.message);

      if (wasRunning && !data.running) {
        window.location.reload();
      }
      wasRunning = Boolean(data.running);
    };

    runButton.addEventListener('click', async () => {
      runButton.disabled = true;
      await fetch(api.runBackup, { method: 'POST' });
      await refreshStatus();
    });

    refreshStatus();
    window.setInterval(refreshStatus, refreshIntervalMs);
  };

  const initScheduleControls = () => {
    const startButton = query(selectors.startScheduleButton);
    const stopButton = query(selectors.stopScheduleButton);
    const statusElement = query(selectors.scheduleStatus);
    if (!startButton || !stopButton || !statusElement) return;

    const refreshSchedule = async () => {
      const data = await fetchJson(api.scheduleStatus);
      const started = Boolean(data.started);
      toggleHidden(selectors.startScheduleButton, started);
      toggleHidden(selectors.stopScheduleButton, !started);
      const nextBackup = data.next_backup || 'the configured time';
      updateText(selectors.scheduleStatus, started ? `Daily schedule is active; waiting for ${nextBackup}` : 'Schedule not started in this Web UI');
    };

    startButton.addEventListener('click', async () => {
      startButton.disabled = true;
      await fetch(api.startSchedule, { method: 'POST' });
      startButton.disabled = false;
      await refreshSchedule();
    });

    stopButton.addEventListener('click', async () => {
      stopButton.disabled = true;
      await fetch(api.stopSchedule, { method: 'POST' });
      stopButton.disabled = false;
      await refreshSchedule();
    });

    refreshSchedule();
  };

  const init = () => {
    initBackupControls();
    initScheduleControls();
  };

  return { init };
})();
