/* Obrazovka Dnes: jedna hlavná akcia a týždeň. Sady sú v page-sets.js,
   čísla a graf v page-stats.js. Spoločné veci sú v app-core.js. */

/* ── INIT ── */
window.addEventListener('pageshow', async () => {
    setLang(currentLang);
    document.body.classList.add('stats-loading');
    await loadDashboard();
    // Predohrev offline stránok až po dátach — inak súťaží o linku práve
    // vtedy, keď čakáme na štatistiky.
    warmOfflinePages();
    setTimeout(() => document.body.classList.add('theme-ready'), 100);
});

/* Online: predohrej SW cache pre navigačné stránky, aby boli dostupné offline. */
function warmOfflinePages() {
    if (!navigator.onLine) return;
    ['/sady', '/profile', '/test', '/repeat'].forEach(path => {
        fetch(path, { credentials: 'include' }).catch(() => {});
    });
}

async function loadDashboard() {
    const { stats, fromServer } = await fetchDashboard();
    renderToday(stats, fromServer);
    renderStreak(stats);
    renderWeek(stats);
    document.body.classList.remove('stats-loading');
    if (fromServer) schedulePrefetch(allCategories);
}

/* Prefetch beží raz za načítanie stránky, až po `load` a potom v nečinnosti:
   timeout 4 s vynucoval spustenie aj vtedy, keď prehliadač ešte pracoval, a
   súťažil o to isté jedno vCPU s dotazmi, na ktoré používateľ čaká. */
let prefetchScheduled = false;
function schedulePrefetch(categories) {
    if (prefetchScheduled) return;
    prefetchScheduled = true;
    const run = () => prefetchAllWords(categories);
    const idle = () => 'requestIdleCallback' in window
        ? requestIdleCallback(run, { timeout: 15000 })
        : setTimeout(run, 5000);
    if (document.readyState === 'complete') idle();
    else window.addEventListener('load', idle, { once: true });
}

async function prefetchAllWords(categories) {
    if (!navigator.onLine || !categories?.length) return;
    if (window.WKOfflineCache) WKOfflineCache.prefetchAllCategories(categories);
}

/* ── ČO DNES ──
   Jedna sada, do ktorej sa oplatí ísť: najprv najslabšia podľa úspešnosti,
   inak tá, kde ostáva najviac slov. Zamknuté a hotové sady vypadávajú.
   `from=dnes` vráti používateľa z testu späť sem, nie na stránku sady. */
function openCategories() {
    const newestOwnId = newestOwnCategoryId(allCategories);
    return allCategories.filter(c => !isCategoryLocked(c, newestOwnId));
}

function pickNextCategory(stats) {
    const open = openCategories().filter(c => unknownCount(c) > 0);
    if (!open.length) return null;
    const weak = (stats?.weak_categories || []).find(w => open.some(c => c.id === w.id));
    if (weak) return open.find(c => c.id === weak.id);
    return open.reduce((a, b) => unknownCount(b) > unknownCount(a) ? b : a);
}

/* Všetko je „Viem": ostáva zopakovať si najväčšiu sadu. */
function pickReviewCategory() {
    const open = openCategories().filter(c => c.total_words > 0);
    if (!open.length) return null;
    return open.reduce((a, b) => b.total_words > a.total_words ? b : a);
}

function learnedToday(stats) {
    const today = new Date().toISOString().slice(0, 10);
    return (stats?.activity || []).some(a => a.date === today && a.tests > 0);
}

function setTodayCard({ title, meta, button, href, quiet = false }) {
    document.getElementById('todayTitle').textContent = title;
    document.getElementById('todayMeta').textContent = meta;
    document.getElementById('todayBtnText').textContent = button;
    const btn = document.getElementById('todayBtn');
    btn.href = href;
    btn.classList.toggle('primary', !quiet);
    btn.classList.toggle('outline', quiet);
}

function renderToday(stats, fromServer) {
    const sk = currentLang === 'sk';
    const next = pickNextCategory(stats);
    const review = next || pickReviewCategory();
    const testUrl = c => `/test?category=${c.id}${unknownCount(c) ? '&level=dont_know' : ''}&from=dnes`;

    if (!allCategories.length) {
        setTodayCard(fromServer ? {
            title: sk ? 'Vytvor si prvú sadu' : 'Create your first set',
            meta: sk ? 'Sada je zoznam slov, ktoré sa chceš naučiť. AI ti ju pripraví z témy alebo z fotky.'
                     : 'A set is a list of words you want to learn. AI builds it from a topic or a photo.',
            button: sk ? 'Vytvoriť sadu' : 'Create a set',
            href: '/sady?nova=1',
        } : {
            title: sk ? 'Si offline' : "You're offline",
            meta: sk ? 'Tvoje sady sa ukážu, keď budeš online.' : 'Your sets will show up once you are online.',
            button: sk ? 'Sady' : 'Sets',
            href: '/sady',
        });
        return;
    }
    if (!review) {
        setTodayCard({
            title: sk ? 'Pridaj si slová' : 'Add some words',
            meta: sk ? 'V tvojich sadách zatiaľ nie je čo sa učiť.' : 'There is nothing to learn in your sets yet.',
            button: sk ? 'Sady' : 'Sets',
            href: '/sady',
        });
        return;
    }
    if (learnedToday(stats)) {
        setTodayCard({
            title: sk ? 'Na dnes hotovo' : 'Done for today',
            meta: sk ? 'Zajtra pokračuj ďalej.' : 'Come back tomorrow.',
            button: sk ? 'Chcem ešte' : 'I want more',
            href: testUrl(review),
            quiet: true,
        });
        return;
    }
    if (next) {
        const n = unknownCount(next);
        const minutes = Math.max(1, Math.ceil(n / 3));
        setTodayCard({
            title: `${n} ${wordsLabel(n)}`,
            meta: sk ? `Zo sady ${next.name}. Asi ${minutes} min.` : `From ${next.name}. About ${minutes} min.`,
            button: sk ? 'Začať' : 'Start',
            href: testUrl(next),
        });
        return;
    }
    setTodayCard({
        title: sk ? 'Všetko vieš' : 'You know it all',
        meta: sk ? `Zopakuj si sadu ${review.name}, nech ti slová ostanú.` : `Go over ${review.name} so the words stick.`,
        button: sk ? 'Zopakovať' : 'Review',
        href: testUrl(review),
    });
}

function renderStreak(stats) {
    const n = stats?.streak_days || 0;
    const sk = currentLang === 'sk';
    const days = n === 1 ? 'deň' : (n >= 2 && n <= 4) ? 'dni' : 'dní';
    document.getElementById('streakText').textContent = !n ? ''
        : sk ? `${n} ${days} v rade` : `${n}-day streak`;
}

/* Týždeň od pondelka. Dni aktivity ráta server v UTC, preto aj tu. */
function renderWeek(stats) {
    const active = new Set((stats?.activity || [])
        .filter(a => (a.tests || 0) + (a.reviews || 0) > 0).map(a => a.date));
    const now = new Date();
    const todayIndex = (now.getUTCDay() + 6) % 7;
    const names = currentLang === 'sk'
        ? ['Po', 'Ut', 'St', 'Št', 'Pi', 'So', 'Ne']
        : ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
    let done = 0;
    document.getElementById('weekDots').innerHTML = names.map((name, i) => {
        const day = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - todayIndex + i));
        const on = active.has(day.toISOString().slice(0, 10));
        if (on) done++;
        return `<div class="week-day ${on ? 'on' : ''} ${i === todayIndex ? 'today' : ''}"><span></span>${name}</div>`;
    }).join('');
    document.getElementById('weekCount').textContent = currentLang === 'sk' ? `${done} z 7 dní` : `${done} of 7 days`;
}
