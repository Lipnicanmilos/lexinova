/* Presunute z flashcard_test.html — inline JS sa nedalo cachovat. */
/* ── CONFIG ── */
/* URL je zdroj pravdy pre kategóriu/level. Offline môže service worker poslať
   cachovanú verziu /test s INÝMI query parametrami (matchuje cez ignoreSearch),
   takže hodnoty zapečené Jinjou v HTML by boli nesprávne (napr. „všetky slová"
   namiesto zvoleného levelu). Adresný riadok však vždy drží reálne parametre. */
const _q        = new URLSearchParams(location.search);
const CAT_ID    = _q.get('category') ? parseInt(_q.get('category'), 10) : PAGE_DATA.categoryId;
const CAT_NAME  = PAGE_DATA.categoryName;
const LEVEL_RAW = _q.get('level') || PAGE_DATA.level;

/* ── LABELS ── */
const L = {
    en: {
        topDash:    '← Dashboard',
        leaveTitle:  'End the test?',
        leaveWarn:   'Do you really want to end the flashcard test? Your answers so far will be saved.',
        leaveStay:   'Stay',
        leaveConfirm:'End test',
        loggedIn:   'Logged in as',
        dirFwd:     'Original → Translation',
        dirRev:     'Translation → Original',
        wordNum:    (i,t) => `Word ${i} / ${t}`,
        scoreStr:   (k,d) => `✅ ${k}   😕 ${d}`,
        flipHint:   '👆 Click to reveal translation',
        flipHintRev:'👆 Click to reveal original',
        btnDont:    "😕 Don't know",
        btnKnow:    '✅ I know',
        scoreLbl:   'accuracy',
        scoreLblEarly: 'of the deck',
        hintRate:   'know / don\u2019t know',
        wrongTitle: 'Words you didn\u2019t know',
        practiceWrong: '\u2192 Practice just these',
        statKnow:   n => `✅ ${n} know`,
        statDont:   n => `😕 ${n} don't know`,
        results: {
            high: { title:'🌟 Excellent!',        msg:'Great result — you know most of the words. Keep it up!' },
            mid:  { title:'💪 Good job!',          msg:'Solid progress! Keep practising the words you missed.' },
            low:  { title:'📚 Keep practising!',  msg:"Don't worry — with regular practice you'll get there. Try again!" },
        },
        retry:       '🔁 Try again',
        dashboard:   '← Dashboard',
        finish:      'Finish & save',
        spaceKey:    'Space',
        hintReveal:  'show translation',
        hintHide:    'hide translation',
        hintPrev:    'previous card',
        hintNext:    'next card — marks it as “Don’t know”',
        hintSpeak:   'play the word',
        earlyNote:   n => `Test ended early — answers from ${n} card${n === 1 ? '' : 's'} saved.`,
        loading:     'Loading words…',
        noWords:     'No words found for this test. <a href="/dashboard">Back to Dashboard</a>',
        offlineNote: '📡 You are offline — results will sync automatically once you reconnect.',
        saving:      'Saving results…',
    },
    sk: {
        topDash:    '← Nástenka',
        leaveTitle:  'Ukončiť test?',
        leaveWarn:   'Naozaj chceš ukončiť test kartičiek? Doterajšie odpovede sa uložia.',
        leaveStay:   'Zostať',
        leaveConfirm:'Ukončiť test',
        loggedIn:   'Prihlásený ako',
        dirFwd:     'Originál → Preklad',
        dirRev:     'Preklad → Originál',
        wordNum:    (i,t) => `Slovíčko ${i} / ${t}`,
        scoreStr:   (k,d) => `✅ ${k}   😕 ${d}`,
        flipHint:   '👆 Klikni pre zobrazenie prekladu',
        flipHintRev:'👆 Klikni pre zobrazenie originálu',
        btnDont:    '😕 Neviem',
        btnKnow:    '✅ Viem',
        scoreLbl:   'úspešnosť',
        scoreLblEarly: 'z balíka',
        hintRate:   'neviem / viem',
        wrongTitle: 'Slová, ktoré si nevedel',
        practiceWrong: '\u2192 Precvičiť len tieto',
        statKnow:   n => `✅ ${n} viem`,
        statDont:   n => `😕 ${n} neviem`,
        results: {
            high: { title:'🌟 Výborné!',          msg:'Výborný výsledok — väčšinu slovíčok vieš. Tak ďalej!' },
            mid:  { title:'💪 Dobrý výsledok!',   msg:'Dobrý pokrok! Pokračuj v precvičovaní slovíčok, ktoré ti nešli.' },
            low:  { title:'📚 Ešte treba trénovať!', msg:'Nevadí — s pravidelným opakovaním to zvládneš. Skús to znova!' },
        },
        retry:       '🔁 Skúsiť znova',
        dashboard:   '← Nástenka',
        finish:      'Ukončiť a uložiť',
        spaceKey:    'Medzerník',
        hintReveal:  'zobraziť preklad',
        hintHide:    'skryť preklad',
        hintPrev:    'predchádzajúca kartička',
        hintNext:    'ďalšia kartička — označí „Neviem“',
        hintSpeak:   'prehrať slovíčko',
        earlyNote:   n => `Test ukončený predčasne — uložené odpovede z ${n} ${n === 1 ? 'kartičky' : 'kartičiek'}.`,
        loading:     'Načítavam slovíčka…',
        noWords:     'Pre tento test sa nenašli žiadne slovíčka. <a href="/dashboard">Späť na nástenku</a>',
        offlineNote: '📡 Si offline — výsledky sa automaticky odošlú po pripojení.',
        saving:      'Ukladám výsledky…',
    }
};

/* ── STATE ── */
let lang         = localStorage.getItem('preferredLang') || 'en';
let direction    = 'original_to_translation';
let words        = [];
let idx          = 0;
let scoreKnow    = 0;
let scoreDont    = 0;
let isFlipped    = false;
let answers      = [];   // { word_id, is_correct }
let answered     = new Set();   // id už zodpovedaných kartičiek (návrat šípkou)
let pendingFrom  = 0;    // index prvej ešte neodoslanej odpovede (poistka proti dvojitému zápisu)
let leaving      = false;// odchádzame vedome (cez modál) → beforeunload nemá vyskakovať
let guardArmed   = false;// v histórii je naša strážna položka (kvôli tlačidlu späť)
let submitPromise = Promise.resolve();   // sľub uloženia výsledkov (počkáme naň pred odchodom)

/* ── LANGUAGE ── */
function setLang(l) {
    lang = l;
    localStorage.setItem('preferredLang', l);
    document.querySelectorAll('.lang-mini button').forEach(b =>
        b.classList.toggle('active', b.getAttribute('data-lang') === l));
    applyLabels();
}

function applyLabels() {
    const lbl = L[lang];
    // Ikonové tlačidlá nemajú text — názov pre čítačky obrazovky a bublinu
    // treba prekladať zvlášť.
    document.querySelectorAll('[data-en-label]').forEach(el => {
        const t = el.getAttribute(`data-${lang}-label`);
        if (t) { el.title = t; el.setAttribute('aria-label', t); }
    });
    document.getElementById('backLink').textContent      = lbl.topDash;
    document.getElementById('labelLoggedIn').textContent = lbl.loggedIn;
    document.getElementById('dirFwdLabel').textContent   = lbl.dirFwd;
    document.getElementById('dirRevLabel').textContent   = lbl.dirRev;
    document.getElementById('btnDont').textContent       = lbl.btnDont;
    document.getElementById('btnKnow').textContent       = lbl.btnKnow;
    document.getElementById('ctaRetry').textContent      = lbl.retry;
    document.getElementById('ctaDashboard').textContent  = lbl.dashboard;
    document.getElementById('btnFinishLabel').textContent = lbl.finish;
    document.getElementById('hintSpaceKey').textContent = lbl.spaceKey;
    document.getElementById('hintRate').textContent = lbl.hintRate;
    document.getElementById('hintReveal').textContent   = lbl.hintReveal;
    document.getElementById('hintHide').textContent     = lbl.hintHide;
    document.getElementById('hintPrev').textContent     = lbl.hintPrev;
    document.getElementById('hintNext').textContent     = lbl.hintNext;
    document.getElementById('hintSpeak').textContent    = lbl.hintSpeak;
    if (words.length) updateProgressUI();
}

/* Predčasné ukončenie priamo na obrazovke testu: potvrdenie, uloženie
   doterajších odpovedí a rovnaká výsledková obrazovka ako po dokončení —
   len počítaná zo zodpovedaných kartičiek, nie z celého balíka. */
async function finishEarly() {
    if (!isTestInProgress()) return;
    if (!(await confirmLeave())) return;
    showResults({ early: true });
}

/* ── LEAVE → DASHBOARD (s upozornením, ak test beží) ── */
/* Test beží = je zobrazená testovacia obrazovka a ostávajú nezodpovedané karty. */
function isTestInProgress() {
    return document.getElementById('testScreen').style.display === 'block' &&
           words.length > 0 && idx < words.length;
}

async function goDashboard(e) {
    if (e) e.preventDefault();
    if (isTestInProgress()) {
        if (!(await confirmLeave())) return false;
        // Predčasné ukončenie: ulož zmeny levelu pre doteraz zodpovedané karty.
        submitPromise = submitResults();
    }
    // Počkaj na uloženie výsledkov, aby dashboard ukázal čerstvé čísla — ale
    // s viditeľnou odozvou a stropom 5 s: fetch má keepalive, takže sa uloženie
    // dokončí aj po odchode zo stránky, len dashboard môže chvíľu ukazovať staré čísla.
    document.getElementById('savingText').textContent = L[lang].saving;
    document.getElementById('savingOverlay').classList.add('show');
    try { await Promise.race([submitPromise, new Promise(r => setTimeout(r, 5000))]); } catch {}
    leaving = true;   // odchod je potvrdený → beforeunload nesmie pýtať znova
    window.location.href = '/dashboard';
    return false;
}

/* Vlastný potvrdzovací modal v štýle appky (namiesto natívneho confirm).
   Vráti Promise<boolean> — true = ukončiť test, false = zostať. Text aj tlačidlá
   sú v aktuálnom jazyku. */
function confirmLeave() {
    return new Promise(resolve => {
        const lbl = L[lang];
        const modal = document.getElementById('leaveModal');
        const stayBtn = document.getElementById('leaveStayBtn');
        const confirmBtn = document.getElementById('leaveConfirmBtn');

        document.getElementById('leaveTitle').textContent = lbl.leaveTitle;
        document.getElementById('leaveText').textContent  = lbl.leaveWarn;
        stayBtn.textContent    = lbl.leaveStay;
        confirmBtn.textContent = lbl.leaveConfirm;
        modal.classList.add('show');

        function cleanup(result) {
            modal.classList.remove('show');
            stayBtn.removeEventListener('click', onStay);
            confirmBtn.removeEventListener('click', onLeave);
            modal.removeEventListener('click', onBackdrop);
            document.removeEventListener('keydown', onKey);
            resolve(result);
        }
        const onStay = () => cleanup(false);
        const onLeave = () => cleanup(true);
        const onBackdrop = e => { if (e.target === modal) cleanup(false); };
        const onKey = e => { if (e.key === 'Escape') cleanup(false); };

        stayBtn.addEventListener('click', onStay);
        confirmBtn.addEventListener('click', onLeave);
        modal.addEventListener('click', onBackdrop);
        document.addEventListener('keydown', onKey);
    });
}

/* ── DARK MODE ── */
function toggleDark() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    document.documentElement.setAttribute('data-theme', isDark ? 'light' : 'dark');
    localStorage.setItem('darkMode', !isDark);
}

/* ── TEST DIRECTION ── */
function setDirection(dir) {
    direction = dir;
    document.getElementById('dirFwd').classList.toggle('active', dir === 'original_to_translation');
    document.getElementById('dirRev').classList.toggle('active', dir === 'translation_to_original');
    restartTest();
}

/* ── LOAD WORDS ── */
async function loadWords() {
    document.getElementById('testScreen').style.display = 'none';
    document.getElementById('resultsScreen').style.display = 'none';
    document.getElementById('emptyMsg').style.display = 'none';
    document.getElementById('loadingMsg').style.display = 'block';
    document.getElementById('loadingMsg').textContent = L[lang].loading;

    // Determine which levels to load
    let levels;
    if (LEVEL_RAW === 'know') {
        levels = ['know'];
    } else if (LEVEL_RAW === 'dont_know') {
        levels = ['dont_know', 'learning'];  // treat legacy 'learning' as dont_know
    } else {
        levels = ['dont_know', 'learning', 'know'];
    }

    const body = { knowledge_levels: levels, limit: 1000, test_direction: direction };
    if (CAT_ID) body.category_id = CAT_ID;

    let data = null;

    try {
        if (!navigator.onLine) throw new Error('offline');
        const res = await fetch('/api/v1/words/test/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        data = await res.json();
    } catch (e) {
        // Sieť zlyhala / offline → skús offline cache.
        console.warn('[WK] test/start zlyhal, skúšam offline cache:', e);
        data = loadFromOfflineCache(levels);
    }

    document.getElementById('loadingMsg').style.display = 'none';

    if (!data || data.length === 0) {
        document.getElementById('emptyMsg').style.display = 'block';
        document.getElementById('emptyMsg').innerHTML = L[lang].noWords;
        return;
    }

    words = shuffleArr(data);
    idx = 0; scoreKnow = 0; scoreDont = 0; answers = []; answered = new Set(); pendingFrom = 0;
    document.getElementById('testScreen').style.display = 'block';
    armHistoryGuard();
    showCard();
}

/* Zlúči slovíčka z offline cache pre požadované levely (per-level kľúče).
   Cache sa prefetchuje len pre 'original_to_translation'. Pri reverznom smere
   prehodíme polia na klientovi (rovnako ako to robí backend pri swap_direction).
   Bez kategórie (test „všetky slová") sa zlúčia cache všetkých kategórií
   známych z dashboardu (wk_cached_categories). */
function loadFromOfflineCache(levels) {
    if (!window.WKOfflineCache) return null;
    let catIds = [];
    if (CAT_ID) {
        catIds = [CAT_ID];
    } else {
        try {
            const cats = JSON.parse(localStorage.getItem('wk_cached_categories') || '[]');
            catIds = cats.map(c => c && c.id).filter(Boolean);
        } catch (e) { /* poškodená cache → žiadny fallback */ }
    }
    if (!catIds.length) return null;

    const seen = new Set();
    const merged = [];
    const isRev = direction === 'translation_to_original';
    // offline-cache ukladá len 'dont_know' a 'know'; 'learning' mapuj na 'dont_know'.
    const cacheLevels = [...new Set(levels.map(l => l === 'learning' ? 'dont_know' : l))];
    for (const catId of catIds) {
        for (const level of cacheLevels) {
            const key = WKOfflineCache.offlineWordsCacheKey({
                categoryId: catId,
                level,
                testDirection: WKOfflineCache.DEFAULT_TEST_DIRECTION  // vždy 'original_to_translation'
            });
            const cached = WKOfflineCache.loadOfflineWordsFromCache(key);
            if (!cached) continue;
            for (const w of cached) {
                const id = w.id != null ? w.id : `${w.original_word}|${w.translation}`;
                if (seen.has(id)) continue;
                seen.add(id);
                if (isRev) {
                    // Prehoď polia (zhodné so serverovým swap_direction).
                    merged.push({
                        ...w,
                        original_word: w.translation,
                        translation: w.original_word,
                        language_from: w.language_to,
                        language_to: w.language_from
                    });
                } else {
                    merged.push(w);
                }
            }
        }
    }
    return merged.length ? merged : null;
}

/* ── CARD FLOW ── */
function shuffleArr(arr) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
}

function showCard() {
    isFlipped = false;
    const w = words[idx];
    const isRev = direction === 'translation_to_original';

    document.getElementById('wordLang').textContent  = w.language_from;
    document.getElementById('wordText').textContent  = w.original_word;
    document.getElementById('transLang').textContent = w.language_to;
    document.getElementById('transText').textContent = w.translation;
    document.getElementById('translationBlock').style.display = 'none';
    document.getElementById('flipHint').textContent = isRev ? L[lang].flipHintRev : L[lang].flipHint;
    document.getElementById('flipHint').style.display = 'flex';
    document.getElementById('flashcard').classList.remove('flipped');

    ['btnDont','btnKnow'].forEach(id => document.getElementById(id).classList.remove('visible'));
    updateProgressUI();
}

function updateProgressUI() {
    const lbl = L[lang];
    document.getElementById('progressText').textContent = lbl.wordNum(idx + 1, words.length);
    document.getElementById('scoreText').innerHTML = lbl.scoreStr(scoreKnow, scoreDont);
    document.getElementById('progressFill').style.width = `${(idx / words.length) * 100}%`;
}

/* Skrytie prekladu späť — v Opakovaní to šípka nadol vie, v teste sa raz
   odkrytý preklad nedal schovať a nezostávalo než si slovo pamätať. */
function hideTranslation() {
    if (!isFlipped) return;
    isFlipped = false;
    document.getElementById('flashcard').classList.remove('flipped');
    document.getElementById('translationBlock').style.display = 'none';
    document.getElementById('flipHint').style.display = '';
}

function flipCard() {
    if (isFlipped) return;
    isFlipped = true;
    document.getElementById('flashcard').classList.add('flipped');
    document.getElementById('translationBlock').style.display = 'block';
    document.getElementById('flipHint').style.display = 'none';
    setTimeout(() => ['btnDont','btnKnow'].forEach(id =>
        document.getElementById(id).classList.add('visible')), 150);
}

function recordAnswer(know) {
    if (!words.length) return;
    // Návrat šípkou vľavo na už zodpovedanú kartičku ju nesmie započítať znova.
    if (answered.has(words[idx].id)) { moveCard(1); return; }
    if (know) scoreKnow++; else scoreDont++;
    answered.add(words[idx].id);
    answers.push({ word_id: words[idx].id, is_correct: know });
    idx++;
    if (idx >= words.length) showResults();
    else showCard();
}

/* Tlačidlá Neviem/Viem — až po odkrytí prekladu, inak by sa dalo odpovedať
   naslepo. Klávesnica má vlastnú cestu (šípka doprava), ktorá odkrytie
   nevyžaduje. */
function answer(know) {
    if (!isFlipped) return;
    recordAnswer(know);
}

/* Presun medzi kartičkami šípkami — rovnako ako v Opakovaní sa pri ňom nič
   nezapisuje a úroveň slovíčka ostáva nedotknutá. Na konci balíka sa test
   nedokončí sám: preskočené kartičky si používateľ môže prejsť znova a
   ukončiť ho tlačidlom. */
function moveCard(step) {
    if (!words.length) return;
    const target = idx + step;
    if (target < 0 || target >= words.length) return;
    idx = target;
    showCard();
}

/* ── RESULTS ── */
/* Slová označené ako „Neviem" — s prekladom, nech sa dajú rovno prejsť. */
/* Slová z databázy idú do innerHTML, takže musia prejsť escapovaním. */
function escapeHtml(str) {
    return String(str).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

function renderWrongWords() {
    const wrongIds = answers.filter(a => !a.is_correct).map(a => a.word_id);
    const box = document.getElementById('wrongList');
    if (!wrongIds.length) { box.style.display = 'none'; return; }

    const byId = new Map(words.map(w => [w.id, w]));
    document.getElementById('wrongTitle').textContent = L[lang].wrongTitle;
    document.getElementById('wrongWords').innerHTML = wrongIds
        .map(id => byId.get(id))
        .filter(Boolean)
        .map(w => '<li><b>' + escapeHtml(w.original_word) + '</b> <span>— '
                  + escapeHtml(w.translation) + '</span></li>')
        .join('');
    box.style.display = 'block';

    const practice = document.getElementById('ctaPracticeWrong');
    if (CAT_ID) {
        practice.textContent = L[lang].practiceWrong;
        practice.href = `/test?category=${CAT_ID}&level=dont_know`;
        practice.style.display = 'inline-flex';
    } else {
        practice.style.display = 'none';
    }
}

async function showResults({ early = false } = {}) {
    document.getElementById('testScreen').style.display = 'none';
    const el = document.getElementById('resultsScreen');
    el.style.display = 'block';

    // Úspešnosť vždy zo zodpovedaných kartičiek — preskočené (šípkou) ani
    // nedokončené by ju inak umelo znižovali.
    const total = scoreKnow + scoreDont;
    const pct   = total ? Math.round((scoreKnow / total) * 100) : 0;
    const tier  = pct >= 80 ? 'high' : pct >= 50 ? 'mid' : 'low';
    const lbl   = L[lang];

    // Percento z jednej zodpovedanej kartičky nič nehovorí („100 % · Výborné!"
    // po 1 z 21). Pri predčasnom ukončení preto ukážeme počet, nie percento.
    const partial = early && total < words.length;
    document.getElementById('scorePct').textContent = partial
        ? `${total}/${words.length}` : pct + '%';
    document.getElementById('scoreLbl').textContent = partial ? lbl.scoreLblEarly : lbl.scoreLbl;
    document.getElementById('resultTitle').textContent = lbl.results[tier].title;
    document.getElementById('resultMsg').textContent   = lbl.results[tier].msg;
    document.getElementById('statKnow').textContent   = lbl.statKnow(scoreKnow);
    document.getElementById('statDont').textContent   = lbl.statDont(scoreDont);

    if (early) {
        document.getElementById('resultMsg').textContent = lbl.earlyNote(total);
    }

    renderWrongWords();

    // Cieľ funnelu — až tu je test naozaj dokončený. Predčasné ukončenie, odchod
    // cez modál ani poistný beacon sem nevedú, takže sa nezapočítajú.
    if (!early) window.lexiTrack('Test dokonceny', { uspesnost: tier });

    // Ulož výsledky; sľub si podržíme, aby sme naň počkali pred odchodom na dashboard
    // (inak by dashboard načítal štatistiky ešte pred uložením → staré čísla).
    submitPromise = submitResults().then(status => {
        if (status === 'queued') {
            document.getElementById('resultMsg').textContent += ' ' + L[lang].offlineNote;
        }
    });
}

async function submitResults() {
    // Posielame len odpovede, ktoré ešte neodišli — inak by sa pri kombinácii
    // „modál + poistný beacon" tie isté karty započítali dvakrát (times_tested).
    if (answers.length === pendingFrom) return 'empty';
    const payload = answers.slice(pendingFrom);
    pendingFrom = answers.length;
    try {
        if (!navigator.onLine) throw new Error('offline');
        const res = await fetch('/api/v1/words/test/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            keepalive: true   // dokončí sa aj keď používateľ medzitým odnaviguje preč
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return 'saved';
    } catch (e) {
        // Offline / výpadok → do fronty; odošle sa automaticky po pripojení.
        console.warn('Submit failed, queueing results:', e);
        if (window.WKOfflineCache) WKOfflineCache.queueTestResults(payload);
        return 'queued';
    }
}

function restartTest() {
    document.getElementById('resultsScreen').style.display = 'none';
    loadWords();
}

/* ── SPEECH ── */
/* Čítanie rieši zdieľaný `speech.js` (locale + výber hlasu + tempo z nastavení
   Opakovania). Jazyk berieme z popisku pod slovom — ten už zohľadňuje smer testu. */
function speakWord(e)  { e.stopPropagation(); speakCurrentWord(); }

/* Prehrá slovíčko na prednej strane kartičky (v opačnom smere testu je to
   preklad — vždy to, čo je práve zobrazené). Volá to aj medzerník. */
function speakCurrentWord() { speakFrom('wordText', 'wordLang', 'en-US'); }
function speakTrans(e) { e.stopPropagation(); speakFrom('transText', 'transLang', 'sk-SK'); }
function speakFrom(textId, langId, fallbackLocale) {
    const text = document.getElementById(textId).textContent;
    const lang = LexiSpeech.toLocale(document.getElementById(langId).textContent, fallbackLocale);
    LexiSpeech.speak(text, lang);
}

/* ── ODCHOD INAK AKO ODKAZOM „← Dashboard" ──
   Tlačidlo späť (v prehliadači aj hardvérové na mobile) predtým odišlo z testu
   ticho a bez uloženia odpovedí. Do histórie preto pridáme strážnu položku:
   back ju vyberie, my ju hneď vrátime a namiesto odchodu ukážeme ten istý modál
   ako pri odkaze. Zavretú kartu / reload rieši beforeunload + poistný beacon. */
function armHistoryGuard() {
    if (guardArmed) return;              // v histórii stačí jedna stráž
    history.pushState({ lexiTestGuard: true }, '');
    guardArmed = true;
}

window.addEventListener('popstate', () => {
    const wasArmed = guardArmed;
    guardArmed = false;                  // strážna položka je práve spotrebovaná
    if (isTestInProgress()) {
        armHistoryGuard();               // vráť ju hneď — modál môže byť otvorený dlho
        goDashboard(null);               // potvrdenie + uloženie + odchod (rovnaká cesta ako odkaz)
        return;
    }
    // Test nebeží (výsledky / prázdny zoznam) → späť má fungovať normálne,
    // takže dokrič ešte jeden krok späť za spotrebovanú stráž.
    if (wasArmed) history.back();
});

window.addEventListener('beforeunload', e => {
    // Len tvrdý odchod (zavretie karty, reload, iná adresa) s nezapísanými odpoveďami.
    if (leaving || !isTestInProgress() || answers.length === pendingFrom) return;
    e.preventDefault();
    e.returnValue = '';                  // text dialógu si určuje prehliadač, nedá sa prepísať
});

/* Posledná poistka: ak stránka aj tak zmizne (zavretá karta, prepnutie appky na
   mobile), pošli doteraz nezapísané odpovede beaconom — ten prežije zánik stránky. */
window.addEventListener('pagehide', () => {
    if (answers.length === pendingFrom) return;
    const payload = answers.slice(pendingFrom);
    pendingFrom = answers.length;
    try {
        navigator.sendBeacon('/api/v1/words/test/submit',
            new Blob([JSON.stringify(payload)], { type: 'application/json' }));
    } catch (err) { /* stránka končí — viac sa spraviť nedá */ }
});

/* ── KEYBOARD ── */
document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT') return;
    // Keď je otvorený potvrdzovací modal, klávesy neovládajú kartu za ním.
    if (document.getElementById('leaveModal').classList.contains('show')) return;
    // Medzerník prehrá zobrazené slovíčko; šípka doprava posunie ďalej a
    // kartičku pritom označí ako „Neviem" (preskočené = nevedel som ho).
    // „Viem" ostáva zámerne len na tlačidle — omylom stlačená klávesa by
    // slovíčko označila za zvládnuté a prestalo by sa vracať.
    if (e.key === ' ') { e.preventDefault(); speakCurrentWord(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); flipCard(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); hideTranslation(); }
    else if (e.key === 'ArrowLeft')  { e.preventDefault(); moveCard(-1); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); recordAnswer(false); }
    // 1 = Neviem, 2 = Viem. Rovnako ako tlačidlá fungujú až po odkrytí
    // prekladu — inak by sa dalo odpovedať naslepo.
    else if (e.key === '1') { e.preventDefault(); answer(false); }
    else if (e.key === '2') { e.preventDefault(); answer(true); }
});


/* ── INIT ── */
document.querySelectorAll('.lang-mini button').forEach(b =>
    b.addEventListener('click', () => setLang(b.getAttribute('data-lang'))));
document.getElementById('darkToggle').addEventListener('click', toggleDark);

setLang(lang);    // apply labels
loadWords();
