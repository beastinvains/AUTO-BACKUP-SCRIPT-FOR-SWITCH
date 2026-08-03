(() => {
  const refresh = document.querySelector('#auto-refresh');
  if (refresh) refresh.addEventListener('change', () => {
    if (refresh.checked) window.setInterval(() => window.location.reload(), Number(refresh.dataset.refresh));
  });
  window.backupControls = () => {
    const button = document.querySelector('#run-backup');
    const status = document.querySelector('#backup-status');
    if (!button || !status) return;
    let wasRunning = false;
    const update = async () => {
      const response = await fetch('/api/backup-status');
      const data = await response.json();
      button.disabled = data.running;
      status.textContent = data.running ? `${data.message} (${data.elapsed_seconds}s)` : data.message;
      if (wasRunning && !data.running) window.location.reload();
      wasRunning = data.running;
    };
    button.addEventListener('click', async () => {
      button.disabled = true;
      await fetch('/backup/run', { method: 'POST' });
      await update();
    });
    update();
    window.setInterval(update, 2000);
  };
})();
