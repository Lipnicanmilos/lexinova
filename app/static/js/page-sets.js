/* Obrazovka Sady: zoznam sád, úprava a zdieľanie. Nová sada je na /sady/nova.
   Spoločné veci sú v app-core.js. */
let categoryToDelete = null;
let categoriesFromServer = false;

/* ── INIT ── */
window.addEventListener('pageshow', async () => {
    setLang(currentLang);
    await loadCategories();
    setTimeout(() => document.body.classList.add('theme-ready'), 100);
});

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
    function openDeleteModal(id)  { categoryToDelete = id; document.getElementById('deleteModal').style.display = 'flex'; setLang(currentLang); }
    function closeEditModal()     { document.getElementById('editModal').style.display   = 'none'; }
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
