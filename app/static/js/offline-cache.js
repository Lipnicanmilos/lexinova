(function (global) {
    const OFFLINE_WORDS_KEY_PREFIX = 'offline_words_v1:';
    const ALL_LEVELS = ['dont_know', 'know'];
    const DEFAULT_TEST_DIRECTION = 'original_to_translation';
    const CACHE_MAX_AGE_MS = 24 * 60 * 60 * 1000;

    // Prefetch je prace na pozadi — bezi po jednom. Merania na produkcii
    // (2026-08-19): tri suvbezne requesty trvali 2220 ms kazdy oproti 1076 ms
    // samostatne, cize instancia suvbeznost neutiahne a prefetch by spomalil
    // presne to, na co pouzivatel caka.
    const MAX_CONCURRENCY = 1;

    function offlineWordsCacheKey({ categoryId, level, testDirection }) {
        return `${OFFLINE_WORDS_KEY_PREFIX}cat=${categoryId}&level=${level}&dir=${testDirection}`;
    }

    function loadOfflineWordsFromCache(cacheKey) {
        try {
            const raw = localStorage.getItem(cacheKey);
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            if (!parsed || !Array.isArray(parsed.words)) return null;
            if (typeof parsed.updated_at !== 'string') return null;
            return parsed.words;
        } catch (e) {
            return null;
        }
    }

    function saveOfflineWordsToCache(cacheKey, wordsToSave) {
        try {
            localStorage.setItem(cacheKey, JSON.stringify({
                updated_at: new Date().toISOString(),
                words: wordsToSave
            }));
        } catch (e) {
            console.warn('[WK] Offline cache save failed:', e);
        }
    }

    function isCacheFresh(cacheKey) {
        try {
            const raw = localStorage.getItem(cacheKey);
            if (!raw) return false;
            const parsed = JSON.parse(raw);
            if (!parsed || !parsed.updated_at) return false;
            const age = Date.now() - new Date(parsed.updated_at).getTime();
            return age < CACHE_MAX_AGE_MS;
        } catch (e) {
            return false;
        }
    }

    async function prefetchCategoryLevel(categoryId, level, testDirection = DEFAULT_TEST_DIRECTION) {
        const cacheKey = offlineWordsCacheKey({ categoryId, level, testDirection });
        if (isCacheFresh(cacheKey)) {
            return;
        }

        try {
            const res = await fetch('/api/v1/words/test/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({
                    category_id: parseInt(categoryId, 10),
                    knowledge_levels: [level],
                    limit: 1000,
                    test_direction: testDirection
                })
            });

            if (!res.ok) return;

            const words = await res.json();
            if (words.length > 0) {
                saveOfflineWordsToCache(cacheKey, words);
            }
        } catch (e) {
            console.warn(`[WK] Prefetch failed cat=${categoryId} level=${level}:`, e);
        }
    }

    // Spusti ulohy paralelne, ale max MAX_CONCURRENCY naraz (worker pool).
    async function runWithConcurrency(tasks, concurrency) {
        let index = 0;
        async function worker() {
            while (index < tasks.length) {
                const current = index++;
                await tasks[current]();
            }
        }
        const workers = [];
        for (let i = 0; i < Math.min(concurrency, tasks.length); i++) {
            workers.push(worker());
        }
        await Promise.all(workers);
    }

    // Jeden request na kategoriu namiesto jedneho na uroven. Server vracia
    // knowledge_level pri kazdom slove, takze rozdelenie do dvoch cache klucov
    // zvladne prehliadac sam — a dashboard nemusi cakat na dve volania po 2,5 s,
    // ktore si na jednom vCPU navzajom prekazaju.
    async function prefetchCategoryAllLevels(categoryId, testDirection = DEFAULT_TEST_DIRECTION) {
        const keys = ALL_LEVELS.map(level =>
            ({ level, cacheKey: offlineWordsCacheKey({ categoryId, level, testDirection }) })
        );
        if (keys.every(k => isCacheFresh(k.cacheKey))) return;

        try {
            const res = await fetch('/api/v1/words/test/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({
                    category_id: parseInt(categoryId, 10),
                    knowledge_levels: ALL_LEVELS,
                    limit: 1000,
                    test_direction: testDirection
                })
            });
            if (!res.ok) return;

            const words = await res.json();
            if (!words.length) return;   // prazdna odpoved sa neuklada (mohla by byt chyba)

            for (const { level, cacheKey } of keys) {
                const forLevel = words.filter(w => w.knowledge_level === level);
                if (forLevel.length) saveOfflineWordsToCache(cacheKey, forLevel);
            }
        } catch (e) {
            console.warn(`[WK] Prefetch failed cat=${categoryId}:`, e);
        }
    }

    // Kolko kategorii sa predsťahuje. Offline sa realne otvaraju posledne
    // pouzivane sady; stahovat vsetky znamena s kazdou dalsou sadou dlhsie
    // zatazovat server presne vtedy, ked pouzivatel caka na dashboard.
    const PREFETCH_MAX_CATEGORIES = 3;

    async function prefetchAllCategories(categories, testDirection = DEFAULT_TEST_DIRECTION) {
        if (!navigator.onLine || !categories || categories.length === 0) return;

        const recent = [...categories]
            .filter(cat => cat && cat.id)
            .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
            .slice(0, PREFETCH_MAX_CATEGORIES);

        const tasks = recent.map(cat =>
            () => prefetchCategoryAllLevels(cat.id, testDirection)
        );

        await runWithConcurrency(tasks, MAX_CONCURRENCY);
    }

    // ── Offline fronta výsledkov testov ─────────────────────────────────────
    // Odpovede, ktoré sa nepodarilo odoslať (offline / výpadok), sa uložia sem
    // a automaticky odošlú po návrate online. Každá dávka = jeden test
    // (jeden POST → jedna TestSession na serveri, aby sedel streak a graf).
    const PENDING_RESULTS_KEY = 'wk_pending_test_results_v1';

    function queueTestResults(answers) {
        if (!answers || !answers.length) return;
        try {
            const raw = localStorage.getItem(PENDING_RESULTS_KEY);
            const batches = raw ? JSON.parse(raw) : [];
            batches.push({ queued_at: new Date().toISOString(), answers });
            localStorage.setItem(PENDING_RESULTS_KEY, JSON.stringify(batches));
        } catch (e) {
            console.warn('[WK] Ulozenie fronty vysledkov zlyhalo:', e);
        }
    }

    let flushingResults = false;

    async function flushPendingResults() {
        if (flushingResults || !navigator.onLine) return;
        let batches;
        try {
            batches = JSON.parse(localStorage.getItem(PENDING_RESULTS_KEY) || '[]');
        } catch (e) {
            batches = [];
        }
        if (!Array.isArray(batches) || !batches.length) return;

        flushingResults = true;
        try {
            while (batches.length) {
                const res = await fetch('/api/v1/words/test/submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify(batches[0].answers)
                });
                // 401/5xx → nechaj dávku vo fronte, skúsi sa nabudúce.
                if (!res.ok) break;
                batches.shift();
                localStorage.setItem(PENDING_RESULTS_KEY, JSON.stringify(batches));
            }
            if (!batches.length) console.log('[WK] Offline vysledky testov odoslane.');
        } catch (e) {
            console.warn('[WK] Odoslanie fronty vysledkov zlyhalo:', e);
        } finally {
            flushingResults = false;
        }
    }

    // Auto-flush: po návrate online a krátko po načítaní stránky.
    global.addEventListener('online', flushPendingResults);
    if (navigator.onLine) setTimeout(flushPendingResults, 2000);

    global.WKOfflineCache = {
        OFFLINE_WORDS_KEY_PREFIX,
        ALL_LEVELS,
        DEFAULT_TEST_DIRECTION,
        offlineWordsCacheKey,
        loadOfflineWordsFromCache,
        saveOfflineWordsToCache,
        isCacheFresh,
        prefetchCategoryLevel,
        prefetchCategoryAllLevels,
        prefetchAllCategories,
        queueTestResults,
        flushPendingResults
    };
})(window);
