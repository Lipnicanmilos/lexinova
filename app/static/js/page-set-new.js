/* Nová sada: jedno pole, fotka alebo súbor. Server rozhodne, čo sa vložilo, a
   vráti návrh; do účtu ide až to, čo tu používateľ nechá zaškrtnuté. */
const T = {
    sk: {
        hintVideo: 'Vidím video. Vyberiem z neho slová.',
        hintVideoFree: 'Vidím video. Slová z videa sú súčasťou PLUS.',
        hintPairs: n => `Vidím slová s prekladom (${n}). Netreba AI.`,
        hintList: n => `Vidím zoznam (${n}). Doplním preklady.`,
        hintTopic: n => `Vidím tému. Navrhnem ${n} slov.`,
        loadingTopic: 'Vyberám slová…', loadingList: 'Prekladám slová…', loadingVideo: 'Pozerám video, môže to trvať aj minútu…',
        loadingPhoto: 'Čítam fotku…', loadingFile: 'Čítam súbor…', loadingPairs: 'Pripravujem sadu…',
        needText: 'Napíš tému alebo vlož slová.', needName: 'Pomenuj sadu.',
        count: (chosen, total) => `Uloží sa ${chosen} z ${total}`,
        all: 'Označiť všetko', none: 'Odškrtnúť všetko', save: n => `Uložiť sadu (${n})`,
        connection: 'Nepodarilo sa spojiť so serverom. Skús to znova.', failed: 'Nepodarilo sa to. Skús to znova.',
        expired: 'Prihlásenie vypršalo. Prihlás sa znova.', tooBig: 'Fotka je príliš veľká (max 5 MB).',
    },
    en: {
        hintVideo: "I see a video. I'll pick words from it.",
        hintVideoFree: 'I see a video. Words from videos are part of PLUS.',
        hintPairs: n => `I see words with translations (${n}). No AI needed.`,
        hintList: n => `I see a list (${n}). I'll add the translations.`,
        hintTopic: n => `I see a topic. I'll suggest ${n} words.`,
        loadingTopic: 'Picking words…', loadingList: 'Translating words…', loadingVideo: 'Watching the video, this can take a minute…',
        loadingPhoto: 'Reading the photo…', loadingFile: 'Reading the file…', loadingPairs: 'Preparing the set…',
        needText: 'Type a topic or paste some words.', needName: 'Name your set.',
        count: (chosen, total) => `Saving ${chosen} of ${total}`,
        all: 'Check all', none: 'Uncheck all', save: n => `Save the set (${n})`,
        connection: 'Could not reach the server. Please try again.', failed: 'That did not work. Please try again.',
        expired: 'Your session expired. Please log in again.', tooBig: 'The photo is too large (max 5 MB).',
    },
};
function t(key) { return T[currentLang === 'en' ? 'en' : 'sk'][key]; }

const $ = id => document.getElementById(id);
const LANGUAGES_KEY = 'wk_new_set_languages';
const IMAGE_MAX_BYTES = 5 * 1024 * 1024;
const IMAGE_MAX_SIDE = 2000;

let preview = null;      // odpoveď servera + zvolené jazyky
let source = 'text';     // pre meranie: odkiaľ sada vznikla

function showView(id) {
    ['formView', 'loadingView', 'previewView'].forEach(view => { $(view).hidden = view !== id; });
    window.scrollTo(0, 0);
}

function showError(id, text) {
    $(id).textContent = text;
    $(id).hidden = !text;
}

/* ── JAZYKY ──
   Skoro každá sada ide rovnakým smerom, preto sú zbalené a pamätajú si posledný výber. */
function loadLanguages() {
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(LANGUAGES_KEY) || '{}'); } catch (e) {}
    $('languageFrom').value = saved.from || 'en';
    $('languageTo').value = saved.to || 'sk';
    renderLanguages();
}

function renderLanguages() {
    const name = select => select.options[select.selectedIndex]?.textContent || '';
    $('langSummary').textContent = `${name($('languageFrom'))} → ${name($('languageTo'))}`;
    try {
        localStorage.setItem(LANGUAGES_KEY, JSON.stringify({ from: $('languageFrom').value, to: $('languageTo').value }));
    } catch (e) {}
}

/* ── NÁPOVEDA POČAS PÍSANIA ──
   Len naznačí, čo sa stane. Rovnako rozhoduje server (services/set_input.py). */
const YOUTUBE_RE = /^(https?:\/\/)?((www|m|music)\.)?(youtube\.com|youtube-nocookie\.com|youtu\.be)\/\S+$/i;
const STRONG_PAIR_RE = /\t|\s=\s?|=\s|;/;
const DASH_PAIR_RE = /^(.*?[^?!.\s])\s+[-–—]\s+\S/;

function isPair(line, multiline) {
    if (STRONG_PAIR_RE.test(line)) return true;
    return multiline && (DASH_PAIR_RE.test(line) || line.split(',').length === 2);
}

function topicCount(text) {
    for (const match of text.matchAll(/(?<![\d.,])(\d{1,3})(?![\d.,])/g)) {
        const n = Number(match[1]);
        if (n >= 5 && n <= 200) return n;
    }
    return 20;
}

function kindOf(text) {
    const lines = text.split('\n').map(line => line.trim()).filter(Boolean);
    if (!lines.length) return null;
    if (lines.length === 1 && YOUTUBE_RE.test(lines[0])) return { kind: 'video' };
    const pairs = lines.filter(line => isPair(line, lines.length > 1)).length;
    if (pairs >= lines.length * 0.7) return { kind: 'pairs', n: pairs };
    if (lines.length >= 3) return { kind: 'list', n: lines.length };
    if (lines.length === 1) {
        const items = lines[0].split(',').map(item => item.trim()).filter(Boolean);
        if (items.length >= 3 && items.every(item => item.split(/\s+/).length <= 3)) return { kind: 'list', n: items.length };
    }
    return { kind: 'topic', n: Math.min(topicCount(text), IS_PLUS ? 200 : 30) };
}

function renderHint() {
    const text = $('newText').value;
    const found = text.trim().length > 2 ? kindOf(text) : null;
    showError('newError', '');
    if (!found) { $('newHint').textContent = ''; return; }
    $('newHint').textContent = found.kind === 'video'
        ? t(IS_PLUS ? 'hintVideo' : 'hintVideoFree')
        : t(found.kind === 'pairs' ? 'hintPairs' : found.kind === 'list' ? 'hintList' : 'hintTopic')(found.n);
}

/* ── NÁVRH ZO SERVERA ── */
function errorMessage(status, data) {
    if (status === 401) return t('expired');
    // Server píše hlášky po slovensky, anglickému rozhraniu ich nepodsúvame.
    if (typeof data?.detail === 'string' && (currentLang === 'sk' || !data.detail)) return data.detail;
    return t('failed');
}

async function requestPreview(url, options, loadingKey) {
    const from = $('languageFrom').value, to = $('languageTo').value;
    showError('newError', '');
    $('loadingText').textContent = t(loadingKey);
    showView('loadingView');
    let res;
    try {
        res = await fetch(url, { credentials: 'same-origin', ...options });
    } catch (e) {
        showView('formView');
        showError('newError', t('connection'));
        return;
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        showView('formView');
        showError('newError', errorMessage(res.status, data));
        return;
    }
    showPreview({ ...data, language_from: from, language_to: to });
}

function createFromText() {
    const text = $('newText').value.trim();
    if (text.length < 2) { showError('newError', t('needText')); return; }
    const kind = kindOf(text)?.kind || 'topic';
    source = kind === 'pairs' ? 'zoznam' : kind === 'list' ? 'ai-zoznam' : kind === 'video' ? 'ai-video' : 'ai-text';
    requestPreview('/api/v1/categories/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, language_from: $('languageFrom').value, language_to: $('languageTo').value }),
    }, { pairs: 'loadingPairs', list: 'loadingList', video: 'loadingVideo' }[kind] || 'loadingTopic');
}

/* Fotka z telefónu mávala viac než povolených 5 MB a AI toľko detailov nepotrebuje:
   zmenší sa rovno tu. Keď to prehliadač nevie, ide originál a limit stráži server. */
async function shrinkImage(file) {
    if (file.size <= IMAGE_MAX_BYTES / 2) return file;
    try {
        const bitmap = await createImageBitmap(file);
        const scale = Math.min(1, IMAGE_MAX_SIDE / Math.max(bitmap.width, bitmap.height));
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(bitmap.width * scale);
        canvas.height = Math.round(bitmap.height * scale);
        canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
        const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.85));
        return blob ? new File([blob], 'photo.jpg', { type: 'image/jpeg' }) : file;
    } catch (e) {
        return file;
    }
}

async function createFromFile(file) {
    if (!file) return;
    const form = new FormData();
    form.append('language_from', $('languageFrom').value);
    form.append('language_to', $('languageTo').value);
    if (file.type.startsWith('image/')) {
        const image = await shrinkImage(file);
        if (image.size > IMAGE_MAX_BYTES) { showError('newError', t('tooBig')); return; }
        form.append('image', image);
        source = 'ai-foto';
        await requestPreview('/api/v1/categories/preview-image', { method: 'POST', body: form }, 'loadingPhoto');
    } else {
        form.append('file', file);
        source = 'subor';
        await requestPreview('/api/v1/categories/preview-file', { method: 'POST', body: form }, 'loadingFile');
    }
}

/* ── NÁHĽAD ── */
function showPreview(data) {
    preview = data;
    $('previewName').value = data.category_name || '';
    showError('previewError', '');
    // Slová sú cudzí text — skladajú sa cez DOM, nie cez innerHTML.
    $('previewList').replaceChildren(...data.words.map((word, i) => {
        const li = document.createElement('li');
        const label = document.createElement('label');
        const box = document.createElement('input');
        box.type = 'checkbox';
        box.checked = true;
        box.dataset.i = i;
        box.addEventListener('change', () => {
            li.classList.toggle('off', !box.checked);
            updatePreviewCount();
        });
        const original = document.createElement('b');
        original.textContent = word.original_word;
        const translation = document.createElement('span');
        translation.textContent = word.translation;
        label.append(box, original, translation);
        li.append(label);
        return li;
    }));
    updatePreviewCount();
    showView('previewView');
    if (!data.category_name) $('previewName').focus();
}

function previewBoxes() { return [...document.querySelectorAll('#previewList input[type="checkbox"]')]; }

function updatePreviewCount() {
    const boxes = previewBoxes();
    const chosen = boxes.filter(box => box.checked).length;
    $('previewCount').textContent = t('count')(chosen, boxes.length);
    $('previewToggle').textContent = t(chosen === boxes.length ? 'none' : 'all');
    $('saveBtn').textContent = t('save')(chosen);
    $('saveBtn').disabled = chosen === 0;
}

function togglePreview() {
    const boxes = previewBoxes();
    const turnOn = boxes.some(box => !box.checked);
    boxes.forEach(box => {
        box.checked = turnOn;
        box.closest('li').classList.toggle('off', !turnOn);
    });
    updatePreviewCount();
}

async function savePreview() {
    const words = previewBoxes().filter(box => box.checked).map(box => preview.words[Number(box.dataset.i)]);
    const name = $('previewName').value.trim();
    if (!words.length) return;
    if (!name) { showError('previewError', t('needName')); $('previewName').focus(); return; }

    $('saveBtn').disabled = true;
    showError('previewError', '');
    try {
        const res = await fetch('/api/v1/categories/ai-save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                category_name: name,
                category_description: preview.category_description,
                language_from: preview.language_from,
                language_to: preview.language_to,
                words,
            }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(errorMessage(res.status, data));
        window.lexiTrack?.('Sada vytvorena', { zdroj: source });
        window.location.href = `/category/${data.category_id}/words`;
    } catch (e) {
        $('saveBtn').disabled = false;
        showError('previewError', e.message === 'Failed to fetch' ? t('connection') : e.message);
    }
}

/* ── PRÁZDNA SADA ── */
async function createEmpty(e) {
    e.preventDefault();
    const name = $('emptyName').value.trim();
    if (!name) return;
    try {
        const res = await fetch('/api/v1/categories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description: '' }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) { showError('newError', errorMessage(res.status, data)); return; }
        window.lexiTrack?.('Sada vytvorena', { zdroj: 'rucne' });
        window.location.href = `/category/${data.id}/words`;
    } catch (err) {
        showError('newError', t('connection'));
    }
}

/* ── OVLÁDANIE ── */
$('newText').addEventListener('input', renderHint);
$('createBtn').addEventListener('click', createFromText);
$('languageFrom').addEventListener('change', renderLanguages);
$('languageTo').addEventListener('change', renderLanguages);
['cameraInput', 'fileInput'].forEach(id => $(id).addEventListener('change', async e => {
    await createFromFile(e.target.files[0]);
    e.target.value = '';   // ten istý súbor sa dá vybrať znova
}));
$('previewToggle').addEventListener('click', togglePreview);
$('saveBtn').addEventListener('click', savePreview);
$('discardBtn').addEventListener('click', () => showView('formView'));
$('emptyForm').addEventListener('submit', createEmpty);

setLang(currentLang);
loadLanguages();
