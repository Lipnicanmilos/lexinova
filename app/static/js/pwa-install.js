/* LexiNova – PWA install button (zdieľané pre index/dashboard/repeat).
 * Očakáva tlačidlo s id="installBtn" a/alebo ľubovoľné prvky s atribútom
 * [data-pwa-install] (napr. položka v mobilnom menu). Ak nič nenájde, nerobí nič.
 * - Ak appka beží nainštalovaná (standalone), tlačidlá zostanú skryté.
 * - Chromium: beforeinstallprompt -> natívny prompt.
 * - iOS Safari: event neexistuje -> tlačidlo sa zobrazí a po kliknutí
 *   sa ukáže návod "Zdieľať -> Pridať na plochu".
 */
(function () {
    'use strict';

    const btns = Array.from(document.querySelectorAll('#installBtn, [data-pwa-install]'));
    if (!btns.length) return;

    const isStandalone =
        window.matchMedia('(display-mode: standalone)').matches ||
        window.navigator.standalone === true;
    if (isStandalone) { btns.forEach(b => { b.style.display = 'none'; }); return; }

    const showBtn = () => btns.forEach(b => {
        // data-display (mobilne menu = flex) > icon-btn v hlavicke (inline-flex) > index (inline-block)
        b.style.display = b.dataset.display ||
            (b.classList.contains('icon-btn') ? 'inline-flex' : 'inline-block');
    });
    const hideBtn = () => btns.forEach(b => { b.style.display = 'none'; });
    const lang = () => localStorage.getItem('preferredLang') || 'sk';

    /* ── Chromium (Android, desktop Chrome/Edge) ── */
    let deferredPrompt = null;
    window.addEventListener('beforeinstallprompt', e => {
        e.preventDefault();
        deferredPrompt = e;
        showBtn();
    });
    window.addEventListener('appinstalled', () => {
        deferredPrompt = null;
        hideBtn();
    });

    /* ── iOS Safari – beforeinstallprompt neexistuje ── */
    const ua = window.navigator.userAgent;
    const isIos = /iphone|ipad|ipod/i.test(ua) ||
        (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1); // iPadOS sa hlasi ako Mac
    if (isIos) showBtn();

    function showIosGuide() {
        let ov = document.getElementById('pwaIosGuide');
        if (!ov) {
            ov = document.createElement('div');
            ov.id = 'pwaIosGuide';
            ov.style.cssText =
                'position:fixed;inset:0;z-index:9999;background:rgba(15,23,42,.55);' +
                'display:flex;align-items:center;justify-content:center;padding:1.25rem;';
            const sk = lang() === 'sk';
            ov.innerHTML =
                '<div style="background:#fff;color:#1e293b;border-radius:16px;max-width:340px;width:100%;' +
                'padding:1.5rem;text-align:center;font-size:.95rem;line-height:1.55;box-shadow:0 20px 60px rgba(0,0,0,.25);">' +
                '<div style="font-size:2rem;">📲</div>' +
                '<h3 style="margin:.5rem 0 .75rem;font-size:1.05rem;">' +
                (sk ? 'Inštalácia na iPhone/iPad' : 'Install on iPhone/iPad') + '</h3>' +
                '<p style="margin:0 0 .5rem;">' +
                (sk ? '1. Ťukni na tlačidlo <strong>Zdieľať</strong> <span style="font-size:1.1em;">⎋</span> v spodnej lište Safari.'
                    : '1. Tap the <strong>Share</strong> <span style="font-size:1.1em;">⎋</span> button in the Safari toolbar.') + '</p>' +
                '<p style="margin:0 0 1rem;">' +
                (sk ? '2. Vyber <strong>Pridať na plochu</strong> <span style="font-size:1.1em;">➕</span>.'
                    : '2. Choose <strong>Add to Home Screen</strong> <span style="font-size:1.1em;">➕</span>.') + '</p>' +
                '<button type="button" id="pwaIosGuideClose" style="padding:.55rem 1.6rem;border:none;border-radius:50px;' +
                'background:#4079ff;color:#fff;font-weight:600;cursor:pointer;font-size:.9rem;">' +
                (sk ? 'Rozumiem' : 'Got it') + '</button></div>';
            document.body.appendChild(ov);
            ov.addEventListener('click', e => { if (e.target === ov) ov.remove(); });
            ov.querySelector('#pwaIosGuideClose').addEventListener('click', () => ov.remove());
        }
    }

    btns.forEach(btn => btn.addEventListener('click', async () => {
        if (deferredPrompt) {
            deferredPrompt.prompt();
            const { outcome } = await deferredPrompt.userChoice;
            deferredPrompt = null;
            if (outcome === 'accepted') hideBtn();
        } else if (isIos) {
            showIosGuide();
        }
    }));
})();
