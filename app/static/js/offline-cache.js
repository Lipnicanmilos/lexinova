(function (global) {
    const OFFLINE_WORDS_KEY_PREFIX = 'offline_words_v1:';
    const ALL_LEVELS = ['dont_know', 'learning', 'know'];
    const DEFAULT_TEST_DIRECTION = 'original_to_translation';
    const CACHE_MAX_AGE_MS = 24 * 60 * 60 * 1000;
    const REQUEST_DELAY_MS = 300;

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
            console.log(`[WK] Prefetch skip (fresh cache): cat=${categoryId} level=${level}`);
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
                console.log(`[WK] Prefetch uložený: cat=${categoryId} level=${level}, ${words.length} slov`);
            }
        } catch (e) {
            console.warn(`[WK] Prefetch failed cat=${categoryId} level=${level}:`, e);
        }
    }

    async function prefetchCategoryAllLevels(categoryId, testDirection = DEFAULT_TEST_DIRECTION) {
        for (const level of ALL_LEVELS) {
            await prefetchCategoryLevel(categoryId, level, testDirection);
            await new Promise(r => setTimeout(r, REQUEST_DELAY_MS));
        }
    }

    async function prefetchAllCategories(categories, testDirection = DEFAULT_TEST_DIRECTION) {
        if (!navigator.onLine || !categories || categories.length === 0) return;

        for (const cat of categories) {
            if (!cat || !cat.id) continue;
            await prefetchCategoryAllLevels(cat.id, testDirection);
            await new Promise(r => setTimeout(r, REQUEST_DELAY_MS));
        }

        console.log('[WK] Offline prefetch všetkých kategórií dokončený');
    }

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
        prefetchAllCategories
    };
})(window);
