/* Obrazovka Sady: zoznam sád, nová sada (text, fotka, video, ručne), zdieľanie.
   Spoločné veci sú v app-core.js. */
let categoryToDelete = null;
let categoriesFromServer = false;

/* ── INIT ── */
window.addEventListener('pageshow', async () => {
    setLang(currentLang);
    await loadCategories();
    openRequestedModal();
    setTimeout(() => document.body.classList.add('theme-ready'), 100);
});

/* `/sady?nova=1` otvorí výber spôsobu rovno (prázdny účet ho má aj bez toho). */
function openRequestedModal() {
    if (new URLSearchParams(location.search).get('nova') !== '1') return;
    history.replaceState({}, '', '/sady');
    if (allCategories.length) openNewSetModal();
}

async function loadCategories() {
    const { fromServer } = await fetchDashboard();
    categoriesFromServer = fromServer;
    displayCategories(allCategories);
}

/* ── ZOZNAM SÁD ──
   Karta má jednu akciu: otvoriť sadu. Zdieľanie, úprava a mazanie sú pod „⋯",
   tri ikonky na každej karte zoznam zbytočne zahlcovali. */
function setMeta(c, locked) {
    const sk = currentLang === 'sk';
    const total = c.total_words || 0;
    const known = c.level_counts?.know || 0;
    if (locked) return sk ? `${total} ${wordsLabel(total)} · odomkne PLUS` : `${total} ${wordsLabel(total)} · unlocks with PLUS`;
    if (!total) return sk ? 'Zatiaľ bez slov' : 'No words yet';
    return `${total} ${wordsLabel(total)} · ${known} ${sk ? 'vieš' : 'known'}`;
}

function setCardMenu(c) {
    const l = currentLang === 'sk'
        ? { more: 'Možnosti sady', share: 'Zdieľať', edit: 'Upraviť', del: 'Zmazať' }
        : { more: 'Set options', share: 'Share', edit: 'Edit', del: 'Delete' };
    return `
        <button type="button" class="card-menu-btn" onclick="toggleCardMenu(event, ${c.id})"
                title="${l.more}" aria-label="${l.more}" aria-expanded="false" aria-controls="cardMenu${c.id}">⋯</button>
        <div class="card-menu" id="cardMenu${c.id}" hidden>
            <button type="button" onclick="openShareModal(${c.id})"><i class="fa-solid fa-share-nodes"></i> ${l.share}</button>
            <button type="button" onclick="openEditModal(${c.id})"><i class="fa-solid fa-pen"></i> ${l.edit}</button>
            <button type="button" class="danger" onclick="openDeleteModal(${c.id})"><i class="fa-solid fa-trash"></i> ${l.del}</button>
        </div>`;
}

function displayCategories(categories) {
    const list = document.getElementById('categoriesList');
    const classLabel = currentLang === 'sk' ? 'Trieda' : 'Class';

    categories.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
    const newestOwnId = newestOwnCategoryId(categories);

    document.body.classList.toggle('no-sets', categoriesFromServer && !categories.length);
    document.getElementById('firstSetVideo').style.display = currentUserIsPlus ? '' : 'none';

    list.innerHTML = categories.map(c => {
        const locked = isCategoryLocked(c, newestOwnId);
        const total = c.total_words || 0;
        const known = c.level_counts?.know || 0;
        const name = escapeHtml(c.name);
        const percent = total ? Math.round(known / total * 100) : 0;
        return `
        <li class="set-card ${locked ? 'locked' : ''}" onclick="handleCategoryClick(event, ${c.id}, ${locked})">
            <div class="set-card-top">
                <div class="set-card-name">${locked ? name : `<a href="/category/${c.id}/words">${name}</a>`}</div>
                ${c.from_class ? '' : setCardMenu(c)}
            </div>
            <div class="set-card-meta">
                ${c.from_class ? `<span class="class-chip"><i class="fa-solid fa-chalkboard-user"></i> ${classLabel}${c.class_name ? ': ' + escapeHtml(c.class_name) : ''}</span>` : ''}
                ${locked ? '<i class="fa-solid fa-lock"></i>' : ''}
                <span>${setMeta(c, locked)}</span>
            </div>
            <div class="set-card-bar"><span style="width:${percent}%"></span></div>
        </li>`;
    }).join('');
}

function closeCardMenus() {
    document.querySelectorAll('.card-menu:not([hidden])').forEach(menu => {
        menu.hidden = true;
        menu.previousElementSibling.setAttribute('aria-expanded', 'false');
    });
}

function toggleCardMenu(e, id) {
    e.stopPropagation();
    const menu = document.getElementById(`cardMenu${id}`);
    const open = menu.hidden;
    closeCardMenus();
    menu.hidden = !open;
    e.currentTarget.setAttribute('aria-expanded', String(open));
}
document.addEventListener('click', closeCardMenus);

function handleCategoryClick(e, id, locked) {
    if (e.target.closest('button, a')) return;
    if (!locked) { window.location.href = `/category/${id}/words`; return; }
    // Zamknutá karta predtým na klik nereagovala vôbec — nebolo jasné,
    // či je to chyba alebo zámer.
    showMessage(currentLang === 'sk'
        ? 'Free účet má odomknutú len najnovšiu sadu. Ostatné odomkne PLUS.'
        : 'The free plan keeps only your newest set unlocked. PLUS unlocks the rest.', 'error');
}

    /* ── MODALS ── */
    /* Názov sa berie z dát, nie z atribútu onclick — tam by ho bolo treba
       escapovať pre HTML aj pre JS naraz a úvodzovka v názve to rozbíjala. */
    function openEditModal(id) {
        const cat = allCategories.find(c => c.id === id);
        document.getElementById('editCategoryId').value  = id;
        document.getElementById('editName').value        = cat?.name || '';
        document.getElementById('editDescription').value = cat?.description || '';
        document.getElementById('editModal').style.display = 'flex';
        setLang(currentLang);
    }
    /* Výber spôsobu vytvorenia. Každá z volieb si ho zavrie sama, takže ich
       možno volať aj priamo (E2E skript, odkazy). */
    function openNewSetModal()  { document.getElementById('newSetModal').style.display = 'flex'; setLang(currentLang); }
    function closeNewSetModal() { document.getElementById('newSetModal').style.display = 'none'; }

    function openAICreateModal()  { closeNewSetModal(); document.getElementById('aiCreateModal').style.display = 'flex'; setLang(currentLang); resetAIModal(); }
    function closeAICreateModal() { document.getElementById('aiCreateModal').style.display = 'none'; resetAIModal(); }
    function openCreateModal() {
        closeNewSetModal();
        if (!currentUserIsPlus && allCategories.filter(c => !c.from_class).length >= 5) {
            showMessage(currentLang==='sk'?`Máš maximum sád (5).`:`You've reached the set limit (5).`, 'error');
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
        save.textContent = (sk ? 'Uložiť (' : 'Save (') + chosen + ')';
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
            showMessage(currentLang === 'sk' ? 'Názov sady je povinný.' : 'Set name is required.', 'error');
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
        closeNewSetModal();
        if (!currentUserIsPlus && allCategories.filter(c => !c.from_class).length >= 5) {
            showMessage(currentLang==='sk'?`Máš maximum sád (5).`:`You've reached the set limit (5).`, 'error');
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
        closeNewSetModal();
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
        if (res.ok) { closeEditModal(); loadCategories(); showMessage(currentLang==='sk'?'Sada upravená!':'Set updated!'); }
    });

    document.getElementById('createCategoryForm').addEventListener('submit', async e => {
        e.preventDefault();
        const res = await fetch('/api/v1/categories', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({ name:document.getElementById('createName').value, description:document.getElementById('createDescription').value, user_id:currentUserId })
        });
        if (res.ok) { window.lexiTrack('Sada vytvorena', { zdroj: 'rucne' }); closeCreateModal(); e.target.reset(); loadCategories(); showMessage(currentLang==='sk'?'Sada vytvorená!':'Set created!'); }
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
           
            showMessage(currentLang==='sk'?'Sada vymazaná!':'Set deleted!');
        } catch {
            showMessage(currentLang==='sk'?'Mazanie zlyhalo, skúste znova.':'Delete failed, please try again.','error');
        } finally {
            btn.disabled = false;
            cancelBtn.disabled = false;
            btn.textContent = currentLang==='sk'?'Vymazať':'Delete';
        }
    }
