(() => {
  const form = document.getElementById('login-form');
  const error = document.getElementById('login-error');
  const button = form.querySelector('button[type="submit"]');
  document.documentElement.classList.add('motion-ready');

  const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) { entry.target.classList.add('in-view'); observer.unobserve(entry.target); }
  }), {threshold:.15, rootMargin:'0px 0px -20px 0px'}) : null;
  document.querySelectorAll('.login-reveal').forEach(el => observer ? observer.observe(el) : el.classList.add('in-view'));

  form.addEventListener('submit', async event => {
    event.preventDefault();
    error.textContent = '';
    button.disabled = true;
    button.querySelector('span:first-child').textContent = 'Signing in';
    try {
      const response = await fetch('/api/login', {method:'POST', body:new FormData(form), credentials:'same-origin'});
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Could not sign in. Please try again.');
      if (document.getElementById('remember-device').checked && window.PasswordCredential && navigator.credentials?.store) {
        try { await navigator.credentials.store(new PasswordCredential(form)); } catch (_) { /* Browser declined or does not support password saving. */ }
      }
      window.location.assign('/#workspace');
    } catch (err) {
      error.textContent = err.message || 'Could not connect. Please try again.';
      button.disabled = false;
      button.querySelector('span:first-child').textContent = 'Log in';
    }
  });

  fetch('/api/me', {credentials:'same-origin'}).then(r => r.ok ? r.json() : null).then(data => {
    if (data?.user) window.location.replace('/#workspace');
  }).catch(() => {});
})();
