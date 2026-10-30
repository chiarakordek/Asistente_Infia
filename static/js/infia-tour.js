(() => {
  const root = document.getElementById('infiaTour');
  if (!root) return;

  const card = document.getElementById('tourCard');
  const hole = document.getElementById('tourMaskHole');
  const shade = document.getElementById('tourMaskShade');
  const base = document.getElementById('tourMaskBase');
  const skip = document.getElementById('tourSkip');
  const next = document.getElementById('tourNext');
  const title = document.getElementById('tourTitle');
  const description = document.getElementById('tourDescription');
  const progressLabel = document.getElementById('tourProgressLabel');
  const progressBar = document.getElementById('tourProgressBar');
  const userId = root.dataset.userId || 'user';
  const completedKey = `infia-tutorial-completed-${userId}`;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let steps = [];
  let current = 0;
  let previousFocus = null;
  let positionFrame = 0;

  const makeSteps = () => {
    const student = document.querySelector('#alumnosContainer .alumno-item');
    const room = document.querySelector('.nav-room-switcher');
    const studentSection = document.getElementById('alumnosSection');
    const roster = document.getElementById('alumnosContainer');
    const mic = student?.querySelector('.student-quick-record');
    const studentLink = student?.querySelector('.alumno-nombre');
    const empty = roster?.querySelector('.roster-empty');
    const planning = document.querySelector('a.nav-link-item[href="/planificacion"]');

    return [
      {
        target: room || document.querySelector('.welcome-card'),
        title: 'Tu sala, siempre organizada',
        text: 'Si trabajás con más de una sala, cambiala desde acá. Cada una mantiene sus alumnos, observaciones e informes por separado.'
      },
      {
        target: studentSection,
        title: 'Cargá a tus alumnos',
        text: 'Podés agregar uno por vez o cargar varios juntos. Así queda lista tu lista para registrar lo que pasa en el aula.'
      },
      {
        target: mic || empty || roster,
        title: 'Registrá en el momento',
        text: mic
          ? 'Tocá el micrófono junto al nombre para dictar una observación rápida. También podés escribirla con «Registrar observación».'
          : 'Cuando cargues un alumno, vas a ver el micrófono junto a su nombre para dictar una observación. También podés escribirla.'
      },
      {
        target: studentLink || roster,
        title: 'Revisá su recorrido',
        text: 'Abrí el nombre para ver las observaciones de ese alumno, generar un informe, editarlo y descargarlo.'
      },
      {
        target: planning,
        title: 'Prepará tu planificación',
        text: 'En Planificación podés crear las áreas, indicadores y unidades que usás. Es un espacio secundario: podés empezar a registrar observaciones sin configurarlo.'
      }
    ].filter(step => step.target);
  };

  function setViewport() {
    const width = window.innerWidth;
    const height = window.innerHeight;
    const svg = root.querySelector('.infia-tour-scrim');
    const mask = document.getElementById('tourMask');
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('width', width);
    svg.setAttribute('height', height);
    mask.setAttribute('x', 0);
    mask.setAttribute('y', 0);
    mask.setAttribute('width', width);
    mask.setAttribute('height', height);
    for (const rect of [base, shade]) {
      rect.setAttribute('x', 0);
      rect.setAttribute('y', 0);
      rect.setAttribute('width', width);
      rect.setAttribute('height', height);
    }
  }

  function position() {
    if (root.hidden || !steps[current]) return;
    setViewport();
    const target = steps[current].target;
    const bounds = target.getBoundingClientRect();
    const pad = 8;
    const left = Math.max(8, bounds.left - pad);
    const top = Math.max(8, bounds.top - pad);
    hole.setAttribute('x', left);
    hole.setAttribute('y', top);
    hole.setAttribute('width', Math.max(0, Math.min(window.innerWidth - left, bounds.width + pad * 2)));
    hole.setAttribute('height', Math.max(0, Math.min(window.innerHeight - top, bounds.height + pad * 2)));

    const gap = 18;
    const cardWidth = Math.min(440, window.innerWidth - 24);
    card.style.width = `${cardWidth}px`;
    const cardHeight = card.getBoundingClientRect().height;
    const cardLeft = Math.min(Math.max(12, bounds.left + bounds.width / 2 - cardWidth / 2), window.innerWidth - cardWidth - 12);
    const below = bounds.bottom + gap + cardHeight <= window.innerHeight - 12;
    const cardTop = below ? bounds.bottom + gap : Math.max(12, bounds.top - gap - cardHeight);
    card.style.left = `${cardLeft}px`;
    card.style.top = `${cardTop}px`;
  }

  function showStep(index) {
    current = index;
    const step = steps[current];
    if (!step) return finish();
    step.target.scrollIntoView({ behavior: reducedMotion.matches ? 'auto' : 'smooth', block: 'center', inline: 'nearest' });
    title.textContent = step.title;
    description.textContent = step.text;
    progressLabel.textContent = `PASO ${current + 1} DE ${steps.length}`;
    progressBar.style.width = `${((current + 1) / steps.length) * 100}%`;
    next.innerHTML = current === steps.length - 1 ? 'Terminar <span aria-hidden="true">✓</span>' : 'Siguiente <span aria-hidden="true">→</span>';
    window.setTimeout(position, reducedMotion.matches ? 0 : 220);
  }

  async function markComplete() {
    try { localStorage.setItem(completedKey, 'true'); } catch (_) {}
    try {
      await fetch('/api/tutorial/completar', {
        method: 'POST',
        headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
      });
    } catch (_) {}
  }

  function finish() {
    root.hidden = true;
    window.removeEventListener('resize', schedulePosition);
    window.removeEventListener('scroll', schedulePosition, true);
    document.removeEventListener('keydown', onKeyDown);
    markComplete();
    previousFocus?.focus?.({ preventScroll: true });
  }

  function schedulePosition() {
    if (positionFrame) cancelAnimationFrame(positionFrame);
    positionFrame = requestAnimationFrame(position);
  }

  function onKeyDown(event) {
    if (event.key === 'Escape') {
      event.preventDefault();
      finish();
    } else if (event.key === 'Tab') {
      const controls = [skip, next];
      if (event.shiftKey && document.activeElement === skip) {
        event.preventDefault(); next.focus();
      } else if (!event.shiftKey && document.activeElement === next) {
        event.preventDefault(); skip.focus();
      }
    }
  }

  function start() {
    const manual = new URLSearchParams(window.location.search).get('tutorial') === '1';
    let alreadyCompleted = false;
    try { alreadyCompleted = localStorage.getItem(completedKey) === 'true'; } catch (_) {}
    if (!manual && root.dataset.auto !== 'true' && alreadyCompleted) return;
    steps = makeSteps();
    if (!steps.length) return;
    previousFocus = document.activeElement;
    root.hidden = false;
    if (manual) {
      const url = new URL(window.location.href);
      url.searchParams.delete('tutorial');
      history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
    }
    showStep(0);
    skip.focus({ preventScroll: true });
    window.addEventListener('resize', schedulePosition);
    window.addEventListener('scroll', schedulePosition, true);
    document.addEventListener('keydown', onKeyDown);
  }

  next.addEventListener('click', () => current === steps.length - 1 ? finish() : showStep(current + 1));
  skip.addEventListener('click', finish);
  document.addEventListener('infia:dashboard-ready', start, { once: true });
  if (document.readyState !== 'loading') document.dispatchEvent(new Event('infia:dashboard-ready'));
})();
