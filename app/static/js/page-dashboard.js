/* Presunute z dashboard.html — inline JS sa nedalo cachovat. */
let currentLang    = localStorage.getItem('preferredLang') || 'sk';
    let currentUserId  = null;
    let currentUserIsPlus = false;
    let categoryToDelete  = null;
    let allCategories  = [];

    /* ── INIT ── */
    window.addEventListener('pageshow', async () => {
        setupLanguages();
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
        ['/profile', '/test', '/repeat'].forEach(path => {
            fetch(path, { credentials: 'include' }).catch(() => {});
        });
    }

    /* ── MOBILE MENU ── */
    const menuToggle = document.getElementById('menuToggle');
    const mobileNav  = document.getElementById('mobileNav');
    menuToggle.addEventListener('click', () => {
        mobileNav.classList.toggle('open');
        menuToggle.textContent = mobileNav.classList.contains('open') ? '✕' : '☰';
    });

    /* ── USER ── */
    function ensureOfflineBanner() {
        if (document.getElementById('offlineBanner')) return;
        const b = document.createElement('div');
        b.id = 'offlineBanner';
        b.style.cssText = 'background:#f59e0b;color:#fff;text-align:center;padding:8px;font-weight:600;position:sticky;top:64px;z-index:9999;';
        b.textContent = '⚠️ Offline – zobrazujú sa uložené dáta';
        document.body.prepend(b);
    }

    async function loadUserData() {
        try {
            const res  = await fetch('/api/user');
            if (!res.ok) throw new Error();
            applyUserData(await res.json());
        } catch {
            applyOfflineUser();
        }
    }

    function applyUserData(user) {
        document.getElementById('userEmailChip').textContent = user.name || user.email;
        currentUserId     = user.id;
        currentUserIsPlus = user.is_plus;
        if (user.is_admin) {
            document.getElementById('adminBtn').style.display = 'inline-flex';
            document.getElementById('adminBtnMobile').style.display = 'flex';
        }
        // Prvá trieda je zadarmo, takže odkaz patrí každému učiteľovi.
        // Žiacke (pseudonymné) kontá triedy nezakladajú.
        if (!user.is_pseudonymous) {
            document.getElementById('classesBtn').style.display = 'inline-flex';
            document.getElementById('classesBtnMobile').style.display = 'flex';
        }
        localStorage.setItem('wk_user_name',   user.name || user.email);
        localStorage.setItem('wk_user_id',     String(user.id || ''));
        localStorage.setItem('wk_user_is_plus', String(!!user.is_plus));
        const isDarkServer = user.dark_mode;
        const isDarkLocal  = localStorage.getItem('darkMode') === 'true';
        if (isDarkServer !== isDarkLocal) {
            localStorage.setItem('darkMode', isDarkServer);
            document.documentElement.setAttribute('data-theme', isDarkServer ? 'dark' : '');
        }
    }

    /* Offline: identita z poslednej návštevy, nech hlavička nie je prázdna. */
    function applyOfflineUser() {
        ensureOfflineBanner();
        document.getElementById('userEmailChip').textContent = localStorage.getItem('wk_user_name') || 'Offline';
        currentUserId     = parseInt(localStorage.getItem('wk_user_id') || '0') || null;
        currentUserIsPlus = localStorage.getItem('wk_user_is_plus') === 'true';
    }

    /* ── STATS ── */
    function renderStats(stats) {
        document.getElementById('statsTotalCategories').textContent = stats.total_categories ?? 0;
        document.getElementById('statsTotalWords').textContent = stats.total_words ?? 0;
        renderLevelBar(stats);

        // Mastery prstenec + streak + na zopakovanie + netestované
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
        const item = (color, label, count) => `
            <div><span class="dot" style="background:${color}"></span>
                <span>${label}</span> <b>${count}</b> <small>(${pct(count)}%)</small></div>`;
        el.innerHTML = `
            <div class="level-bar">
                <span class="seg-dk" style="width:${pct(dk)}%"></span>
                <span class="seg-kn"></span>
            </div>
            <div class="level-legend">
                ${item('#e53e3e', l.dk, dk)}
                ${item('#38a169', l.kn, kn)}
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
        list.innerHTML = items.map(c => `
            <li>
                <span class="weak-name">${escapeHtml(c.name)}</span>
                <span class="weak-rate">${c.accuracy}%</span>
                <span class="weak-meta">${l.success} · ${c.words} ${l.words}</span>
                <a class="btn-primary" href="/test?category=${c.id}&level=dont_know">${l.practice}</a>
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
                        ? [{ type: 'bar', label: reviewsLabel, data: reviews, backgroundColor: 'rgba(64,255,170,.4)', borderRadius: 6, yAxisID: 'y', stack: 'aktivita' }]
                        : []),
                    { type: 'line', label: accLabel, data: acc, borderColor: '#40ffaa', backgroundColor: '#40ffaa', tension: .35, spanGaps: true, pointRadius: 3, yAxisID: 'y1' },
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
            trendEl.style.color = diff > 0 ? '#38a169' : diff < 0 ? '#e53e3e' : 'var(--muted)';
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

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }

    function applyStats(stats) {
        localStorage.setItem('wk_cached_stats', JSON.stringify(stats));
        renderStats(stats);
        document.body.classList.remove('stats-loading');
    }

    function applyCategories(list) {
        allCategories = Array.isArray(list) ? list : (list.categories || []);
        localStorage.setItem('wk_cached_categories', JSON.stringify(allCategories));
        schedulePrefetch(allCategories);
        displayCategories(allCategories);
    }

    async function loadUserStats() {
        try {
            const res   = await fetch('/api/user/stats');
            if (!res.ok) throw new Error();
            applyStats(await res.json());
        } catch {
            const c = localStorage.getItem('wk_cached_stats');
            if (c) renderStats(JSON.parse(c));
        } finally {
            // Aj keď sa nepodarilo nič načítať — skeleton nesmie ostať navždy.
            document.body.classList.remove('stats-loading');
        }
    }

    /* ── CATEGORIES ── */
    async function loadCategories(userLoaded) {
        try {
            const res = await fetch('/api/v1/categories');
            if (!res.ok) throw new Error();
            const data = await res.json();
            // Zámok pre free účty sa riadi currentUserIsPlus — vykresliť sa dá
            // až keď je známy, inak by PLUS používateľ na moment videl zámky.
            await userLoaded;
            applyCategories(data);
        } catch {
            await userLoaded;
            const c = localStorage.getItem('wk_cached_categories');
            displayCategories(c ? JSON.parse(c) : []);
        }
    }

    /* Prefetch beží raz za načítanie stránky. loadCategories() sa volá aj po
       vytvorení či zmazaní sady, takže bez tejto poistky sa sťahovanie všetkých
       slovíčok spúšťalo trikrát za sebou (bolo to vidieť aj v konzole). */
    let prefetchScheduled = false;
    function schedulePrefetch(categories) {
        if (prefetchScheduled) return;
        prefetchScheduled = true;
        // Až po `load` a potom v nečinnosti. Timeout 4 s vynucoval spustenie aj
        // vtedy, keď prehliadač ešte pracoval — prefetch tak súťažil o to isté
        // jedno vCPU s dotazmi, na ktoré používateľ čaká.
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

    function displayCategories(categories) {
        const list = document.getElementById('categoriesList');
        const l = { sk:{dk:'Neviem 😕',kn:'Viem ✅',words:'SLOV',cls:'Trieda'}, en:{dk:"Don't Know 😕",kn:'Know ✅',words:'WORDS',cls:'Class'} }[currentLang];
        // Ikonové akcie na karte potrebujú názov pre čítačky obrazovky —
        // bez neho čítačka oznámi len „tlačidlo".
        const a = { sk:{share:'Zdieľať sadu',edit:'Premenovať sadu',del:'Zmazať sadu'},
                    en:{share:'Share set',edit:'Rename set',del:'Delete set'} }[currentLang];

        categories.sort((a,b) => new Date(b.created_at||0) - new Date(a.created_at||0));

        const pad  = n => String(n).padStart(2,'0');
        const fmt  = s => { if(!s) return ''; const d = new Date(s); return `${pad(d.getDate())}.${pad(d.getMonth()+1)}.${d.getFullYear()}`; };
        // Free lock „len najnovšia" sa týka len vlastných sád — sady triedy sú vždy odomknuté
        const newestOwnId = categories.find(c => !c.from_class)?.id ?? null;

        list.innerHTML = categories.map(c => {
            const locked = !currentUserIsPlus && !c.from_class && c.id !== newestOwnId;
            const actions = c.from_class
                ? `<span style="padding:.35rem .6rem;border-radius:8px;background:var(--grad);color:#0f172a;font-size:.68rem;font-weight:800;">🏫 ${l.cls}${c.class_name ? ': ' + escapeHtml(c.class_name) : ''}</span>`
                : `${locked ? '<i class="fa-solid fa-lock" style="padding:.5rem;color:var(--muted);"></i>' : ''}
                    <button class="card-action-btn ${c.share_code ? 'shared' : ''}" onclick="openShareModal(${c.id})" title="${a.share}" aria-label="${a.share}"><i class="fa-solid fa-share-nodes"></i></button>
                    <button class="card-action-btn" onclick="openEditModal(${c.id},'${c.name.replace(/'/g,"\\'")}')" title="${a.edit}" aria-label="${a.edit}"><i class="fa-solid fa-pen"></i></button>
                    <button class="card-action-btn del" onclick="openDeleteModal(${c.id})" title="${a.del}" aria-label="${a.del}"><i class="fa-solid fa-trash"></i></button>`;
            return `
            <li class="category-item ${locked ? 'locked' : ''}"
                onclick="handleCategoryClick(event, ${c.id}, ${locked})">
                <div class="card-actions">
                    ${actions}
                </div>
                <div class="category-name">${c.name}</div>
                <div class="category-desc">${c.description || ''}</div>
                <div style="font-size:.73rem;color:var(--muted);margin-bottom:1rem;display:flex;align-items:center;gap:5px;">
                    <i class="fa-regular fa-calendar"></i> ${fmt(c.created_at)}
                </div>
                <div class="chart-row">
                    <canvas id="chart-${c.id}" class="mini-chart"></canvas>
                    <div class="chart-legend">
                        <div style="color:#e53e3e">● ${l.dk}: ${(c.level_counts?.dont_know||0)+(c.level_counts?.learning||0)}</div>
                        <div style="color:#38a169">● ${l.kn}: ${c.level_counts?.know||0}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-weight:800;font-size:1.1rem">${c.total_words||0}</div>
                        <small style="color:var(--muted);font-size:.62rem;">${l.words}</small>
                    </div>
                </div>
            </li>`;
        }).join('');
        categories.forEach(c => setTimeout(() => createMiniChart(c), 50));
    }

    function handleCategoryClick(e, id, locked) {
        if (e.target.closest('button')) return;
        if (!locked) window.location.href = `/category/${id}/words`;
    }

    function createMiniChart(c) {
        const el = document.getElementById(`chart-${c.id}`);
        if (!el) return;
        drawWhenVisible(el, () => drawMiniChart(el, c));
    }

    function drawMiniChart(el, c) {
        new Chart(el.getContext('2d'), {
            type: 'doughnut',
            data: { datasets: [{ data: [(c.level_counts?.dont_know||0)+(c.level_counts?.learning||0), c.level_counts?.know||0], backgroundColor:['#e53e3e','#38a169'], borderWidth:0 }] },
            options: { cutout:'70%', plugins:{ legend:{ display:false } } }
        });
    }

    /* ── LANGUAGE ── */
    function setupLanguages() {
        document.querySelectorAll('.lang-btn').forEach(b => b.addEventListener('click', () => {
            currentLang = b.dataset.lang; setLang(currentLang);
            loadUserStats(); displayCategories(allCategories);
        }));
        setLang(currentLang);
    }
    function setLang(lang) {
        localStorage.setItem('preferredLang', lang);
        document.querySelectorAll('.lang-btn').forEach(b => b.classList.toggle('active', b.dataset.lang === lang));
        document.querySelectorAll('[data-en]').forEach(el => { const t = el.getAttribute(`data-${lang}`); if(t) el.textContent = t; });
        // Ikonové tlačidlá nemajú text — názov pre čítačky obrazovky aj bublinu
        // treba prekladať zvlášť, inak ostane natvrdo v jednom jazyku.
        document.querySelectorAll('[data-en-label]').forEach(el => {
            const t = el.getAttribute(`data-${lang}-label`);
            if (t) { el.title = t; el.setAttribute('aria-label', t); }
        });
    }

    /* Celá nástenka jedným requestom. Tri samostatné volania sa navzájom
       spomaľovali (merané: 3 súbežné 2220 ms každé oproti 1076 ms samostatne)
       a každé platilo vlastnú réžiu. Pri zlyhaní sa vykreslí z offline cache;
       staré endpointy ostávajú pre čiastočné obnovenie po zmene sady. */
    async function loadDashboard() {
        try {
            const res = await fetch('/api/dashboard');
            if (!res.ok) throw new Error('HTTP ' + res.status);
            const data = await res.json();
            applyUserData(data.user);
            applyStats(data.stats);
            applyCategories(data.categories);
        } catch (e) {
            console.warn('[WK] Nástenka sa nenačítala, skúšam offline cache:', e);
            applyOfflineUser();
            const stats = localStorage.getItem('wk_cached_stats');
            if (stats) renderStats(JSON.parse(stats));
            document.body.classList.remove('stats-loading');
            const cats = localStorage.getItem('wk_cached_categories');
            displayCategories(cats ? JSON.parse(cats) : []);
        }
    }

    /* ── TOAST ── */
    function showMessage(text, type='success') {
        const toast = document.getElementById('toast');
        const icon  = document.getElementById('toastIcon');
        const span  = document.getElementById('toastText');
        span.textContent = text;
        toast.style.background = type === 'success' ? '#38a169' : 'var(--danger)';
        icon.className = type === 'success' ? 'fa-solid fa-check-circle' : 'fa-solid fa-exclamation-circle';
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 3000);
    }

    /* ── MODALS ── */
    function openEditModal(id, name) {
        const cat = allCategories.find(c => c.id === id);
        document.getElementById('editCategoryId').value  = id;
        document.getElementById('editName').value        = name;
        document.getElementById('editDescription').value = cat?.description || '';
        document.getElementById('editModal').style.display = 'flex';
        setLang(currentLang);
    }
    function openAICreateModal()  { document.getElementById('aiCreateModal').style.display = 'flex'; setLang(currentLang); resetAIModal(); }
    function closeAICreateModal() { document.getElementById('aiCreateModal').style.display = 'none'; resetAIModal(); }
    function openCreateModal() {
        if (!currentUserIsPlus && allCategories.filter(c => !c.from_class).length >= 5) {
            showMessage(currentLang==='sk'?`Máš maximum kategórií (5).`:`You've reached the category limit (5).`, 'error');
            return;
        }
        document.getElementById('createModal').style.display = 'flex'; setLang(currentLang);
    }
    function openDeleteModal(id)  { categoryToDelete = id; document.getElementById('deleteModal').style.display = 'flex'; setLang(currentLang); }
    function closeEditModal()     { document.getElementById('editModal').style.display   = 'none'; }
    function closeCreateModal()   { document.getElementById('createModal').style.display = 'none'; }
    function closeDeleteModal()   { document.getElementById('deleteModal').style.display = 'none'; }

    /* ── SHARE (zdieľanie sady linkom) ── */
    let shareCategoryId = null;

    function openShareModal(id) {
        shareCategoryId = id;
        const cat = allCategories.find(c => c.id === id);
        setShareModalState(cat?.share_code || null);
        document.getElementById('shareModal').style.display = 'flex';
        setLang(currentLang);
    }
    function closeShareModal() { document.getElementById('shareModal').style.display = 'none'; }

    function setShareModalState(code) {
        document.getElementById('shareInactive').style.display = code ? 'none' : '';
        document.getElementById('shareActive').style.display   = code ? '' : 'none';
        if (code) document.getElementById('shareLinkInput').value = `${location.origin}/s/${code}`;
    }

    function updateSharedCategory(code) {
        const cat = allCategories.find(c => c.id === shareCategoryId);
        if (cat) cat.share_code = code;
        localStorage.setItem('wk_cached_categories', JSON.stringify(allCategories));
        setShareModalState(code);
        displayCategories(allCategories);
        setLang(currentLang);
    }

    async function createShareLink() {
        try {
            const res  = await fetch(`/api/v1/categories/${shareCategoryId}/share`, { method: 'POST' });
            const data = await res.json();
            if (!res.ok) throw new Error();
            updateSharedCategory(data.share_code);
        } catch {
            showMessage(currentLang === 'sk' ? 'Vytvorenie odkazu zlyhalo.' : 'Failed to create link.', 'error');
        }
    }

    async function copyShareLink() {
        const input = document.getElementById('shareLinkInput');
        try { await navigator.clipboard.writeText(input.value); }
        catch { input.select(); document.execCommand('copy'); }
        showMessage(currentLang === 'sk' ? 'Odkaz skopírovaný.' : 'Link copied.');
    }

    async function revokeShareLink() {
        try {
            const res = await fetch(`/api/v1/categories/${shareCategoryId}/share`, { method: 'DELETE' });
            if (!res.ok) throw new Error();
            updateSharedCategory(null);
            showMessage(currentLang === 'sk' ? 'Zdieľanie zrušené.' : 'Sharing disabled.');
        } catch {
            showMessage(currentLang === 'sk' ? 'Zrušenie zdieľania zlyhalo.' : 'Failed to stop sharing.', 'error');
        }
    }

    /* ── AI CREATE ── */
    let aiStepTimer = null;

    function resetAIModal() {
        clearTimeout(aiStepTimer);
        document.getElementById('aiCreateForm').style.display = '';
        document.getElementById('aiPreview').style.display = 'none';
        aiPreviewData = null;
        document.getElementById('aiLoading').classList.remove('active');
        ['aiStep1','aiStep2','aiStep3'].forEach(id => {
            const li = document.getElementById(id);
            li.className = '';
            li.querySelector('.step-icon').textContent = '⏳';
        });
    }

    function setAIStep(n) {
        for (let i = 1; i <= 3; i++) {
            const li   = document.getElementById('aiStep' + i);
            const icon = li.querySelector('.step-icon');
            if (i < n)      { li.className = 'done';   icon.textContent = '✅'; }
            else if (i === n) { li.className = 'active'; icon.textContent = '⚙️'; }
            else             { li.className = '';        icon.textContent = '⏳'; }
        }
        const texts = {
            en: ['Analyzing your prompt…', 'Generating vocabulary…', 'Preparing preview…'],
            sk: ['Analyzujem prompt…',      'Generujem slovíčka…',   'Pripravujem náhľad…']
        };
        document.getElementById('aiStepText').textContent = (texts[currentLang] || texts.en)[n - 1];
    }

    /* Preloží AI chybu na hlášku pre používateľa (SK/EN) podľa status kódu. */
    function aiErrorMessage(status, data) {
        const sk = currentLang === 'sk';
        if (status === 401) return sk ? 'Prihlásenie vypršalo. Prihlás sa znova.' : 'Session expired. Please log in again.';
        /* 403 = funkcia len pre PLUS (napr. AI z videa). Server posiela detail po slovensky,
           preto ho anglickému používateľovi nepodsúvame. */
        if (status === 403) {
            return sk ? 'Táto funkcia je dostupná len s PLUS predplatným.'
                      : 'This feature is available with a PLUS subscription only.';
        }
        if (status === 429) {
            if (sk && data && data.detail && data.detail.length < 200) return data.detail;
            return sk ? 'Vyčerpal si limit AI generovaní. Skús to neskôr.' : 'AI generation limit reached. Please try again later.';
        }
        if (status === 502) {
            if (sk && data && data.detail) return data.detail;
            return sk ? 'AI generovanie zlyhalo. Skús to znova.' : 'AI generation failed. Please try again.';
        }
        if (status >= 500) return sk ? 'Chyba servera. Skús to o chvíľu.' : 'Server error. Please try again shortly.';
        if (data && data.detail && typeof data.detail === 'string') return data.detail;
        return sk ? 'Požiadavka zlyhala.' : 'Request failed.';
    }

    function aiCreateCategoryFromDashboard() {
        const prompt = document.getElementById('aiCategoryPrompt').value.trim();
        const lf     = document.getElementById('aiLanguageFrom').value || 'en';
        const lt     = document.getElementById('aiLanguageTo').value   || 'sk';
        const count  = parseInt(document.getElementById('aiWordCount').value || '25', 10);
        if (!prompt) { showMessage(currentLang === 'sk' ? 'Prompt je povinný.' : 'Prompt is required.', 'error'); return; }

        /* Show loading */
        document.getElementById('aiCreateForm').style.display = 'none';
        document.getElementById('aiLoading').classList.add('active');
        setLang(currentLang);

        /* Animate step 1 immediately, step 2 after 1.2 s */
        setAIStep(1);
        aiStepTimer = setTimeout(() => setAIStep(2), 1200);

        /* Generovanie a ukladanie sú dva kroky: server vráti návrh, do účtu ide
           až to, čo používateľ v náhľade nechá. */
        fetch('/api/v1/categories/ai-preview', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, language_from: lf, language_to: lt, count })
        }).then(async res => {
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(aiErrorMessage(res.status, data));

            clearTimeout(aiStepTimer);
            setAIStep(3);
            await new Promise(r => setTimeout(r, 500));
            ['aiStep1','aiStep2','aiStep3'].forEach(id => {
                const li = document.getElementById(id);
                li.className = 'done';
                li.querySelector('.step-icon').textContent = '✅';
            });
            await new Promise(r => setTimeout(r, 300));

            showAIPreview(data, lf, lt);
        }).catch(err => {
            clearTimeout(aiStepTimer);
            resetAIModal();
            showMessage(err.message || 'AI request failed', 'error');
        });
    }

    /* ── NÁHĽAD PRED ULOŽENÍM ──
       Vygenerované slová sa ukážu na odsúhlasenie; do účtu ide až výber. Kým
       používateľ nepotvrdí, v databáze nie je nič. */
    let aiPreviewData = null;

    function showAIPreview(data, languageFrom, languageTo) {
        aiPreviewData = { ...data, language_from: languageFrom, language_to: languageTo };

        document.getElementById('aiLoading').classList.remove('active');
        document.getElementById('aiCreateForm').style.display = 'none';
        document.getElementById('aiPreview').style.display = '';
        document.getElementById('aiPreviewName').value = data.category_name || '';

        document.getElementById('aiPreviewList').innerHTML = (data.words || []).map((w, i) =>
            '<li id="pw' + i + '">' +
            '<input type="checkbox" id="pwc' + i + '" data-i="' + i + '" checked>' +
            '<label for="pwc' + i + '" style="cursor:pointer;">' +
            '<span class="pw">' + escapeHtml(w.original_word) + '</span>' +
            '<span class="pt"> — ' + escapeHtml(w.translation) + '</span>' +
            '</label></li>').join('');

        document.querySelectorAll('#aiPreviewList input[type="checkbox"]').forEach(cb =>
            cb.addEventListener('change', () => {
                document.getElementById('pw' + cb.dataset.i).classList.toggle('off', !cb.checked);
                updatePreviewCount();
            }));

        updatePreviewCount();
    }

    function selectedPreviewWords() {
        return [...document.querySelectorAll('#aiPreviewList input[type="checkbox"]')]
            .filter(cb => cb.checked)
            .map(cb => aiPreviewData.words[Number(cb.dataset.i)]);
    }

    function updatePreviewCount() {
        const chosen = selectedPreviewWords().length;
        const total  = (aiPreviewData && aiPreviewData.words || []).length;
        const sk = currentLang === 'sk';
        document.getElementById('aiPreviewCount').textContent = sk
            ? 'Uloží sa ' + chosen + ' z ' + total
            : 'Saving ' + chosen + ' of ' + total;
        document.getElementById('aiPreviewToggle').textContent = chosen === total
            ? (sk ? 'Odškrtnúť všetko' : 'Uncheck all')
            : (sk ? 'Označiť všetko' : 'Check all');
        const save = document.getElementById('aiPreviewSave');
        save.textContent = (sk ? '💾 Uložiť (' : '💾 Save (') + chosen + ')';
        save.disabled = chosen === 0;
    }

    function toggleAllPreviewWords() {
        const boxes = [...document.querySelectorAll('#aiPreviewList input[type="checkbox"]')];
        const turnOn = boxes.some(cb => !cb.checked);
        boxes.forEach(cb => {
            cb.checked = turnOn;
            document.getElementById('pw' + cb.dataset.i).classList.toggle('off', !turnOn);
        });
        updatePreviewCount();
    }

    async function saveAIPreview() {
        const words = selectedPreviewWords();
        if (!words.length) return;
        const name = document.getElementById('aiPreviewName').value.trim();
        if (!name) {
            showMessage(currentLang === 'sk' ? 'Názov kategórie je povinný.' : 'Category name is required.', 'error');
            return;
        }

        const btn = document.getElementById('aiPreviewSave');
        btn.disabled = true;
        try {
            const res = await fetch('/api/v1/categories/ai-save', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    category_name: name,
                    category_description: aiPreviewData.category_description,
                    language_from: aiPreviewData.language_from,
                    language_to: aiPreviewData.language_to,
                    words: words,
                }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(aiErrorMessage(res.status, data));

            window.lexiTrack('Sada vytvorena', { zdroj: 'ai-text' });
            closeAICreateModal();
            await loadCategories();
            await loadUserStats();
            showMessage(
                currentLang === 'sk' ? 'Vytvorené: ' + data.category_name : 'Created: ' + data.category_name,
                'success'
            );
        } catch (err) {
            btn.disabled = false;
            showMessage(err.message || 'Save failed', 'error');
        }
    }

    /* ── AI CREATE FROM PHOTO ── */
    let aiImageStepTimer = null;

    function openAIImageModal()  {
        if (!currentUserIsPlus && allCategories.filter(c => !c.from_class).length >= 5) {
            showMessage(currentLang==='sk'?`Máš maximum kategórií (5).`:`You've reached the category limit (5).`, 'error');
            return;
        }
        document.getElementById('aiImageModal').style.display = 'flex'; setLang(currentLang); resetAIImageModal();
    }
    function closeAIImageModal() { document.getElementById('aiImageModal').style.display = 'none'; resetAIImageModal(); }

    function resetAIImageModal() {
        clearTimeout(aiImageStepTimer);
        document.getElementById('aiImageForm').style.display = '';
        document.getElementById('aiImageLoading').classList.remove('active');
        const file = document.getElementById('aiImageFile'); if (file) file.value = '';
        const cam = document.getElementById('aiImageCamera'); if (cam) cam.value = '';
        const prev = document.getElementById('aiImagePreview'); if (prev) { prev.style.display = 'none'; prev.src = ''; }
        ['aiImageStep1','aiImageStep2','aiImageStep3'].forEach(id => {
            const li = document.getElementById(id);
            li.className = '';
            li.querySelector('.step-icon').textContent = '⏳';
        });
    }

    function showChosenFileName(inputId, labelId) {
        const file = document.getElementById(inputId).files[0];
        const el = document.getElementById(labelId);
        el.textContent = file ? file.name : (el.getAttribute(`data-${currentLang}`) || 'Žiadny súbor');
    }

    function previewAIImage() {
        showChosenFileName('aiImageFile', 'aiImageFileName');
        const file = document.getElementById('aiImageFile').files[0];
        const prev = document.getElementById('aiImagePreview');
        if (!file) { prev.style.display = 'none'; prev.src = ''; return; }
        prev.src = URL.createObjectURL(file);
        prev.style.display = 'block';
    }

    // Fotka z fotoaparátu (mobil): presype ju do hlavneho inputu, aby zvysok logiky ostal nezmeneny.
    function useCameraPhoto() {
        const cam = document.getElementById('aiImageCamera');
        if (!cam.files.length) return;
        const target = document.getElementById('aiImageFile');
        try {
            const dt = new DataTransfer();
            dt.items.add(cam.files[0]);
            target.files = dt.files;
        } catch (_) { /* DataTransfer nepodporovany – preview aspon cez kamera input nizsie */ }
        previewAIImage();
    }

    function setAIImageStep(n) {
        for (let i = 1; i <= 3; i++) {
            const li   = document.getElementById('aiImageStep' + i);
            const icon = li.querySelector('.step-icon');
            if (i < n)        { li.className = 'done';   icon.textContent = '✅'; }
            else if (i === n) { li.className = 'active'; icon.textContent = '⚙️'; }
            else              { li.className = '';        icon.textContent = '⏳'; }
        }
        const texts = {
            en: ['Uploading image…', 'Recognizing words…', 'Saving to your account…'],
            sk: ['Nahrávam obrázok…', 'Rozpoznávam slovíčka…', 'Ukladám do účtu…']
        };
        document.getElementById('aiImageStepText').textContent = (texts[currentLang] || texts.en)[n - 1];
    }

    function aiCreateCategoryFromImage() {
        const file = document.getElementById('aiImageFile').files[0];
        const lf   = document.getElementById('aiImageLanguageFrom').value || 'en';
        const lt   = document.getElementById('aiImageLanguageTo').value   || 'sk';
        if (!file) { showMessage(currentLang === 'sk' ? 'Vyber obrázok.' : 'Please select an image.', 'error'); return; }
        if (file.size > 5 * 1024 * 1024) { showMessage(currentLang === 'sk' ? 'Obrázok je príliš veľký (max 5 MB).' : 'Image too large (max 5 MB).', 'error'); return; }

        const form = new FormData();
        form.append('image', file);
        form.append('language_from', lf);
        form.append('language_to', lt);

        /* Show loading */
        document.getElementById('aiImageForm').style.display = 'none';
        document.getElementById('aiImageLoading').classList.add('active');
        setLang(currentLang);
        setAIImageStep(1);
        aiImageStepTimer = setTimeout(() => setAIImageStep(2), 1000);

        fetch('/api/v1/categories/ai-create-from-image', {
            method: 'POST', body: form
        }).then(async res => {
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(aiErrorMessage(res.status, data));

            clearTimeout(aiImageStepTimer);
            setAIImageStep(3);
            await new Promise(r => setTimeout(r, 700));

            ['aiImageStep1','aiImageStep2','aiImageStep3'].forEach(id => {
                const li = document.getElementById(id);
                li.className = 'done';
                li.querySelector('.step-icon').textContent = '✅';
            });
            document.getElementById('aiImageStepText').textContent = currentLang === 'sk' ? 'Hotovo! 🎉' : 'Done! 🎉';
            await new Promise(r => setTimeout(r, 700));

            window.lexiTrack('Sada vytvorena', { zdroj: 'ai-foto' });
            closeAIImageModal();
            await loadCategories();
            await loadUserStats();
            showMessage(
                currentLang === 'sk'
                    ? `Vytvorené: ${data.category_name} (${data.inserted_words} slov)`
                    : `Created: ${data.category_name} (${data.inserted_words} words)`,
                'success'
            );
        }).catch(err => {
            clearTimeout(aiImageStepTimer);
            resetAIImageModal();
            showMessage(err.message || 'AI request failed', 'error');
        });
    }

    /* ── AI CREATE FROM YOUTUBE VIDEO (len PLUS) ── */
    let aiVideoStepTimer = null;

    /* Rovnaké tvary odkazu ako prijíma server (app/services/youtube.py) —
       nech používateľ nečaká na request, ktorý aj tak skončí 400. */
    const YT_URL_RE = /^(https?:\/\/)?((www|m|music)\.)?((youtube\.com|youtube-nocookie\.com)\/(watch\?(.*&)?v=|shorts\/|embed\/|live\/|v\/)|youtu\.be\/)[\w-]{11}/i;

    function openAIVideoModal() {
        /* PLUS gating je vynútený na serveri (403); tu len ušetríme zbytočný request. */
        if (!currentUserIsPlus) {
            showMessage(
                currentLang === 'sk'
                    ? 'Generovanie z videa je dostupné len s PLUS predplatným.'
                    : 'Generating from video is available with a PLUS subscription only.',
                'error'
            );
            return;
        }
        document.getElementById('aiVideoModal').style.display = 'flex';
        setLang(currentLang);
        resetAIVideoModal();
    }
    function closeAIVideoModal() { document.getElementById('aiVideoModal').style.display = 'none'; resetAIVideoModal(); }

    function resetAIVideoModal() {
        clearTimeout(aiVideoStepTimer);
        document.getElementById('aiVideoForm').style.display = '';
        document.getElementById('aiVideoLoading').classList.remove('active');
        const url = document.getElementById('aiVideoUrl'); if (url) url.value = '';
        ['aiVideoStep1','aiVideoStep2','aiVideoStep3'].forEach(id => {
            const li = document.getElementById(id);
            li.className = '';
            li.querySelector('.step-icon').textContent = '⏳';
        });
    }

    function setAIVideoStep(n) {
        for (let i = 1; i <= 3; i++) {
            const li   = document.getElementById('aiVideoStep' + i);
            const icon = li.querySelector('.step-icon');
            if (i < n)        { li.className = 'done';   icon.textContent = '✅'; }
            else if (i === n) { li.className = 'active'; icon.textContent = '⚙️'; }
            else              { li.className = '';        icon.textContent = '⏳'; }
        }
        const texts = {
            en: ['Checking the video…', 'AI is watching the video…', 'Saving to your account…'],
            sk: ['Overujem video…', 'AI pozerá video…', 'Ukladám do účtu…']
        };
        document.getElementById('aiVideoStepText').textContent = (texts[currentLang] || texts.en)[n - 1];
    }

    function aiCreateCategoryFromVideo() {
        const url = document.getElementById('aiVideoUrl').value.trim();
        const lf  = document.getElementById('aiVideoLanguageFrom').value || 'en';
        const lt  = document.getElementById('aiVideoLanguageTo').value   || 'sk';

        if (!url) {
            showMessage(currentLang === 'sk' ? 'Vlož odkaz na video.' : 'Please paste a video link.', 'error');
            return;
        }
        if (!YT_URL_RE.test(url)) {
            showMessage(
                currentLang === 'sk' ? 'Toto nevyzerá ako odkaz na YouTube video.'
                                     : "This doesn't look like a YouTube video link.",
                'error'
            );
            return;
        }

        document.getElementById('aiVideoForm').style.display = 'none';
        document.getElementById('aiVideoLoading').classList.add('active');
        setLang(currentLang);
        setAIVideoStep(1);
        /* Overenie cez oEmbed je rýchle, samotné pozeranie videa trvá desiatky sekúnd. */
        aiVideoStepTimer = setTimeout(() => setAIVideoStep(2), 1500);

        fetch('/api/v1/categories/ai-create-from-video', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_url: url, language_from: lf, language_to: lt })
        }).then(async res => {
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(aiErrorMessage(res.status, data));

            clearTimeout(aiVideoStepTimer);
            setAIVideoStep(3);
            await new Promise(r => setTimeout(r, 700));

            ['aiVideoStep1','aiVideoStep2','aiVideoStep3'].forEach(id => {
                const li = document.getElementById(id);
                li.className = 'done';
                li.querySelector('.step-icon').textContent = '✅';
            });
            document.getElementById('aiVideoStepText').textContent = currentLang === 'sk' ? 'Hotovo! 🎉' : 'Done! 🎉';
            await new Promise(r => setTimeout(r, 700));

            window.lexiTrack('Sada vytvorena', { zdroj: 'ai-video' });
            closeAIVideoModal();
            await loadCategories();
            await loadUserStats();
            showMessage(
                currentLang === 'sk'
                    ? `Vytvorené: ${data.category_name} (${data.inserted_words} slov)`
                    : `Created: ${data.category_name} (${data.inserted_words} words)`,
                'success'
            );
        }).catch(err => {
            clearTimeout(aiVideoStepTimer);
            resetAIVideoModal();
            showMessage(err.message || 'AI request failed', 'error');
        });
    }

    /* ── FORM HANDLERS ── */
    document.getElementById('editCategoryForm').addEventListener('submit', async e => {
        e.preventDefault();
        const id  = document.getElementById('editCategoryId').value;
        const res = await fetch(`/api/v1/categories/${id}`, {
            method:'PUT', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({ name:document.getElementById('editName').value, description:document.getElementById('editDescription').value })
        });
        if (res.ok) { closeEditModal(); loadCategories(); showMessage(currentLang==='sk'?'Kategória upravená!':'Category updated!'); }
    });

    document.getElementById('createCategoryForm').addEventListener('submit', async e => {
        e.preventDefault();
        const res = await fetch('/api/v1/categories', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({ name:document.getElementById('createName').value, description:document.getElementById('createDescription').value, user_id:currentUserId })
        });
        if (res.ok) { window.lexiTrack('Sada vytvorena', { zdroj: 'rucne' }); closeCreateModal(); e.target.reset(); loadCategories(); loadUserStats(); showMessage(currentLang==='sk'?'Kategória vytvorená!':'Category created!'); }
    });

    async function confirmDelete() {
        const btn = document.getElementById('confirmDeleteBtn');
        const cancelBtn = document.getElementById('deleteCancelBtn');
        btn.disabled = true;
        cancelBtn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> ' + (currentLang==='sk'?'Mažem…':'Deleting…');
        try {
            const res = await fetch(`/api/v1/categories/${categoryToDelete}`, { method:'DELETE' });
            if (!res.ok) throw new Error();
            closeDeleteModal();
            loadCategories();
            loadUserStats();
            showMessage(currentLang==='sk'?'Kategória vymazaná!':'Category deleted!');
        } catch {
            showMessage(currentLang==='sk'?'Mazanie zlyhalo, skúste znova.':'Delete failed, please try again.','error');
        } finally {
            btn.disabled = false;
            cancelBtn.disabled = false;
            btn.textContent = currentLang==='sk'?'Vymazať':'Delete';
        }
    }

    /* ── NOTIFICATIONS ── */
    async function requestNotificationPermission() {
        if (!('Notification' in window)) { showMessage('Notifikácie nie sú podporované.','error'); return; }
        const p = await Notification.requestPermission();
        if (p !== 'granted') { showMessage('Notifikácie neboli povolené.','error'); return; }
        showMessage('Notifikácie povolené!','success');
        if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
            navigator.serviceWorker.controller.postMessage({
                type:'SHOW_NOTIFICATION', title:'LexiNova',
                body: currentLang==='sk'?'Offline tréning je pripravený.':'Offline training is ready.', tag:'lexinova-demo'
            });
        }
    }

    function logout() { fetch('/api/v1/logout',{method:'POST'}).then(() => window.location.href='/login'); }
