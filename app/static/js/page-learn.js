/* Jedno učenie: server pošle dávku úloh, stránka ich prejde a odpovede zapíše
   cez ten istý `/test/submit` ako test — priehradky, séria aj graf sa tak rátajú
   na jednom mieste. Spoločné veci sú v app-core.js. */
const _q = new URLSearchParams(location.search);
const CATEGORY = parseInt(_q.get('category') || '', 10) || null;
const EXTRA = _q.get('extra') === '1';
/* Späť vedie tam, odkiaľ učenie začalo. */
const BACK_URL = CATEGORY ? `/category/${CATEGORY}/words` : '/dashboard';

const T = {
    sk: {
        askChoice: 'Čo to znamená?', askCloze: 'Doplň do vety', askListen: 'Čo počuješ?', askRecall: 'Ako sa to povie?',
        score: (right, total) => `${right} z ${total} správne`,
        backSet: 'Späť na sadu', backToday: 'Späť na Dnes',
        emptyTitle: 'Na dnes hotovo', emptyText: 'Ďalšie slová prídu zajtra.',
        emptySetTitle: 'Zatiaľ tu nie je čo sa učiť', emptySetText: 'Pridaj do sady prvé slová.',
        errorTitle: 'Slová sa nenačítali', errorText: 'Učenie potrebuje pripojenie. Skús to o chvíľu znova.',
    },
    en: {
        askChoice: 'What does it mean?', askCloze: 'Fill in the sentence', askListen: 'What do you hear?', askRecall: 'How do you say it?',
        score: (right, total) => `${right} of ${total} correct`,
        backSet: 'Back to the set', backToday: 'Back to Today',
        emptyTitle: 'Done for today', emptyText: 'More words will come tomorrow.',
        emptySetTitle: 'Nothing to learn here yet', emptySetText: 'Add the first words to this set.',
        errorTitle: 'The words did not load', errorText: 'Learning needs a connection. Please try again shortly.',
    },
};
function t(key) { return T[currentLang === 'en' ? 'en' : 'sk'][key]; }

let items = [];
let idx = 0;
let answers = [];        // { word_id, is_correct }
let pendingFrom = 0;     // prvá ešte neodoslaná odpoveď (poistka proti dvojitému zápisu)
let rightCount = 0;
let wrongItems = [];
let answered = false;    // na aktuálnu otázku už padla odpoveď
let revealed = false;    // kartička je otočená

const $ = id => document.getElementById(id);

function showView(id) {
    ['loadingView', 'cardView', 'questionView', 'doneView', 'emptyView'].forEach(view => { $(view).hidden = view !== id; });
    $('learnTop').hidden = id === 'doneView' || id === 'emptyView';
}

function itemLocale(item) { return LexiSpeech.toLocale(item.language_from, 'en-US'); }
function speak(text, item) { if (LexiSpeech.available) LexiSpeech.speak(text, itemLocale(item)); }

/* ── NAČÍTANIE ── */
async function loadSession() {
    const params = new URLSearchParams();
    if (CATEGORY) params.set('category_id', CATEGORY);
    if (EXTRA) params.set('extra', 'true');
    try {
        const res = await fetch(`/api/v1/learn/session?${params}`, { credentials: 'same-origin' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        items = await res.json();
    } catch (e) {
        console.warn('[WK] Učenie sa nenačítalo:', e);
        showEmpty(t('errorTitle'), t('errorText'));
        return;
    }
    if (!items.length) {
        showEmpty(CATEGORY ? t('emptySetTitle') : t('emptyTitle'), CATEGORY ? t('emptySetText') : t('emptyText'));
        return;
    }
    showItem();
}

function showEmpty(title, text) {
    $('emptyTitle').textContent = title;
    $('emptyText').textContent = text;
    $('emptyBack').textContent = CATEGORY ? t('backSet') : t('backToday');
    $('emptyBack').href = BACK_URL;
    showView('emptyView');
}

function updateProgress() {
    $('learnFill').style.width = `${Math.round(idx / items.length * 100)}%`;
    $('learnCount').textContent = `${idx + 1} / ${items.length}`;
}

function showItem() {
    answered = false;
    revealed = false;
    updateProgress();
    if (items[idx].exercise === 'card') showCard(items[idx]);
    else showQuestion(items[idx]);
}

/* ── KARTIČKA ── */
function showCard(item) {
    $('cardWord').textContent = item.original_word;
    $('cardTranslation').textContent = item.translation;
    $('cardExample').textContent = item.example_sentence || '';
    $('cardExampleTr').textContent = item.example_translation || '';
    $('cardBack').hidden = true;
    $('cardHint').hidden = false;
    $('cardAnswers').hidden = true;
    $('cardSpeak').hidden = !LexiSpeech.available;
    $('flashcard').classList.remove('flipped');
    showView('cardView');
    speak(item.original_word, item);
}

function revealCard() {
    if (revealed || items[idx]?.exercise !== 'card') return;
    revealed = true;
    $('cardBack').hidden = false;
    $('cardHint').hidden = true;
    $('cardAnswers').hidden = false;
    $('flashcard').classList.add('flipped');
}

/* ── OTÁZKA ──
   Počúvanie bez hlasu v prehliadači nejde; namiesto neho sa ukáže preklad a
   hľadá sa to isté slovo medzi tými istými možnosťami. */
function showQuestion(item) {
    const listen = item.exercise === 'listen' && LexiSpeech.available;
    const recall = item.exercise === 'listen' && !LexiSpeech.available;
    const cloze = item.exercise === 'cloze';

    $('questionAsk').textContent = t(cloze ? 'askCloze' : listen ? 'askListen' : recall ? 'askRecall' : 'askChoice');
    $('questionPlay').hidden = !listen;
    $('questionPrompt').hidden = listen;
    $('questionFeedback').hidden = true;
    $('btnNext').hidden = true;

    const main = $('promptMain');
    if (cloze) {
        const gap = document.createElement('span');
        gap.className = 'learn-gap';
        gap.id = 'clozeGap';
        main.replaceChildren(document.createTextNode(item.sentence_before || ''), gap,
                             document.createTextNode(item.sentence_after || ''));
    } else {
        main.textContent = recall ? item.translation : item.original_word;
    }
    $('promptSub').textContent = cloze ? (item.sentence_translation || '') : '';

    $('questionOptions').replaceChildren(...item.options.map((option, i) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'learn-option';
        btn.textContent = option;
        btn.addEventListener('click', () => chooseOption(i));
        return btn;
    }));
    showView('questionView');
    if (listen) speak(item.original_word, item);
}

function chooseOption(i) {
    const item = items[idx];
    if (answered || !item || i < 0 || i >= item.options.length) return;
    answered = true;
    const correct = item.options[i] === item.answer;

    document.querySelectorAll('#questionOptions .learn-option').forEach((btn, n) => {
        btn.disabled = true;
        if (item.options[n] === item.answer) btn.classList.add('right');
        else if (n === i) btn.classList.add('wrong');
    });
    if (item.exercise === 'cloze') {
        const gap = $('clozeGap');
        gap.textContent = item.sentence_hidden;
        gap.classList.add('filled');
        speak(item.sentence_before + item.sentence_hidden + item.sentence_after, item);
    }
    // Po odpovedi vždy obe strany slova: to je chvíľa, keď si ho človek zapamätá.
    const feedback = $('questionFeedback');
    feedback.textContent = `${item.original_word} — ${item.translation}`;
    feedback.hidden = false;
    recordAnswer(item, correct);
    $('btnNext').hidden = false;
    $('btnNext').focus();
}

/* ── ODPOVEDE ── */
function recordAnswer(item, correct) {
    answers.push({ word_id: item.id, is_correct: correct });
    if (correct) rightCount++;
    else wrongItems.push(item);
}

function nextItem() {
    idx++;
    if (idx >= items.length) finish();
    else showItem();
}

function answerCard(correct) {
    if (!revealed || answered) return;
    answered = true;
    recordAnswer(items[idx], correct);
    nextItem();
}

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

function finish() {
    $('learnFill').style.width = '100%';
    $('doneScore').textContent = t('score')(rightCount, answers.length);
    $('doneWrong').replaceChildren(...wrongItems.map(item => {
        const li = document.createElement('li');
        const word = document.createElement('b');
        word.textContent = item.original_word;
        li.append(word, document.createTextNode(` — ${item.translation}`));
        return li;
    }));
    $('doneWrong').hidden = !wrongItems.length;
    $('doneBack').textContent = CATEGORY ? t('backSet') : t('backToday');
    $('doneBack').href = BACK_URL;
    showView('doneView');
    submitResults();
}

/* Odchod krížikom: čo je zodpovedané, ostáva. Pýtať sa netreba — učenie sa dá
   kedykoľvek prerušiť a zvyšok príde nabudúce. */
async function leave(e) {
    e.preventDefault();
    await Promise.race([submitResults(), new Promise(resolve => setTimeout(resolve, 3000))]);
    window.location.href = BACK_URL;
}

/* Zavretá karta, tlačidlo späť, prepnutie appky na telefóne: doteraz nezapísané
   odpovede pošle beacon, ten prežije zánik stránky. */
window.addEventListener('pagehide', () => {
    if (answers.length === pendingFrom) return;
    const payload = answers.slice(pendingFrom);
    pendingFrom = answers.length;
    try {
        navigator.sendBeacon('/api/v1/words/test/submit',
            new Blob([JSON.stringify(payload)], { type: 'application/json' }));
    } catch (err) { /* stránka končí — viac sa spraviť nedá */ }
});

/* ── OVLÁDANIE ── */
$('closeBtn').href = BACK_URL;
$('closeBtn').addEventListener('click', leave);
$('flashcard').addEventListener('click', revealCard);
$('cardSpeak').addEventListener('click', e => {
    e.stopPropagation();
    speak(items[idx].original_word, items[idx]);
});
$('btnKnow').addEventListener('click', () => answerCard(true));
$('btnDont').addEventListener('click', () => answerCard(false));
$('btnNext').addEventListener('click', nextItem);
$('questionPlay').addEventListener('click', () => speak(items[idx].original_word, items[idx]));

document.addEventListener('keydown', e => {
    const item = items[idx];
    if (!item || e.ctrlKey || e.metaKey || e.altKey) return;
    if (item.exercise === 'card') {
        if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); revealCard(); }
        else if (e.key === '1') answerCard(false);
        else if (e.key === '2') answerCard(true);
        return;
    }
    if (/^[1-9]$/.test(e.key)) chooseOption(Number(e.key) - 1);
    // Enter na zaostrenom „Ďalej" rieši prehliadač, inak by preskočil dve úlohy.
    else if (e.key === 'Enter' && answered && e.target.id !== 'btnNext') nextItem();
});

setLang(currentLang);
loadSession();
