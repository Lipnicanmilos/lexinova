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
    const { stats, today, fromServer } = await fetchDashboard(true);
    renderToday(stats, today, fromServer);
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
   Dávku skladá server naprieč sadami (services/learning.py), tu sa len povie,
   koľko jej je. „Hotovo" neznamená, že došli nové slová: keď nič nie je na rade
   a dnes sa už učilo, je pokoj — inak by 200-slovná sada nedala nikdy hotovo. */
function hasOpenWords() {
    const newestOwnId = newestOwnCategoryId(allCategories);
    return allCategories.some(c => !isCategoryLocked(c, newestOwnId) && c.total_words > 0);
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

function renderToday(stats, today, fromServer) {
    const sk = currentLang === 'sk';

    if (!today) {
        setTodayCard({
            title: sk ? 'Si offline' : "You're offline",
            meta: sk ? 'Učenie potrebuje pripojenie. Kartičky zo sád fungujú aj bez neho.'
                     : 'Learning needs a connection. Flashcards in your sets work without one.',
            button: sk ? 'Sady' : 'Sets',
            href: '/sady',
        });
        return;
    }
    if (!allCategories.length) {
        setTodayCard({
            title: sk ? 'Vytvor si prvú sadu' : 'Create your first set',
            meta: sk ? 'Sada je zoznam slov, ktoré sa chceš naučiť. AI ti ju pripraví z témy alebo z fotky.'
                     : 'A set is a list of words you want to learn. AI builds it from a topic or a photo.',
            button: sk ? 'Vytvoriť sadu' : 'Create a set',
            href: '/sady/nova',
        });
        return;
    }
    if (!hasOpenWords()) {
        setTodayCard({
            title: sk ? 'Pridaj si slová' : 'Add some words',
            meta: sk ? 'V tvojich sadách zatiaľ nie je čo sa učiť.' : 'There is nothing to learn in your sets yet.',
            button: sk ? 'Sady' : 'Sets',
            href: '/sady',
        });
        return;
    }

    const learned = learnedToday(stats);
    if (today.due > 0 || (today.new > 0 && !learned)) {
        const n = Math.min(today.session_size, today.due + today.new);
        const minutes = Math.max(1, Math.ceil(n / 3));
        setTodayCard({
            title: `${n} ${wordsLabel(n)}`,
            meta: sk ? `Asi ${minutes} min. Vyberiem ich za teba.` : `About ${minutes} min. I'll pick them for you.`,
            button: sk ? 'Začať' : 'Start',
            href: '/ucenie',
        });
        return;
    }
    // Nové slová čakajú aj po dnešnom učení; bez nich ide učenie navyše.
    const more = today.new > 0 ? '/ucenie' : '/ucenie?extra=1';
    setTodayCard(learned ? {
        title: sk ? 'Na dnes hotovo' : 'Done for today',
        meta: sk ? 'Ďalšie slová prídu zajtra.' : 'More words will come tomorrow.',
        button: sk ? 'Chcem ešte' : 'I want more',
        href: more,
        quiet: true,
    } : {
        title: sk ? 'Dnes nič nečaká' : 'Nothing due today',
        meta: sk ? 'Všetko máš zopakované.' : 'You are all caught up.',
        button: sk ? 'Chcem ešte' : 'I want more',
        href: more,
        quiet: true,
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
