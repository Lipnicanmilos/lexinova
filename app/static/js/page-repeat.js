/* Presunute z repeat.html — inline JS sa nedalo cachovat. */
let words = [], currentIndex = 0, isFlipped = false;
    // Kolko kartičiek prehrávanie prešlo od posledného zápisu. Opakovanie
    // doteraz neposielalo nič, takže sa čas strávený učením nikde neprejavil.
    let reviewedCount = 0;
    let categoryId = null, level = null, currentUserId = null;
    let speechSynth = window.speechSynthesis;
    let isAutoPlaying = false, shuffledIndices = [], autoPlayIndex = 0;
    let originalLanguage = 'en-US', translationLanguage = 'sk-SK';

    /* Auto Play beh: `playToken` ruší staré slučky (stop/skip/reštart), aby po
       prerušení nebežali dve naraz. `langIsManual` = používateľ si jazyk zvolil
       ručne, takže sa už neprepisuje jazykom zo slovíčka. */
    let playToken = 0, isPaused = false, langIsManual = false, wakeLock = null;
    let playSettings = { repeat: '1', rate: 0.85, gap: 800, shuffle: true, loop: false };

    const SETTINGS_KEY = 'wk_repeat_play_settings';
    const LANG_KEY_PREFIX = 'wk_repeat_lang_';

    /* Krátky kód z DB ("en") → locale pre Web Speech ("en-US") — zo zdieľaného
       `speech.js`, ktorý rovnaké mapovanie používa aj na kartičkách a v deme. */
    const toLocale = LexiSpeech.toLocale;

    /* Pauzy sa dajú zrušiť: `clearAutoPlayTimers` ich rovno doresolvuje, aby
       čakajúca slučka pokračovala a sama sa ukončila na kontrole tokenu
       (inak by promise nikdy nedobehol a slučka by visela). */
    let pendingSleeps = [];
    function sleep(ms) {
        return new Promise(resolve => {
            const id = setTimeout(() => {
                pendingSleeps = pendingSleeps.filter(s => s.id !== id);
                resolve();
            }, ms);
            pendingSleeps.push({ id, resolve });
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        initOfflineUI();

        const params = new URLSearchParams(window.location.search);
        categoryId = params.get('category');
        level      = params.get('level');  // null = všetky levely ("Všetky slová")

        if (!categoryId) { showMessage('Invalid parameters', 'error'); document.getElementById('loading').style.display = 'none'; return; }

        loadPlaySettings();
        wirePlaySettings();
        loadLangOverride();
        loadVoices();   // priebežné dopĺňanie hlasov si `speech.js` rieši sám

        /* Ručná zmena jazyka prebije jazyk uložený pri slovíčku a pamätá sa
           pre danú kategóriu (rôzne kategórie = rôzne jazykové páry). */
        document.getElementById('originalLangSelect').addEventListener('change', e => {
            originalLanguage = e.target.value; langIsManual = true; saveLangOverride();
        });
        document.getElementById('translationLangSelect').addEventListener('change', e => {
            translationLanguage = e.target.value; langIsManual = true; saveLangOverride();
        });

        const savedLang = localStorage.getItem('preferredLang') || 'en';
        setLang(savedLang);
        document.querySelectorAll('.lang-btn').forEach(b => b.addEventListener('click', () => {
            setLang(b.dataset.lang); localStorage.setItem('preferredLang', b.dataset.lang);
        }));

        loadUserData();

        document.addEventListener('keydown', e => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
            if (e.key === 'ArrowRight') nextWord();
            else if (e.key === 'ArrowLeft') previousWord();
            else if ((e.key === 'ArrowUp' || e.key === ' ') && !isFlipped) { e.preventDefault(); flipCard(); }
            else if (e.key === 'ArrowDown' && isFlipped) { e.preventDefault(); flipCard(); }
        });
    });

    /* ── MOBILE MENU ── */
    const menuToggle = document.getElementById('menuToggle');
    const mobileNav  = document.getElementById('mobileNav');
    menuToggle.addEventListener('click', () => {
        mobileNav.classList.toggle('open');
        menuToggle.textContent = mobileNav.classList.contains('open') ? '✕' : '☰';
    });


    /* ── LANG ── */
    function setLang(lang) {
        document.querySelectorAll('.lang-btn').forEach(b => b.classList.toggle('active', b.dataset.lang === lang));
        document.querySelectorAll('[data-en],[data-sk]').forEach(el => { const t = el.getAttribute(`data-${lang}`); if(t) el.textContent = t; });
        // Pauza má dva stavy, preklad by ju inak vrátil vždy na „Pause".
        if (isAutoPlaying) setPauseLabel();
    }

    /* Texty skladané v JS nemá čo preložiť cez data-en/data-sk — jazyk treba
       prečítať v momente použitia, aby prepnutie EN/SK zabralo aj na ne. */
    function uiLang() { return localStorage.getItem('preferredLang') || 'en'; }

    /* ── OFFLINE ── */
    function initOfflineUI() {
        // Pozn.: currentLang tu neexistuje (stránka používa data-en/data-sk) — čítaj z localStorage.
        const sk = (localStorage.getItem('preferredLang') || 'en') === 'sk';
        if (!navigator.onLine) showMessage(sk?'Offline: zobrazenie z cache.':'Offline: showing cached data.','error');
        window.addEventListener('online',  () => showMessage(sk?'Online: dáta sa obnovia.':'Online: data will update.','success'));
        window.addEventListener('offline', () => showMessage(sk?'Offline: zobrazenie z cache.':'Offline: showing cached data.','error'));
    }

    /* ── USER + WORDS ── */
    async function loadUserData() {
        try {
            const res  = await fetch('/api/user', { credentials:'same-origin' });
            const user = await res.json().catch(() => null);
            if (!res.ok || !user || !navigator.onLine) {
                currentUserId = parseInt(localStorage.getItem('wk_user_id')||'0')||null;
                setCategoryInfoFromCache();
                await loadWords(); return;
            }
            currentUserId = user.id;
            if (user.dark_mode) { document.documentElement.setAttribute('data-theme','dark'); localStorage.setItem('darkMode','true'); }
            else { document.documentElement.removeAttribute('data-theme'); localStorage.setItem('darkMode','false'); }
            await loadCategoryInfo();
            await loadWords();
        } catch {
            currentUserId = parseInt(localStorage.getItem('wk_user_id')||'0')||null;
            setCategoryInfoFromCache();
            try { await loadWords(); } catch {}
        }
    }

    /* Offline fallback: názov kategórie z dashboardovej cache (wk_cached_categories),
       aby podnadpis nezostal na „Načítavam…". */
    function setCategoryInfoFromCache() {
        try {
            const cats = JSON.parse(localStorage.getItem('wk_cached_categories') || '[]');
            const cat = cats.find(c => c && String(c.id) === String(categoryId));
            if (cat && cat.name) document.getElementById('categoryInfo').textContent = cat.name;
        } catch (e) { /* poškodená cache → nechaj pôvodný text */ }
    }

    async function loadCategoryInfo() {
        try {
            const res = await fetch(`/api/v1/categories/${categoryId}`, { credentials:'same-origin' });
            if (!res.ok) { setCategoryInfoFromCache(); return; }
            const cat = await res.json();
            const levelLabels = { dont_know:"Don't Know", learning:'Learning', know:'Know' };
            const label = level ? (levelLabels[level] || level)
                : (uiLang() === 'sk' ? 'Všetky slovíčka' : 'All words');
            const pct   = level ? (cat.level_percentages[level] || 0) : (cat.total_percentage ?? '');
            document.getElementById('categoryInfo').textContent =
                pct === '' ? `${cat.name} – ${label}` : `${cat.name} – ${label} (${pct}%)`;
        } catch { setCategoryInfoFromCache(); }
    }

    const { offlineWordsCacheKey, loadOfflineWordsFromCache, saveOfflineWordsToCache, prefetchCategoryLevel } = window.WKOfflineCache;

    async function loadWords() {
        const testDirection = 'original_to_translation';
        // level === null → "Všetky slová": pošli všetky levely a zlúč cache.
        const levelsToLoad = level ? [level] : ['dont_know', 'learning', 'know'];
        const cacheLevels  = level ? [level] : ['dont_know', 'know'];  // cache sa ukladá len pre tieto
        try {
            const res = await fetch('/api/v1/words/test/start', {
                method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin',
                body: JSON.stringify({ category_id:parseInt(categoryId), knowledge_levels:levelsToLoad, limit:1000, test_direction:testDirection })
            });
            if (!res.ok) throw new Error();
            const fresh = await res.json();
            if (!fresh.length) { showMessage('No words found for this level.','error'); document.getElementById('loading').style.display = 'none'; return; }
            // Ulož do cache (pri jednom levele per-level kľúč; pri "všetky" ulož pod každý level zvlášť nemáme rozdelené, tak ulož aspoň pod prvý).
            if (level) {
                saveOfflineWordsToCache(offlineWordsCacheKey({ categoryId, level, testDirection }), fresh);
            }
            words = fresh;
            prefetchOtherLevels(categoryId, level, testDirection);
        } catch {
            // Offline / chyba → zlúč cache z dostupných levelov.
            const seen = new Set();
            const merged = [];
            for (const lvl of cacheLevels) {
                const cached = loadOfflineWordsFromCache(offlineWordsCacheKey({ categoryId, level: lvl, testDirection }));
                if (!cached) continue;
                for (const w of cached) {
                    const id = w.id != null ? w.id : `${w.original_word}|${w.translation}`;
                    if (seen.has(id)) continue;
                    seen.add(id); merged.push(w);
                }
            }
            if (merged.length) { words = merged; showMessage('Offline: loaded from cache.','success'); }
            else { showMessage('Failed to load words (no cache).','error'); document.getElementById('loading').style.display = 'none'; return; }
        }
        document.getElementById('loading').style.display = 'none';
        document.getElementById('content').style.display = 'block';
        applyDetectedLanguages();
        updateProgress(); showCurrentWord();
    }

    async function prefetchOtherLevels(catId, currentLevel, dir) {
        if (!navigator.onLine) return;
        for (const lvl of window.WKOfflineCache.ALL_LEVELS.filter(l => l !== currentLevel)) {
            await prefetchCategoryLevel(catId, lvl, dir);
            await new Promise(r => setTimeout(r, 300));
        }
    }

    /* ── FLASHCARD ── */
    function showCurrentWord() {
        if (!words.length || currentIndex >= words.length) return;
        const w = words[currentIndex];
        const card = document.getElementById('flashcard');
        card.classList.remove('flipped'); isFlipped = false;
        document.getElementById('cardContent').textContent = w.original_word;
        document.getElementById('cardLabel').textContent   = 'Word';
        updateNavigationButtons();
    }

    function flipCard() {
        if (!words.length) return;
        const card = document.getElementById('flashcard');
        if (!isFlipped) {
            card.classList.add('flipped');
            document.getElementById('cardContent').textContent = words[currentIndex].translation;
            document.getElementById('cardLabel').textContent   = 'Translation';
        }
        isFlipped = !isFlipped;
    }

    function nextWord() {
        if (isAutoPlaying) { skipAutoPlay(1); return; }
        if (currentIndex < words.length - 1) { currentIndex++; updateProgress(); showCurrentWord(); }
        else { showMessage("You've reviewed all words! 🎉",'success'); stopAutoPlay(); }
    }

    function previousWord() {
        if (isAutoPlaying) { skipAutoPlay(-1); return; }
        if (currentIndex > 0) { currentIndex--; updateProgress(); showCurrentWord(); }
    }

    /* Skok v Auto Play sekvencii (± 1); prehrávanie plynulo pokračuje. */
    function skipAutoPlay(step) {
        const target = autoPlayIndex + step;
        if (target < 0 || target >= shuffledIndices.length) return;
        clearAutoPlayTimers();
        try { speechSynth.cancel(); } catch {}
        autoPlayIndex = target;
        isPaused = false; setPauseLabel();
        runAutoPlay();   // nový token ukončí predchádzajúcu slučku
    }

    function updateProgress() {
        const pct = ((currentIndex + 1) / words.length) * 100;
        document.getElementById('progressFill').style.width = pct + '%';
        document.getElementById('progressText').textContent = `${currentIndex + 1} / ${words.length}`;
    }

    function updateNavigationButtons() {
        const idx  = isAutoPlaying ? autoPlayIndex : currentIndex;
        const last = (isAutoPlaying ? shuffledIndices.length : words.length) - 1;
        document.getElementById('prevBtn').disabled = idx === 0;
        document.getElementById('nextBtn').disabled = idx === last;
    }

    /* ── NASTAVENIA PREHRÁVANIA ── */
    function loadPlaySettings() {
        try {
            const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}');
            playSettings = { ...playSettings, ...saved };
        } catch { /* poškodená cache → ostanú defaulty */ }
        document.getElementById('repeatCountSelect').value = playSettings.repeat;
        document.getElementById('rateSelect').value        = String(playSettings.rate);
        document.getElementById('gapSelect').value         = String(playSettings.gap);
        document.getElementById('shuffleCheck').checked    = !!playSettings.shuffle;
        document.getElementById('loopCheck').checked       = !!playSettings.loop;
    }

    function savePlaySettings() {
        try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(playSettings)); } catch {}
    }

    function wirePlaySettings() {
        document.getElementById('repeatCountSelect').addEventListener('change', e => {
            playSettings.repeat = e.target.value; savePlaySettings();
        });
        document.getElementById('rateSelect').addEventListener('change', e => {
            playSettings.rate = parseFloat(e.target.value) || 0.85; savePlaySettings();
        });
        document.getElementById('gapSelect').addEventListener('change', e => {
            playSettings.gap = parseInt(e.target.value, 10) || 800; savePlaySettings();
        });
        document.getElementById('shuffleCheck').addEventListener('change', e => {
            playSettings.shuffle = e.target.checked; savePlaySettings();
        });
        document.getElementById('loopCheck').addEventListener('change', e => {
            playSettings.loop = e.target.checked; savePlaySettings();
        });
    }

    /* ── JAZYKY ── */
    function langKey() { return LANG_KEY_PREFIX + categoryId; }

    function loadLangOverride() {
        try {
            const saved = JSON.parse(localStorage.getItem(langKey()) || 'null');
            if (saved && saved.original && saved.translation) {
                originalLanguage = saved.original; translationLanguage = saved.translation;
                langIsManual = true;
                setSelectLang('originalLangSelect', originalLanguage);
                setSelectLang('translationLangSelect', translationLanguage);
            }
        } catch {}
    }

    function saveLangOverride() {
        try {
            localStorage.setItem(langKey(), JSON.stringify({
                original: originalLanguage, translation: translationLanguage,
            }));
        } catch {}
    }

    /* Doplní option, keď jazyk zo slovíčka nie je v pevnom zozname (napr. cs-CZ). */
    function setSelectLang(selectId, locale) {
        const sel = document.getElementById(selectId);
        if (!sel) return;
        if (!Array.from(sel.options).some(o => o.value === locale)) {
            const opt = document.createElement('option');
            opt.value = locale; opt.textContent = locale;
            sel.appendChild(opt);
        }
        sel.value = locale;
    }

    /* Jazyky sa berú zo slovíčka (language_from/language_to z API), takže napr.
       nemecká kategória sa číta nemeckým hlasom bez ručného prepínania.
       Ručná voľba v rozbaľovacom zozname má prednosť. */
    function langForWord(w, isOriginal) {
        if (langIsManual) return isOriginal ? originalLanguage : translationLanguage;
        return isOriginal ? toLocale(w.language_from, 'en-US')
                          : toLocale(w.language_to,   'sk-SK');
    }

    function applyDetectedLanguages() {
        if (langIsManual || !words.length) return;
        const w = words[0];
        originalLanguage    = toLocale(w.language_from, 'en-US');
        translationLanguage = toLocale(w.language_to,   'sk-SK');
        setSelectLang('originalLangSelect', originalLanguage);
        setSelectLang('translationLangSelect', translationLanguage);
    }

    /* ── SPEECH ── */
    /* Výber hlasu, poistný timeout aj `onend`-riadená sekvencia žijú v zdieľanom
       `speech.js` — tu ostávajú len aliasy, aby zvyšok prehrávača ostal rovnaký.
       `speakAsync` dobehne až koncom reči, takže tempo drží skutočná dĺžka slova. */
    const loadVoices = LexiSpeech.refreshVoices;
    const speakAsync = LexiSpeech.speakAsync;

    /* ── WAKE LOCK (dlhé prehrávanie na mobile) ── */
    async function requestWakeLock() {
        try { if ('wakeLock' in navigator) wakeLock = await navigator.wakeLock.request('screen'); } catch {}
    }
    function releaseWakeLock() {
        try { if (wakeLock) wakeLock.release(); } catch {}
        wakeLock = null;
    }
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible' && isAutoPlaying && !wakeLock) requestWakeLock();
    });

    /* ── AUTO PLAY ── */
    function buildOrder() {
        const order = Array.from({ length: words.length }, (_, i) => i);
        if (playSettings.shuffle) {
            for (let i = order.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [order[i], order[j]] = [order[j], order[i]];
            }
        }
        return order;
    }

    /* Kroky pre jedno slovíčko. `sandwich` (slovo → preklad → slovo) necháva
       učiaceho skončiť pri cudzom tvare, čo sa lepšie pamätá. */
    function buildSteps(w) {
        const o = { text: w.original_word, isOriginal: true };
        const t = { text: w.translation,   isOriginal: false };
        if (playSettings.repeat === 'sandwich') return [o, t, o];
        const n = parseInt(playSettings.repeat, 10) || 1;
        const steps = [];
        for (let i = 0; i < n; i++) steps.push(o, t);
        return steps;
    }

    function renderStep(w, step) {
        const card = document.getElementById('flashcard');
        if (step.isOriginal) {
            card.classList.remove('flipped'); isFlipped = false;
            document.getElementById('cardContent').textContent = w.original_word;
            document.getElementById('cardLabel').textContent   = 'Word';
        } else {
            card.classList.add('flipped'); isFlipped = true;
            document.getElementById('cardContent').textContent = w.translation;
            document.getElementById('cardLabel').textContent   = 'Translation';
        }
    }

    function updateAutoPlayProgress() {
        const total = shuffledIndices.length || words.length;
        const pct = ((autoPlayIndex + 1) / total) * 100;
        document.getElementById('progressFill').style.width = pct + '%';
        document.getElementById('progressText').textContent = `${autoPlayIndex + 1} / ${total}`;
    }

    function startAutoPlay() {
        if (!words.length || isAutoPlaying) return;
        isAutoPlaying = true; isPaused = false;
        shuffledIndices = buildOrder();
        autoPlayIndex = 0;
        document.getElementById('autoPlayBtn').style.display = 'none';
        document.getElementById('pauseBtn').style.display = 'inline-block';
        document.getElementById('stopBtn').style.display = 'inline-block';
        setPauseLabel();
        requestWakeLock();
        // Po dlhšej nečinnosti vie fronta reči uviaznuť v pauze.
        try { speechSynth.resume(); } catch {}
        runAutoPlay();
    }

    /* Zápis prehrávania do štatistík. Posiela sa pri zastavení a pri odchode
       zo stránky; `reviewedCount` sa hneď vynuluje, aby sa tie isté kartičky
       nezapočítali dvakrát. */
    function saveReview(useBeacon) {
        if (reviewedCount < 1) return;
        const payload = JSON.stringify({
            category_id: categoryId ? parseInt(categoryId, 10) : null,
            words_reviewed: reviewedCount,
        });
        reviewedCount = 0;
        try {
            if (useBeacon && navigator.sendBeacon) {
                navigator.sendBeacon('/api/v1/words/review/complete',
                    new Blob([payload], { type: 'application/json' }));
                return;
            }
            fetch('/api/v1/words/review/complete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: payload,
                keepalive: true,
            }).catch(() => {});
        } catch (e) { console.warn('Review not saved:', e); }
    }

    window.addEventListener('pagehide', () => saveReview(true));

    function stopAutoPlay() {
        saveReview(false);
        isAutoPlaying = false; isPaused = false;
        playToken++;
        try { speechSynth.cancel(); } catch {}
        clearAutoPlayTimers();
        releaseWakeLock();
        shuffledIndices = []; autoPlayIndex = 0;
        if (words.length) { updateProgress(); showCurrentWord(); }
        document.getElementById('autoPlayBtn').style.display = 'inline-block';
        document.getElementById('pauseBtn').style.display = 'none';
        document.getElementById('stopBtn').style.display = 'none';
    }

    function setPauseLabel() {
        const btn = document.getElementById('pauseBtn');
        const sk = (localStorage.getItem('preferredLang') || 'en') === 'sk';
        btn.textContent = isPaused ? (sk ? '▶ Pokračovať' : '▶ Resume')
                                   : (sk ? '⏸ Pauza'      : '⏸ Pause');
    }

    function togglePauseAutoPlay() {
        if (!isAutoPlaying) return;
        isPaused = !isPaused;
        if (isPaused) { try { speechSynth.cancel(); } catch {} }
        setPauseLabel();
    }

    function clearAutoPlayTimers() {
        pendingSleeps.forEach(s => { clearTimeout(s.id); s.resolve(); });
        pendingSleeps = [];
    }

    function waitWhilePaused(token) {
        return new Promise(resolve => {
            const check = () => {
                if (!isAutoPlaying || token !== playToken || !isPaused) { resolve(); return; }
                setTimeout(check, 150);
            };
            check();
        });
    }

    /* Hlavná slučka. `token` zabezpečí, že po stop/skip/reštarte dobehne len
       najnovšia — staré sa ticho ukončia na prvej kontrole. */
    async function runAutoPlay() {
        const token = ++playToken;
        while (isAutoPlaying && token === playToken) {
            if (autoPlayIndex >= shuffledIndices.length) {
                if (playSettings.loop) {
                    autoPlayIndex = 0;
                    if (playSettings.shuffle) shuffledIndices = buildOrder();
                } else {
                    stopAutoPlay();
                    showMessage(uiLang() === 'sk'
                        ? 'Hotovo! Prešiel si všetky slovíčka. 🎉'
                        : 'Auto-play done! All words reviewed. 🎉', 'success');
                    return;
                }
            }
            const w = words[shuffledIndices[autoPlayIndex]];
            updateAutoPlayProgress();
            updateNavigationButtons();

            for (const step of buildSteps(w)) {
                await waitWhilePaused(token);
                if (!isAutoPlaying || token !== playToken) return;
                renderStep(w, step);
                await speakAsync(step.text, langForWord(w, step.isOriginal), playSettings.rate);
                if (!isAutoPlaying || token !== playToken) return;
                await sleep(Math.round(playSettings.gap / 2));
                if (!isAutoPlaying || token !== playToken) return;
            }

            await sleep(playSettings.gap);
            if (!isAutoPlaying || token !== playToken) return;
            reviewedCount++;
            autoPlayIndex++;
        }
    }

    /* ── MESSAGE ── */
    function showMessage(msg, type) {
        const el = document.getElementById('message');
        el.textContent = msg; el.className = `msg ${type}`;
        setTimeout(() => { el.style.display = 'none'; el.className = 'msg'; }, 5000);
    }

    /* ── LOGOUT ── */
    function logout() { fetch('/api/v1/logout', {method:'POST'}).then(() => window.location.href = '/login'); }
