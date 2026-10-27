(() => {
  const originalAuth = window.openAuth;
  if (originalAuth) {
    window.openAuth = mode => {
      if (mode === 'login') { window.location.assign('/login'); return; }
      return originalAuth(mode);
    };
  }

  const originalReport = window.openReport;
  if (originalReport) {
    window.openReport = type => {
      window.setFilmIntent?.(type);
      return originalReport(type);
    };
  }

  if (new URLSearchParams(window.location.search).get('join') === '1') {
    window.history.replaceState({}, '', '/');
    window.addEventListener('load', () => window.setTimeout(() => window.openAuth?.('register'), 2100), {once:true});
  }
})();
