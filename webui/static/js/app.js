window.app = (() => {
  const initAutoRefresh = () => {
    const refresh = document.querySelector('#auto-refresh');
    if (!refresh) return;

    refresh.addEventListener('change', () => {
      if (!refresh.checked) return;
      window.setInterval(() => window.location.reload(), Number(refresh.dataset.refresh));
    });
  };

  const init = () => {
    initAutoRefresh();
  };

  return { init };
})();

window.app.init();
