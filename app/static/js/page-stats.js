/* Štatistiky: čísla, graf aktivity a odznaky. Odkaz je v Profile; obrazovka
   Dnes ich zámerne neukazuje. Spoločné veci sú v app-core.js. */
window.addEventListener('pageshow', async () => {
    setLang(currentLang);
    document.body.classList.add('stats-loading');
    const { stats } = await fetchDashboard();
    if (stats) renderStats(stats);
    document.body.classList.remove('stats-loading');
    setTimeout(() => document.body.classList.add('theme-ready'), 100);
});

function renderStats(stats) {
    document.getElementById('statsTotalWords').textContent = stats.total_words ?? 0;
    renderLevelBar(stats);

    // Mastery prstenec + séria + na zopakovanie + netestované
    const masteryPct = stats.mastery_pct ?? 0;
    document.getElementById('masteryPct').textContent = `${masteryPct}%`;
    document.getElementById('masteryRing').style.setProperty('--pct', masteryPct);
    document.getElementById('masteryMastered').textContent = stats.words_by_level?.know ?? 0;
    document.getElementById('statStreak').textContent   = stats.streak_days ?? 0;
    document.getElementById('statToReview').textContent = stats.to_review ?? 0;
    document.getElementById('statUntested').textContent = stats.untested ?? 0;
    document.getElementById('statLearned7d').textContent = stats.learned_7d ?? 0;

    renderWeakCategories(stats);
    renderActivity(stats);
    renderBadges(stats);
    renderPlusStats(stats);
}

    /* Rozloženie znalosti ako jeden pruh namiesto dvoch holých čísel.
       Úrovne sú len dve; zrušené 'learning' zo starších riadkov patrí k "Neviem". */
    function renderLevelBar(stats) {
        const counts = stats.words_by_level || {};
        const dk = (counts.dont_know ?? 0) + (counts.learning ?? 0);
        const kn = counts.know ?? 0;
        const total = dk + kn;
        const pct = n => total ? Math.round(n / total * 100) : 0;
        const l = currentLang === 'sk'
            ? { dk: 'Neviem', kn: 'Viem', empty: 'Zatiaľ žiadne slovíčka' }
            : { dk: "Don't know", kn: 'Know', empty: 'No words yet' };
        const el = document.getElementById('statsWordsByLevel');
        if (!total) {
            el.innerHTML = `<small style="color:var(--muted)">${l.empty}</small>`;
            return;
        }
        const item = (level, label, count) => `
            <div><span class="level-dot ${level}"></span>
                <span>${label}</span> <b>${count}</b> <small>(${pct(count)}%)</small></div>`;
        el.innerHTML = `
            <div class="level-bar">
                <span class="seg-dk" style="width:${pct(dk)}%"></span>
                <span class="seg-kn"></span>
            </div>
            <div class="level-legend">
                ${item('dk', l.dk, dk)}
                ${item('kn', l.kn, kn)}
            </div>`;
    }

    /* Kde to nejde: 3 najslabšie kategórie rovno s tlačidlom do testu. */
    function renderWeakCategories(stats) {
        const panel = document.getElementById('weakPanel');
        const list  = document.getElementById('weakList');
        const items = Array.isArray(stats.weak_categories) ? stats.weak_categories : [];
        if (!items.length) { panel.style.display = 'none'; return; }
        const l = currentLang === 'sk'
            ? { success: 'úspešnosť', words: 'slov', practice: 'Precvičiť' }
            : { success: 'accuracy', words: 'words', practice: 'Practice' };
        // Kým kategórie nedobehli, zámok nepoznáme — sadu berieme ako odomknutú
        // a displayCategories() panel prekreslí.
        const newestOwnId = newestOwnCategoryId(allCategories);
        const locked = id => {
            const cat = allCategories.find(c => c.id === id);
            return cat ? isCategoryLocked(cat, newestOwnId) : false;
        };
        list.innerHTML = items.map(c => `
            <li>
                <span class="weak-name">${escapeHtml(c.name)}</span>
                <span class="weak-rate">${c.accuracy}%</span>
                <span class="weak-meta">${l.success} · ${c.words} ${l.words}</span>
                ${locked(c.id)
                    ? `<a class="weak-plus" href="/profile"><i class="fa-solid fa-lock"></i> PLUS</a>`
                    : `<a class="app-btn outline sm" href="/test?category=${c.id}&level=dont_know">${l.practice}</a>`}
            </li>`).join('');
        panel.style.display = 'block';
    }

    /* ── CHART.JS NA POŽIADANIE ──
       204 kB sa sťahovalo pri každom načítaní nástenky, aj keď graf je hlboko
       pod ohybom a väčšina návštev sa k nemu nedostane. Knižnica sa preto
       stiahne až keď sa prvý graf priblíži k oknu — dovtedy nesúťaží o pásmo
       s dotazmi, na ktoré používateľ čaká. */
    let chartLibPromise = null;
    function ensureChartLib() {
        if (window.Chart) return Promise.resolve();
        if (!chartLibPromise) {
            const version = document.querySelector('meta[name="app-version"]')?.content || '';
            chartLibPromise = new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = `/static/vendor/chartjs/chart.umd.min.js?v=${version}`;
                script.onload = resolve;
                script.onerror = reject;
                document.head.appendChild(script);
            });
        }
        return chartLibPromise;
    }

    /* Zavolá `draw`, keď je prvok na dohľad (200 px pred oknom). Bez podpory
       IntersectionObserver kreslíme rovno — radšej graf než prázdne miesto. */
    function drawWhenVisible(el, draw) {
        if (!el) return;
        const run = () => ensureChartLib().then(draw).catch(err =>
            console.warn('[WK] Graf sa nepodarilo vykreslit:', err));
        if (!('IntersectionObserver' in window)) { run(); return; }
        const observer = new IntersectionObserver((entries, obs) => {
            if (entries.some(entry => entry.isIntersecting)) { obs.disconnect(); run(); }
        }, { rootMargin: '200px' });
        observer.observe(el);
    }

    let activityChartInstance = null;
    function renderActivity(stats) {
        const canvas = document.getElementById('activityChart');
        if (!canvas) return;
        const act = Array.isArray(stats.activity) ? stats.activity : [];
        // Nadpis podľa skutočnej dĺžky histórie (PLUS má 30 dní, free 14)
        const daysN = act.length || 14;
        const head = document.getElementById('activityHead');
        if (head) {
            head.dataset.en = `Activity (${daysN} days)`;
            head.dataset.sk = `Aktivita (${daysN} dní)`;
            head.textContent = currentLang === 'sk' ? head.dataset.sk : head.dataset.en;
        }
        const labels = act.map(a => { const d = new Date(a.date); return `${d.getDate()}.${d.getMonth() + 1}`; });
        const tests  = act.map(a => a.tests ?? 0);
        const reviews = act.map(a => a.reviews ?? 0);
        const acc    = act.map(a => a.accuracy);   // null = žiadny test v daný deň
        const testsLabel   = currentLang === 'sk' ? 'Testy' : 'Tests';
        const reviewsLabel = currentLang === 'sk' ? 'Opakovania' : 'Reviews';
        const accLabel     = currentLang === 'sk' ? 'Úspešnosť' : 'Accuracy';

        drawWhenVisible(canvas, () => drawActivityChart(canvas, {
            labels, tests, reviews, acc, testsLabel, reviewsLabel, accLabel,
        }));
    }

    function drawActivityChart(canvas, d) {
        const { labels, tests, reviews, acc, testsLabel, reviewsLabel, accLabel } = d;
        // Canvas nevie čítať CSS premenné — farbu „Viem" si vytiahneme z tokenu.
        const know = getComputedStyle(document.documentElement).getPropertyValue('--know').trim() || '#2e9e62';
        if (activityChartInstance) activityChartInstance.destroy();
        activityChartInstance = new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    { type: 'bar', label: testsLabel, data: tests, backgroundColor: 'rgba(64,121,255,.45)', borderRadius: 6, yAxisID: 'y', stack: 'aktivita' },
                    // Opakovanie (auto-play) nemá správne/nesprávne odpovede, takže
                    // do krivky úspešnosti nevstupuje — v grafe je vlastný stĺpec.
                    // Ak v okne nebolo ani jedno, séria sa vynechá — legenda so
                    // stĺpcom, ktorý nikde nie je, len mätie.
                    ...(reviews.some(n => n > 0)
                        ? [{ type: 'bar', label: reviewsLabel, data: reviews, backgroundColor: 'rgba(64,121,255,.2)', borderRadius: 6, yAxisID: 'y', stack: 'aktivita' }]
                        : []),
                    { type: 'line', label: accLabel, data: acc, borderColor: know, backgroundColor: know, tension: .35, spanGaps: true, pointRadius: 3, yAxisID: 'y1' },
                ],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: true, labels: { boxWidth: 12 } } },
                scales: {
                    x:  { stacked: true, ticks: { autoSkip: true, maxTicksLimit: 15 } },
                    y:  { beginAtZero: true, stacked: true, ticks: { precision: 0 } },
                    y1: { position: 'right', beginAtZero: true, max: 100, grid: { drawOnChartArea: false }, ticks: { callback: v => v + '%' } },
                },
            },
        });
    }

    function renderBadges(stats) {
        const grid = document.getElementById('badgesGrid');
        if (!grid) return;
        const badges = Array.isArray(stats.badges) ? stats.badges : [];
        grid.innerHTML = badges.map(b => {
            const label = currentLang === 'sk' ? b.label_sk : b.label_en;
            const prog = b.earned ? '✓' : `${b.current}/${b.target}`;
            return `<div class="badge ${b.earned ? 'earned' : ''}" title="${escapeHtml(label)}">
                <div class="badge-icon">${b.icon}</div>
                <div class="badge-label">${escapeHtml(label)}</div>
                <div class="badge-prog">${prog}</div>
            </div>`;
        }).join('');
    }

    function renderPlusStats(stats) {
        const section = document.getElementById('plusStatsSection');
        if (!stats.is_plus) { section.style.display = 'none'; return; }

        // Úspešnosť za posledných 7 dní + trend oproti predchádzajúcemu týždňu
        const acc7 = stats.accuracy_7d;
        const prev7 = stats.accuracy_prev_7d;
        document.getElementById('plusSuccessRate').textContent = acc7 == null ? '—' : `${acc7}%`;
        const trendEl = document.getElementById('plusTrend');
        if (acc7 != null && prev7 != null) {
            const diff = acc7 - prev7;
            trendEl.textContent = diff > 0 ? `▲ +${diff} %` : diff < 0 ? `▼ ${diff} %` : '● 0 %';
            trendEl.style.color = diff > 0 ? 'var(--know-ink)' : diff < 0 ? 'var(--dont-ink)' : 'var(--muted)';
            trendEl.title = currentLang === 'sk' ? 'oproti predchádzajúcemu týždňu' : 'vs previous week';
        } else {
            trendEl.textContent = '';
        }

        // Priemer opakovaní na zvládnuté slovo; "Absolvované testy" berieme z
        // test_sessions — stats.tests_taken je súčet zodpovedaných kariet.
        document.getElementById('plusAvgReviews').textContent = stats.avg_reviews_to_master ?? '—';
        document.getElementById('plusTestsTaken').textContent = stats.tests_total ?? 0;

        section.style.display = 'block';
        setLang(currentLang);
    }
