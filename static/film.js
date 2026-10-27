(() => {
  const stages = ['REPORT', 'MATCH', 'RETURN'];
  let currentIntent = 'browse';
  let activeStage = 0;
  let messageIndex = 0;
  const frames = [...document.querySelectorAll('.hero-video, .login-video')]
    .map(video => ({video, frame:video.closest('.hero, .login-hero')}))
    .filter(entry => entry.frame);

  const how = document.querySelector('.how-section');
  if (how && !how.querySelector('.how-film')) {
    const video = document.createElement('video');
    video.className = 'how-film';
    video.autoplay = true;
    video.muted = true;
    video.loop = true;
    video.playsInline = true;
    video.preload = 'metadata';
    video.setAttribute('aria-hidden', 'true');
    video.innerHTML = '<source src="/static/campus-study.mp4" type="video/mp4">';
    const shade = document.createElement('div');
    shade.className = 'how-film-shade';
    shade.setAttribute('aria-hidden', 'true');
    how.prepend(shade);
    how.prepend(video);
  }

  function copyFor(frame) {
    if (frame.classList.contains('login-hero')) return ['Your campus account', 'Reports, claims, possible matches', 'Your updates, all in one place.'];
    if (currentIntent === 'lost') return ['Start with a lost report', 'Add the details you remember', ['A place, a date, one useful clue.', 'Every detail helps narrow the search.', 'We’ll keep an eye out for a match.'][messageIndex % 3]];
    if (currentIntent === 'found') return ['Add a found report', 'Help the owner find it', ['A clear description helps it find its person.', 'Add where you found it.', 'The owner can verify before handover.'][messageIndex % 3]];
    const notes = [
      ['Start with a report.', 'A useful detail starts the search.', 'Tell us where to begin.'],
      ['A small clue can bring a match closer.', 'Browse what has turned up.', 'The right detail connects two reports.'],
      ['Every item deserves a way home.', 'Keep up with claims and handovers.', 'A good match brings the story home.']
    ];
    const title = activeStage === 1 ? 'Look through recent reports' : activeStage === 2 ? 'Keep track of your claims' : 'A clear route back to its owner';
    return [title, 'Report  /  match  /  return', notes[activeStage][messageIndex % 3]];
  }

  function paint(frame) {
    const [title, detail, note] = copyFor(frame);
    frame.querySelector('.journey-title').textContent = title;
    frame.querySelector('.journey-detail').textContent = detail;
    const noteEl = frame.querySelector('.journey-note');
    noteEl.textContent = note;
    frame.querySelectorAll('.journey-step').forEach((item, index) => {
      item.classList.toggle('is-active', index === activeStage);
      item.classList.toggle('is-done', index < activeStage);
      if (index === activeStage) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
    });
    frame.style.setProperty('--journey-progress', `${activeStage / 2 * 100}%`);
  }

  frames.forEach(({frame}) => {
    const overlay = document.createElement('div');
    overlay.className = 'journey-overlay';
    overlay.innerHTML = '<div class="journey-copy"><span class="journey-kicker">CAMPUS LOST &amp; FOUND</span><strong class="journey-title"></strong><span class="journey-detail"></span><span class="journey-note" aria-live="polite"></span></div><div class="journey-steps" aria-label="Report, match, return"><span class="journey-step"><i>01</i><b>REPORT</b></span><span class="journey-step"><i>02</i><b>MATCH</b></span><span class="journey-step"><i>03</i><b>RETURN</b></span></div>';
    frame.append(overlay);
    paint(frame);
  });

  window.setFilmIntent = type => {
    currentIntent = type === 'lost' || type === 'found' ? type : 'browse';
    activeStage = 0;
    messageIndex = 0;
    frames.forEach(({frame}) => paint(frame));
  };

  const sectionMap = [['browse', 1], ['workspace', 2]];
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      activeStage = Number(entry.target.dataset.journeyStage);
      if (currentIntent === 'browse') frames.forEach(({frame}) => paint(frame));
    }), {threshold:.2, rootMargin:'-15% 0px -35% 0px'});
    sectionMap.forEach(([id, stage]) => {
      const section = document.getElementById(id);
      if (section) { section.dataset.journeyStage = stage; observer.observe(section); }
    });
  }

  if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    window.setInterval(() => { messageIndex += 1; frames.forEach(({frame}) => paint(frame)); }, 5200);
  }
})();
