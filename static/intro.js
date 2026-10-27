(() => {
  const overlay = document.getElementById('site-intro');
  if (!overlay || !document.documentElement.classList.contains('show-site-intro')) { overlay?.remove(); return; }
  const started = window.__siteIntroStarted || performance.now();
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const messages = ['Finding what matters.', 'Connecting the clues.', 'Making a way back.'];
  const message = document.getElementById('intro-message');
  const steps = [...overlay.querySelectorAll('.intro-route span')];
  let index = 0, animation = null, interval = 0, closing = false;
  if (!reduced && window.lottie) animation = window.lottie.loadAnimation({container:document.getElementById('intro-animation'),renderer:'svg',loop:true,autoplay:true,path:'/static/intro-loader.json'});
  if (!reduced) interval = window.setInterval(() => {
    index = (index + 1) % messages.length;
    message.classList.add('is-changing');
    window.setTimeout(() => { message.textContent = messages[index]; message.classList.remove('is-changing'); }, 180);
    steps.forEach((item, i) => item.classList.toggle('is-active', i === index));
  }, 520);
  function finish() {
    if (closing) return;
    closing = true;
    window.setTimeout(() => {
      overlay.style.visibility = 'visible';
      overlay.classList.add('is-leaving');
      window.setTimeout(() => { document.documentElement.classList.remove('show-site-intro'); clearInterval(interval); animation?.destroy(); overlay.remove(); }, 580);
    }, Math.max(0, (reduced ? 850 : 1850) - (performance.now() - started)));
  }
  if (document.readyState === 'complete') finish(); else window.addEventListener('load', finish, {once:true});
  window.setTimeout(finish, 6500);
})();
