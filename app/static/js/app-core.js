/* Spoločné veci obrazoviek Dnes, Sady a Štatistiky. Všetky tri ťahajú dáta
   z jedného `/api/dashboard` a rovnako rátajú zámok free účtu. */
let currentLang = localStorage.getItem('preferredLang') || 'sk';
let currentUserId = null;
let currentUserIsPlus = false;
let allCategories = [];

/* ── JAZYK ── */
function setLang(lang) {
    localStorage.setItem('preferredLang', lang);
    document.querySelectorAll('[data-en]').forEach(el => { const t = el.getAttribute(`data-${lang}`); if (t) el.textContent = t; });
    document.querySelectorAll('[data-en-placeholder]').forEach(el => { const t = el.getAttribute(`data-${lang}-placeholder`); if (t) el.placeholder = t; });
    // Ikonové tlačidlá nemajú text — názov pre čítačky obrazovky aj bublinu
    // treba prekladať zvlášť, inak ostane natvrdo v jednom jazyku.
    document.querySelectorAll('[data-en-label]').forEach(el => {
        const t = el.getAttribute(`data-${lang}-label`);
        if (t) { el.title = t; el.setAttribute('aria-label', t); }
    });
}

function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

/* Slovenčina má tri tvary: 1 slovo, 2–4 slová, 5+ slov. */
function wordsLabel(n) {
    if (currentLang !== 'sk') return n === 1 ? 'word' : 'words';
    return n === 1 ? 'slovo' : (n >= 2 && n <= 4) ? 'slová' : 'slov';
}

/* ── TOAST ── */
function showMessage(text, type = 'success') {
    const toast = document.getElementById('toast');
    const icon  = document.getElementById('toastIcon');
    const span  = document.getElementById('toastText');
    span.textContent = text;
    toast.style.background = type === 'success' ? 'var(--know)' : 'var(--danger)';
    icon.className = type === 'success' ? 'fa-solid fa-check-circle' : 'fa-solid fa-exclamation-circle';
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

/* ── POUŽÍVATEĽ ── */
function ensureOfflineBanner(offline) {
    if (document.getElementById('offlineBanner')) return;
    const b = document.createElement('div');
    b.id = 'offlineBanner';
    b.style.cssText = 'background:#f59e0b;color:#fff;text-align:center;padding:8px;font-weight:600;';
    const sk = currentLang === 'sk';
    b.textContent = offline
        ? (sk ? 'Offline – zobrazujú sa uložené dáta' : 'Offline – showing saved data')
        : (sk ? 'Server neodpovedá – zobrazujú sa uložené dáta' : 'The server is not responding – showing saved data');
    // Pod hlavičku: pred ňou ostal prilepený za ňou a nebolo ho vidieť.
    document.querySelector('.app-bar').after(b);
}

/* Uložené dáta sú len záloha na offline: keď sa localStorage zaplní, obrazovka
   má ísť ďalej so živými dátami zo servera. */
function saveLocal(key, value) {
    try { localStorage.setItem(key, value); }
    catch (e) { console.warn('[WK] Uloženie zlyhalo:', key, e); }
}

function applyUserData(user) {
    currentUserId     = user.id;
    currentUserIsPlus = user.is_plus;
    saveLocal('wk_user_name',   user.name || user.email);
    saveLocal('wk_user_id',     String(user.id || ''));
    saveLocal('wk_user_is_plus', String(!!user.is_plus));
    const isDarkServer = user.dark_mode;
    const isDarkLocal  = localStorage.getItem('darkMode') === 'true';
    if (isDarkServer !== isDarkLocal) {
        saveLocal('darkMode', isDarkServer);
        document.documentElement.setAttribute('data-theme', isDarkServer ? 'dark' : '');
    }
}

/* Bez dát zo servera: identita z poslednej návštevy. */
function applyOfflineUser(offline) {
    ensureOfflineBanner(offline);
    currentUserId     = parseInt(localStorage.getItem('wk_user_id') || '0') || null;
    currentUserIsPlus = localStorage.getItem('wk_user_is_plus') === 'true';
}

/* ── ZÁMOK FREE ÚČTU ──
   Free účet má odomknutú len najnovšiu vlastnú sadu, sady triedy vždy.
   Rovnaké pravidlo vynucuje server (_check_category_access) — zamknutý
   test vráti späť na Dnes, preto naň odtiaľto neodkazujeme. */
function newestOwnCategoryId(categories) {
    let newest = null;
    categories.forEach(c => {
        if (c.from_class) return;
        if (!newest || new Date(c.created_at || 0) > new Date(newest.created_at || 0)) newest = c;
    });
    return newest?.id ?? null;
}
function isCategoryLocked(c, newestOwnId) {
    return !currentUserIsPlus && !c.from_class && c.id !== newestOwnId;
}
function unknownCount(c) {
    return (c.level_counts?.dont_know || 0) + (c.level_counts?.learning || 0);
}

/* Celá obrazovka jedným requestom. Tri samostatné volania sa navzájom
   spomaľovali (merané: 3 súbežné 2220 ms každé oproti 1076 ms samostatne)
   a každé platilo vlastnú réžiu. Pri zlyhaní sa vykreslí z offline cache.
   `fromServer` rozlišuje prázdny účet od prázdnej offline cache. Dennú dávku
   (`withToday`) si pýta len obrazovka Dnes — stojí dotazy navyše.
   `failure` hovorí, čo zlyhalo: 'offline' len vtedy, keď prehliadač naozaj nemá
   sieť. Chyba servera nie je offline a používateľ ju nemá hľadať u seba. */
async function fetchDashboard(withToday = false) {
    let failure = 'network';
    try {
        const res = await fetch(withToday ? '/api/dashboard?today=1' : '/api/dashboard');
        failure = 'HTTP ' + res.status;
        if (!res.ok) throw new Error(failure);
        const data = await res.json();
        applyUserData(data.user);
        allCategories = Array.isArray(data.categories) ? data.categories : (data.categories?.categories || []);
        saveLocal('wk_cached_stats', JSON.stringify(data.stats));
        saveLocal('wk_cached_categories', JSON.stringify(allCategories));
        return { stats: data.stats, today: data.today || null, fromServer: true, failure: null };
    } catch (e) {
        console.warn('[WK] Dáta sa nenačítali, skúšam offline cache:', e);
        if (!navigator.onLine) failure = 'offline';
        applyOfflineUser(failure === 'offline');
        const stats = localStorage.getItem('wk_cached_stats');
        const cats  = localStorage.getItem('wk_cached_categories');
        allCategories = cats ? JSON.parse(cats) : [];
        return { stats: stats ? JSON.parse(stats) : null, today: null, fromServer: false, failure };
    }
}
