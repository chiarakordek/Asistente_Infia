(() => {
  const text = document.getElementById('authTypewriter');
  if (!text) return;

  const examples = [
    'Hoy se animó a compartir sus ideas durante el juego.',
    'Contó cómo resolvió el desafío y escuchó a sus compañeros.',
    'Buscó distintas formas de construir la torre.',
    'Pidió ayuda y después pudo retomar la actividad.'
  ];
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reducedMotion) {
    text.textContent = `“${examples[0]}”`;
    return;
  }

  const wait = ms => new Promise(resolve => window.setTimeout(resolve, ms));
  const whenVisible = () => document.hidden
    ? new Promise(resolve => document.addEventListener('visibilitychange', resolve, { once: true }))
    : Promise.resolve();

  async function animateExamples() {
    let exampleIndex = 0;
    while (true) {
      await whenVisible();
      const example = examples[exampleIndex];
      const characters = Array.from(example);
      text.textContent = '“';
      for (const character of characters) {
        text.textContent += character;
        await wait(34 + Math.random() * 26);
      }
      text.textContent += '”';
      await wait(1900);
      for (let remaining = characters.length + 2; remaining > 0; remaining--) {
        text.textContent = Array.from(text.textContent).slice(0, -1).join('');
        await wait(17);
      }
      await wait(240);
      exampleIndex = (exampleIndex + 1) % examples.length;
    }
  }

  animateExamples();
})();
