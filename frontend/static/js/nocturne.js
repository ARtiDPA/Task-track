/* Decorative renderer. No network, no app-state changes, one capped animation loop. */
(() => {
  'use strict';
  const canvas = document.getElementById('matrix-rain');
  const context = canvas?.getContext('2d');
  const preference = matchMedia('(prefers-reduced-motion: reduce)');
  let enabled = !preference.matches;
  try { enabled = localStorage.getItem('ritmo.effects') !== 'off' && !preference.matches; } catch {}
  const controls = [...document.querySelectorAll('.effects-toggle')];
  const authControl = controls[0]?.cloneNode(true);
  if (authControl) {
    authControl.classList.add('auth-effects');
    document.body.append(authControl);
    controls.push(authControl);
  }
  let frame = 0;
  let last = 0;
  let width = 0;
  let height = 0;
  let drops = [];
  const glyphs = '01アカサタナハマヤラワリトモ:+<>/';
  function resize() {
    if (!context) return;
    width = innerWidth;
    height = innerHeight;
    const ratio = Math.min(devicePixelRatio || 1, 1.5);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    drops = Array.from({length: Math.ceil(width / 26)}, () => Math.random() * height / 18);
  }
  function draw(time) {
    if (!enabled || preference.matches || document.hidden || !context) { frame = 0; return; }
    frame = requestAnimationFrame(draw);
    if (time - last < 65) return;
    last = time;
    context.fillStyle = 'rgba(6,10,9,.075)';
    context.fillRect(0, 0, width, height);
    context.font = '12px ui-monospace, monospace';
    drops.forEach((row, index) => {
      context.fillStyle = Math.random() > .98 ? '#c3f9d2' : '#4b9864';
      context.fillText(glyphs[Math.floor(Math.random() * glyphs.length)], index * 26, row * 18);
      drops[index] = row * 18 > height && Math.random() > .98 ? -Math.random() * 30 : row + .38;
    });
  }
  function sync() {
    const active = enabled && !preference.matches;
    document.documentElement.classList.toggle('effects-off', !active);
    controls.forEach(control => {
      control.setAttribute('aria-pressed', String(active));
      control.querySelector('span').textContent = active ? 'ON' : 'OFF';
    });
    // The fixed auth control stays available even before login.
    if (authControl) authControl.hidden = !document.body.classList.contains('auth-open');
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    if (active && !document.hidden && context) frame = requestAnimationFrame(draw);
  }
  controls.forEach(control => control.addEventListener('click', () => {
    enabled = !enabled;
    try { localStorage.setItem('ritmo.effects', enabled ? 'on' : 'off'); } catch {}
    sync();
  }));
  new MutationObserver(sync).observe(document.body, {attributes:true, attributeFilter:['class']});
  preference.addEventListener('change', sync);
  document.addEventListener('visibilitychange', sync);
  let resizeTimer;
  addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(resize, 120); });
  resize();
  sync();
})();
