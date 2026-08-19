/* Presunute z classes.html — inline JS sa nedalo cachovat. */
let currentLang = localStorage.getItem('preferredLang') || 'sk';
let classes = [];
let selectedClassId = null;
let ownCategories = [];

/* ── LANG ── */
function setLang(lang) {
    currentLang = lang;
    localStorage.setItem('preferredLang', lang);
    document.querySelectorAll('[data-en],[data-sk]').forEach(el => {
        const t = el.getAttribute('data-' + lang);
        if (!t) return;
        if (el.tagName === 'TITLE') document.title = t;
        else el.textContent = t;
    });
    document.querySelectorAll('[data-en-placeholder]').forEach(el => {
        el.placeholder = el.getAttribute('data-' + lang + '-placeholder') || '';
    });
    document.querySelectorAll('.lang-btn').forEach(b =>
        b.classList.toggle('active', b.getAttribute('data-lang') === lang));
    renderClasses();
    if (selectedClassId) openDetail(selectedClassId, false);
}
document.querySelectorAll('.lang-btn').forEach(b =>
    b.addEventListener('click', () => setLang(b.getAttribute('data-lang'))));

/* ── HELPERS ── */
const t = (sk, en) => currentLang === 'sk' ? sk : en;

function toast(msg, ok = true) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast show' + (ok ? '' : ' error');
    setTimeout(() => el.classList.remove('show'), 3000);
}

function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c =>
        ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

const pad = n => String(n).padStart(2, '0');
function fmtDate(s) {
    if (!s) return '—';
    const d = new Date(s);
    return `${pad(d.getDate())}.${pad(d.getMonth()+1)}.${d.getFullYear()}`;
}
function fmtDateTime(s) {
    if (!s) return '—';
    const d = new Date(s);
    return `${fmtDate(s)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

async function api(url, options = {}) {
    if (options.body) options.headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    const res = await fetch(url, options);
    let data = {};
    try { data = await res.json(); } catch {}
    return { ok: res.ok, status: res.status, data };
}

function detailErr(data, fallback) {
    return (data && typeof data.detail === 'string') ? data.detail : fallback;
}

/* ── CLASSES ── */
async function loadClasses(keepDetail = false) {
    const { ok, data } = await api('/api/v1/classes');
    if (!ok) { toast(t('Nepodarilo sa načítať triedy.', 'Failed to load classes.'), false); return; }
    classes = data;
    renderClasses();
    document.getElementById('emptyNote').style.display = classes.length ? 'none' : '';
    if (keepDetail && selectedClassId && classes.some(c => c.id === selectedClassId)) {
        openDetail(selectedClassId, false);
    } else if (!classes.some(c => c.id === selectedClassId)) {
        selectedClassId = null;
        document.getElementById('classDetail').style.display = 'none';
        autoOpenSingleClass();
    }
}

/* Slovenčina má tri tvary: 1 žiak, 2–4 žiaci, 5+ žiakov. Angličtina dva.
   Bez toho karta hlásila „1 žiakov". */
function studentCount(n) {
    n = Number(n) || 0;
    if (currentLang !== 'sk') return `${n} student${n === 1 ? '' : 's'}`;
    if (n === 1) return '1 žiak';
    if (n >= 2 && n <= 4) return `${n} žiaci`;
    return `${n} žiakov`;
}

/* Keď je trieda jediná, detail otvoríme rovno — používateľ inak nemá dôvod
   tušiť, že karta je klikacia, a funkcia zostane neobjavená. */
function autoOpenSingleClass() {
    if (classes.length === 1 && selectedClassId === null) openDetail(classes[0].id, false);
}

function renderClasses() {
    const list = document.getElementById('classList');
    list.innerHTML = classes.map(c => `
        <div class="class-card ${c.id === selectedClassId ? 'active' : ''}" onclick="openDetail(${c.id})">
            <h3>${escapeHtml(c.name)}</h3>
            <span class="code-chip">${c.join_code}
                <button title="${t('Kopírovať kód', 'Copy code')}" onclick="event.stopPropagation(); copyText('${c.join_code}')"><i class="fa-regular fa-copy"></i></button>
                <button title="${t('Kopírovať odkaz', 'Copy link')}" onclick="event.stopPropagation(); copyText('${c.join_url}')"><i class="fa-solid fa-link"></i></button>
            </span>
            <div class="class-meta">
                <span><i class="fa-solid fa-user-group"></i> ${studentCount(c.member_count)}</span>
                <span><i class="fa-solid fa-folder"></i> ${c.category_count} ${t('sád', 'sets')}</span>
            </div>
            <div class="class-open">
                ${c.id === selectedClassId
                    ? t('Detail je otvorený nižšie', 'Detail open below')
                    : t('Otvoriť žiakov a sady', 'Open students and sets')}
                <i class="fa-solid fa-chevron-right"></i>
            </div>
            <div class="card-tools">
                <button class="btn btn-ghost" onclick="event.stopPropagation(); renameClass(${c.id})"><i class="fa-solid fa-pen"></i> ${t('Premenovať', 'Rename')}</button>
                <button class="btn btn-ghost" onclick="event.stopPropagation(); regenCode(${c.id})"><i class="fa-solid fa-rotate"></i> ${t('Nový kód', 'New code')}</button>
                <button class="btn btn-ghost danger" onclick="event.stopPropagation(); deleteClass(${c.id})" title="${t('Zmazať triedu', 'Delete class')}" aria-label="${t('Zmazať triedu', 'Delete class')}"><i class="fa-solid fa-trash"></i></button>
            </div>
        </div>`).join('');
}

function copyText(text) {
    navigator.clipboard?.writeText(text)
        .then(() => toast(t('Skopírované.', 'Copied.')))
        .catch(() => toast(t('Kopírovanie zlyhalo.', 'Copy failed.'), false));
}

async function createClass() {
    const input = document.getElementById('newClassName');
    const name = input.value.trim();
    if (!name) { toast(t('Zadaj názov triedy.', 'Enter a class name.'), false); return; }
    const { ok, data } = await api('/api/v1/classes', { method: 'POST', body: JSON.stringify({ name }) });
    if (ok) { input.value = ''; toast(t('Trieda založená.', 'Class created.')); loadClasses(); }
    else toast(detailErr(data, t('Založenie zlyhalo.', 'Create failed.')), false);
}

async function renameClass(id) {
    const cls = classes.find(c => c.id === id);
    const name = prompt(t('Nový názov triedy:', 'New class name:'), cls?.name || '');
    if (!name || !name.trim()) return;
    const { ok, data } = await api(`/api/v1/classes/${id}`, { method: 'PUT', body: JSON.stringify({ name: name.trim() }) });
    if (ok) { toast(t('Premenované.', 'Renamed.')); loadClasses(true); }
    else toast(detailErr(data, t('Premenovanie zlyhalo.', 'Rename failed.')), false);
}

async function regenCode(id) {
    if (!confirm(t('Vygenerovať nový kód? Starý kód aj odkaz prestanú platiť.',
                   'Generate a new code? The old code and link will stop working.'))) return;
    const { ok, data } = await api(`/api/v1/classes/${id}/regenerate-code`, { method: 'POST' });
    if (ok) { toast(t('Nový kód: ', 'New code: ') + data.join_code); loadClasses(true); }
    else toast(detailErr(data, t('Zmena kódu zlyhala.', 'Code change failed.')), false);
}

async function deleteClass(id) {
    if (!confirm(t('Zmazať triedu? Žiacke (pseudonymné) účty bez inej triedy sa zmažú tiež.',
                   'Delete the class? Pseudonymous student accounts without another class will be deleted too.'))) return;
    const { ok, data } = await api(`/api/v1/classes/${id}`, { method: 'DELETE' });
    if (ok) { toast(t('Trieda zmazaná.', 'Class deleted.')); if (selectedClassId === id) selectedClassId = null; loadClasses(); }
    else toast(detailErr(data, t('Mazanie zlyhalo.', 'Delete failed.')), false);
}

/* ── DETAIL ── */
async function openDetail(id, scroll = true) {
    selectedClassId = id;
    renderClasses();
    const cls = classes.find(c => c.id === id);
    if (!cls) return;
    document.getElementById('classDetail').style.display = '';
    document.getElementById('detailTitle').textContent = `${cls.name} · ${cls.join_code}`;

    const [members, categories, overview] = await Promise.all([
        api(`/api/v1/classes/${id}/members`),
        api('/api/v1/categories'),
        api(`/api/v1/classes/${id}/overview`),
    ]);

    renderSets(categories.ok ? categories.data : []);
    renderMembers(members.ok ? members.data : []);
    renderOverview(overview);
    if (scroll) document.getElementById('classDetail').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderSets(categories) {
    ownCategories = categories.filter(c => !c.from_class);
    const cls = classes.find(c => c.id === selectedClassId);
    const assignedIds = cls?.category_ids || [];
    const container = document.getElementById('setsList');
    document.getElementById('noSetsNote').style.display = ownCategories.length ? 'none' : '';
    container.innerHTML = ownCategories.map(c => `
        <div class="set-row">
            <input type="checkbox" id="set-${c.id}" data-category="${c.id}" ${assignedIds.includes(c.id) ? 'checked' : ''} onchange="toggleSet(${c.id}, this)">
            <label for="set-${c.id}">${escapeHtml(c.name)} <span class="muted">(${c.total_words} ${t('slov', 'words')})</span></label>
        </div>`).join('');
}

async function toggleSet(categoryId, box) {
    const id = selectedClassId;
    if (box.checked) {
        const { ok, data } = await api(`/api/v1/classes/${id}/categories`, {
            method: 'POST', body: JSON.stringify({ category_id: categoryId }),
        });
        if (ok) toast(t('Sada priradená.', 'Set assigned.'));
        else { box.checked = false; toast(detailErr(data, t('Priradenie zlyhalo.', 'Assign failed.')), false); }
    } else {
        const { ok, data } = await api(`/api/v1/classes/${id}/categories/${categoryId}`, { method: 'DELETE' });
        if (ok) toast(t('Sada odobraná.', 'Set removed.'));
        else { box.checked = true; toast(detailErr(data, t('Odobranie zlyhalo.', 'Unassign failed.')), false); }
    }
    loadClasses(true);
}

function renderMembers(members) {
    const tbody = document.querySelector('#membersTable tbody');
    document.getElementById('noMembersNote').style.display = members.length ? 'none' : '';
    tbody.innerHTML = members.map(m => `
        <tr>
            <td><b>${escapeHtml(m.nickname)}</b></td>
            <td>${m.is_pseudonymous
                ? `<span class="tag pseudo">${t('žiacky', 'student')}</span>`
                : `<span class="tag email">e-mail</span>`}</td>
            <td class="muted">${fmtDate(m.joined_at)}</td>
            <td style="text-align:right; white-space:nowrap;">
                ${m.is_pseudonymous ? `<button class="btn btn-ghost" onclick="resetMemberPassword(${m.id}, '${escapeHtml(m.nickname).replace(/'/g, "\\'")}')"><i class="fa-solid fa-key"></i> ${t('Reset hesla', 'Reset password')}</button>` : ''}
                <button class="btn btn-ghost danger" onclick="removeMember(${m.id}, '${escapeHtml(m.nickname).replace(/'/g, "\\'")}')" title="${t('Odobrať žiaka', 'Remove student')}" aria-label="${t('Odobrať žiaka', 'Remove student')}"><i class="fa-solid fa-user-minus"></i></button>
            </td>
        </tr>`).join('');
}

async function resetMemberPassword(memberId, nickname) {
    const pw = prompt(t(`Nové heslo pre „${nickname}" (min. 8 znakov, veľké aj malé písmeno a číslica):`,
                        `New password for "${nickname}" (min 8 chars, upper & lower case letter and a digit):`));
    if (!pw) return;
    const { ok, data } = await api(`/api/v1/classes/${selectedClassId}/members/${memberId}/reset-password`, {
        method: 'POST', body: JSON.stringify({ new_password: pw }),
    });
    if (ok) toast(t('Heslo zmenené.', 'Password changed.'));
    else toast(detailErr(data, t('Reset zlyhal.', 'Reset failed.')), false);
}

async function removeMember(memberId, nickname) {
    if (!confirm(t(`Odstrániť „${nickname}" z triedy?`, `Remove "${nickname}" from the class?`))) return;
    const { ok, data } = await api(`/api/v1/classes/${selectedClassId}/members/${memberId}`, { method: 'DELETE' });
    if (ok) { toast(t('Žiak odstránený.', 'Student removed.')); openDetail(selectedClassId, false); loadClasses(true); }
    else toast(detailErr(data, t('Odstránenie zlyhalo.', 'Remove failed.')), false);
}

function renderOverview(overview) {
    const tbody = document.querySelector('#overviewTable tbody');
    const note = document.getElementById('overviewNote');
    tbody.innerHTML = '';
    note.style.display = 'none';

    if (!overview.ok) {
        note.style.display = '';
        note.textContent = overview.status === 403
            ? t('Prehľad pokroku vyžaduje aktívne PLUS.', 'The progress overview requires an active PLUS.')
            : t('Prehľad sa nepodarilo načítať.', 'Failed to load the overview.');
        return;
    }

    const data = overview.data;
    const catNames = Object.fromEntries(data.categories.map(c => [c.id, c]));

    if (!data.members.length) {
        note.style.display = '';
        note.textContent = t('Zatiaľ žiadni žiaci.', 'No students yet.');
        return;
    }

    tbody.innerHTML = data.members.map(m => {
        const chips = Object.entries(m.mastery).map(([catId, counts]) => {
            const cat = catNames[catId];
            if (!cat) return '';
            const total = cat.total_words || 0;
            const pct = total ? Math.round((counts.know || 0) / total * 100) : 0;
            return `<span class="mastery-chip">${escapeHtml(cat.name)}: <b>${pct}%</b></span>`;
        }).join('');
        return `
        <tr>
            <td><b>${escapeHtml(m.nickname)}</b></td>
            <td class="muted">${fmtDateTime(m.last_activity)}</td>
            <td>${m.tests_taken}</td>
            <td>${m.success_rate === null || m.success_rate === undefined ? '—' : m.success_rate + '%'}</td>
            <td>${chips || '—'}</td>
        </tr>`;
    }).join('');
}

/* ── INIT ── */
setLang(currentLang);
loadClasses();
