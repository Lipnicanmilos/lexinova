/* Naklonenie kariet za kurzorom: nastavuje --tilt-x a --tilt-y, zvyšok je v CSS.
   Poslucháč je na dokumente, lebo kartičky a zoznamy kreslí JS až po načítaní.
   Na dotyku a pri „obmedziť pohyb" sa nespustí, karty vtedy stoja rovno. */
(function () {
  if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var MAX_DEG = 6;
  var active = null;

  function reset(el) {
    el.style.removeProperty('--tilt-x');
    el.style.removeProperty('--tilt-y');
  }

  document.addEventListener('pointermove', function (e) {
    var el = e.target.closest ? e.target.closest('[data-tilt], .flashcard, .card-hover, .set-card') : null;
    if (active && active !== el) reset(active);
    active = el;
    if (!el) return;
    var box = el.getBoundingClientRect();
    var x = (e.clientX - box.left) / box.width - 0.5;
    var y = (e.clientY - box.top) / box.height - 0.5;
    el.style.setProperty('--tilt-x', (-y * 2 * MAX_DEG).toFixed(2) + 'deg');
    el.style.setProperty('--tilt-y', (x * 2 * MAX_DEG).toFixed(2) + 'deg');
  }, { passive: true });

  document.documentElement.addEventListener('pointerleave', function () {
    if (active) reset(active);
    active = null;
  });
})();
