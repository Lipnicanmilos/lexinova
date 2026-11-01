/* Listovanie: slová, ktoré človek nevie, na posúvanie ako na Instagrame.
   Posunutie nič nezapisuje. Keby rátalo ako „Neviem", každé prelistovanie by slovo
   vrátilo na začiatok opakovania. Zapíše sa len „Viem" (dvojité klepnutie alebo
   tlačidlo), a to cez ten istý `/test/submit` ako učenie. */
const _q = new URLSearchParams(location.search);
const CATEGORY = parseInt(_q.get('category') || '', 10) || null;
const BACK_URL = CATEGORY ? `/category/${CATEGORY}/words` : '/dashboard';
const LEARN_URL = CATEGORY ? `/ucenie?category=${CATEGORY}` : '/ucenie';
const DOUBLE_TAP_MS = 320;
const LONG_WORD = 24;
const LONGER_WORD = 60;

const T = {
    sk: {
        hint: 'Klepni a uvidíš preklad. Dvojité klepnutie znamená Viem.',
        speak: 'Prehrať slovo', know: 'Viem',
        endTitle: 'Prelistované',
        endText: (total, known) => known ? `${total} ${wordsLabel(total)}, z toho vieš ${known}.` : `${total} ${wordsLabel(total)}.`,
        learn: 'Učiť sa', again: 'Ešte raz',
        backSet: 'Späť na sadu', backToday: 'Späť na Dnes',
        emptyTitle: 'Nič tu nečaká', emptyText: 'Všetky slová vieš. Nové prídu, keď budú na rade.',
        errorTitle: 'Slová sa nenačítali', errorText: 'Listovanie potrebuje pripojenie. Skús to o chvíľu znova.',
    },
    en: {
        hint: 'Tap to see the translation. Double-tap means you know it.',
        speak: 'Play the word', know: 'Know',
        endTitle: 'All done',
        endText: (total, known) => known ? `${total} ${wordsLabel(total)}, you know ${known} of them.` : `${total} ${wordsLabel(total)}.`,
        learn: 'Learn', again: 'Once more',
        backSet: 'Back to the set', backToday: 'Back to Today',
        emptyTitle: 'Nothing waiting here', emptyText: 'You know all the words. New ones will come when they are due.',
        errorTitle: 'The words did not load', errorText: 'Browsing needs a connection. Please try again shortly.',
    },
};
function t(key) { return T[currentLang === 'en' ? 'en' : 'sk'][key]; }

const $ = id => document.getElementById(id);
const feed = $('feed');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

let total = 0;
let answers = [];        // { word_id, is_correct }
let pendingFrom = 0;     // prvá ešte neodoslaná odpoveď (poistka proti dvojitému zápisu)
let lastTap = { card: null, time: 0 };

function wordCards() { return [...feed.querySelectorAll('.feed-card:not(.feed-end)')]; }
function currentCard() { return feed.children[Math.round(feed.scrollTop / feed.clientHeight)] || null; }

function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

/* ── KARTY ── */
function buildCard(item, i) {
    const card = el('section', `feed-card tone-${i % 3}`);
    const panel = el('div', 'feed-panel');
    const face = el('button', 'feed-face');
    face.type = 'button';

    const length = item.original_word.length;
    const word = el('div', `feed-word${length > LONGER_WORD ? ' longer' : length > LONG_WORD ? ' long' : ''}`, item.original_word);
    word.lang = item.language_from || 'en';
    face.append(word);
    if (item.example_sentence) face.append(el('div', 'feed-sentence', item.example_sentence));

    const back = el('div', 'feed-back');
    back.hidden = true;
    back.append(el('div', 'feed-translation', item.translation));
    if (item.example_translation) back.append(el('div', 'feed-sentence-tr', item.example_translation));
    face.append(back);
    face.addEventListener('click', () => tapCard(card));
    panel.append(face);

    if (i === 0) panel.append(el('p', 'feed-hint', t('hint')));

    const rail = el('div', 'feed-rail');
    if (LexiSpeech.available) {
        const speak = iconButton('feed-action', 'fa-volume-high', t('speak'));
        speak.addEventListener('click', () => LexiSpeech.speak(item.original_word, LexiSpeech.toLocale(item.language_from, 'en-US')));
        rail.append(speak);
    }
    const know = iconButton('feed-action know', 'fa-check', t('know'));
    know.addEventListener('click', () => markKnown(card));
    rail.append(know);
    panel.append(rail);

    card.dataset.id = item.id;
    card.append(panel);
    return card;
}

function iconButton(className, icon, label) {
    const btn = el('button', className);
    btn.type = 'button';
    btn.title = label;
    btn.setAttribute('aria-label', label);
    const glyph = el('i', `fa-solid ${icon}`);
    btn.append(glyph);
    return btn;
}

function buildEnd() {
    const card = el('section', 'feed-card feed-end');
    const panel = el('div', 'feed-panel');
    panel.append(el('h2', '', t('endTitle')), el('p', 'feed-end-text'));

    const learn = el('a', 'app-btn primary lg block', t('learn'));
    learn.href = LEARN_URL;
    learn.addEventListener('click', e => leave(e, LEARN_URL));
    const again = el('button', 'app-btn outline lg block', t('again'));
    again.type = 'button';
    again.addEventListener('click', async () => { await submitBeforeLeaving(); location.reload(); });

    panel.append(learn, again);
    card.append(panel);
    return card;
}

function updateEnd() {
    const text = feed.querySelector('.feed-end-text');
    if (text) text.textContent = t('endText')(total, answers.length);
}

/* ── NAČÍTANIE ── */
async function loadFeed() {
    const params = CATEGORY ? `?category_id=${CATEGORY}` : '';
    let items;
    try {
        const res = await fetch(`/api/v1/learn/feed${params}`, { credentials: 'same-origin' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        items = await res.json();
    } catch (e) {
        console.warn('[WK] Listovanie sa nenačítalo:', e);
        showEmpty(t('errorTitle'), t('errorText'));
        return;
    }
    if (!items.length) {
        showEmpty(t('emptyTitle'), t('emptyText'));
        return;
    }
    total = items.length;
    feed.replaceChildren(...items.map(buildCard), buildEnd());
    updateEnd();
    updateCount();
}

function showEmpty(title, text) {
    $('emptyTitle').textContent = title;
    $('emptyText').textContent = text;
    $('emptyBack').textContent = CATEGORY ? t('backSet') : t('backToday');
    $('emptyBack').href = BACK_URL;
    $('loadingView').hidden = true;
    $('feedCount').hidden = true;
    $('emptyView').hidden = false;
}

function updateCount() {
    const cards = wordCards();
    const position = cards.indexOf(currentCard());
    $('feedCount').hidden = position < 0;
    if (position >= 0) $('feedCount').textContent = `${position + 1} / ${cards.length}`;
}

/* ── KLEPNUTIA ──
   Prvé klepnutie preklad hneď ukáže, nečaká, či príde druhé. Dvojité preto preklad
   na chvíľu odhalí, ale slovo aj tak odchádza. */
function tapCard(card) {
    const now = performance.now();
    if (lastTap.card === card && now - lastTap.time < DOUBLE_TAP_MS) {
        lastTap = { card: null, time: 0 };
        markKnown(card);
        return;
    }
    lastTap = { card, time: now };
    toggleTranslation(card);
}

function toggleTranslation(card) {
    const back = card.querySelector('.feed-back');
    back.hidden = !back.hidden;
    card.querySelector('.feed-hint')?.remove();
}

function markKnown(card) {
    if (card.dataset.known) return;
    card.dataset.known = '1';
    answers.push({ word_id: Number(card.dataset.id), is_correct: true });
    updateEnd();

    const pop = el('div', 'feed-pop');
    pop.append(el('i', 'fa-solid fa-check'));
    card.querySelector('.feed-panel').append(pop);

    setTimeout(() => {
        feed.scrollTo({ top: card.nextElementSibling.offsetTop, behavior: reducedMotion ? 'auto' : 'smooth' });
        setTimeout(() => removeCard(card), reducedMotion ? 0 : 500);
    }, 480);
}

/* Karta nad obrazovkou by po zmazaní posunula všetko o jej výšku nahor. */
function removeCard(card) {
    const height = card.offsetHeight;
    const passed = feed.scrollTop >= card.offsetTop + height / 2;
    card.remove();
    if (passed) feed.scrollTop -= height;
    updateCount();
}

/* ── ZÁPIS ── */
async function submitResults() {
    if (answers.length === pendingFrom) return;
    const payload = answers.slice(pendingFrom);
    pendingFrom = answers.length;
    try {
        if (!navigator.onLine) throw new Error('offline');
        const res = await fetch('/api/v1/words/test/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            keepalive: true,
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
    } catch (e) {
        // Offline / výpadok → do fronty; odošle sa automaticky po pripojení.
        console.warn('[WK] Odpovede idú do fronty:', e);
        if (window.WKOfflineCache) WKOfflineCache.queueTestResults(payload);
    }
}

function submitBeforeLeaving() {
    return Promise.race([submitResults(), new Promise(resolve => setTimeout(resolve, 3000))]);
}

async function leave(e, url) {
    e.preventDefault();
    await submitBeforeLeaving();
    window.location.href = url;
}

/* Na telefóne sa appka často len prepne do pozadia a `pagehide` nepríde, preto
   aj `visibilitychange`. Beacon prežije zánik stránky. */
function flushWithBeacon() {
    if (answers.length === pendingFrom) return;
    const payload = answers.slice(pendingFrom);
    pendingFrom = answers.length;
    try {
        navigator.sendBeacon('/api/v1/words/test/submit',
            new Blob([JSON.stringify(payload)], { type: 'application/json' }));
    } catch (err) { /* stránka končí — viac sa spraviť nedá */ }
}
window.addEventListener('pagehide', flushWithBeacon);
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flushWithBeacon();
});

/* ── OVLÁDANIE ── */
$('closeBtn').href = BACK_URL;
$('closeBtn').addEventListener('click', e => leave(e, BACK_URL));
feed.addEventListener('scroll', updateCount, { passive: true });

document.addEventListener('keydown', e => {
    if (e.ctrlKey || e.metaKey || e.altKey || !total) return;
    const card = currentCard();
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        feed.scrollBy({ top: (e.key === 'ArrowDown' ? 1 : -1) * feed.clientHeight, behavior: reducedMotion ? 'auto' : 'smooth' });
    } else if (card && !card.classList.contains('feed-end')) {
        if (e.key === 'v') markKnown(card);
        // Enter na zaostrenom tlačidle rieši prehliadač, inak by sa stal dvakrát.
        else if ((e.key === ' ' || e.key === 'Enter') && !e.target.closest('a, button')) {
            e.preventDefault();
            toggleTranslation(card);
        }
    }
});

setLang(currentLang);
loadFeed();
