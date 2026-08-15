/* Spoločné čítanie slovíčok (Web Speech API) — jediný zdroj pravdy pre kartičky,
   opakovanie aj demo. Predtým mala každá stránka vlastnú kópiu a rozchádzali sa:
   `repeat` mapoval jazyk na locale a vyberal konkrétny hlas, kartičky a demo
   posielali holé „sk"/„en" bez hlasu — prehliadač potom čítal slovenský text
   anglickým hlasom, alebo mlčal.

   Globál: `window.LexiSpeech`. */
(function (global) {
    'use strict';

    var synth = ('speechSynthesis' in global) ? global.speechSynthesis : null;

    /* Krátky kód z DB („en") → locale pre Web Speech („en-US"). Bez regiónu je
       priradenie hlasu na prehliadači a časť z nich ho nenájde vôbec. */
    var LOCALE_BY_CODE = {
        en: 'en-US', sk: 'sk-SK', de: 'de-DE', fr: 'fr-FR', es: 'es-ES', cs: 'cs-CZ',
        it: 'it-IT', pl: 'pl-PL', ru: 'ru-RU', hu: 'hu-HU', pt: 'pt-PT', nl: 'nl-NL',
        uk: 'uk-UA', ro: 'ro-RO', sv: 'sv-SE', da: 'da-DK', no: 'nb-NO', fi: 'fi-FI',
        tr: 'tr-TR', el: 'el-GR', hr: 'hr-HR', sr: 'sr-RS', bg: 'bg-BG', sl: 'sl-SI',
    };

    function toLocale(code, fallback) {
        if (!code) return fallback;
        if (code.indexOf('-') !== -1) return code;
        return LOCALE_BY_CODE[code.toLowerCase()] || fallback;
    }

    /* Zoznam hlasov sa v Chrome plní asynchrónne — preto cache + onvoiceschanged. */
    var voices = [];
    function refreshVoices() {
        try { voices = synth ? synth.getVoices() : []; } catch (e) { voices = []; }
        return voices;
    }
    if (synth) {
        refreshVoices();
        synth.addEventListener
            ? synth.addEventListener('voiceschanged', refreshVoices)
            : (synth.onvoiceschanged = refreshVoices);
    }

    function pickVoice(lang) {
        if (!voices.length) refreshVoices();
        if (!voices.length) return null;
        var want = String(lang || '').toLowerCase().replace('_', '-');
        var base = want.split('-')[0];
        var norm = function (v) { return String(v.lang || '').toLowerCase().replace('_', '-'); };
        var exact = null, sameLang = null;
        for (var i = 0; i < voices.length; i++) {
            var vl = norm(voices[i]);
            if (!exact && vl === want) exact = voices[i];
            if (!sameLang && vl.split('-')[0] === base) sameLang = voices[i];
        }
        return exact || sameLang || null;
    }

    function hasVoiceFor(lang) { return !!pickVoice(lang); }

    /* Tempo reči si používateľ nastavuje v Opakovaní; kartičky ho odteraz rešpektujú
       (jedno nastavenie pre celú appku, žiadne druhé UI). */
    var RATE_KEY = 'wk_repeat_play_settings';
    var DEFAULT_RATE = 0.85;
    function getRate(fallback) {
        var def = typeof fallback === 'number' ? fallback : DEFAULT_RATE;
        try {
            var saved = JSON.parse(global.localStorage.getItem(RATE_KEY) || '{}');
            var rate = parseFloat(saved.rate);
            return (rate >= 0.5 && rate <= 2) ? rate : def;
        } catch (e) { return def; }
    }

    /* Chýbajúci systémový hlas je najčastejšia príčina „nečíta to" / „číta to divne".
       Bez upozornenia to vyzerá ako chyba appky, pritom sa hlas inštaluje v systéme.
       Hlásime raz za jazyk a reláciu — a len keď hlasy vôbec načítané sú (prázdny
       zoznam znamená „ešte neviem", nie „nie je hlas"). */
    var warned = {};
    function warnMissingVoice(lang) {
        if (!lang || warned[lang] || !voices.length) return;
        warned[lang] = true;
        var sk = (function () {
            try { return (global.localStorage.getItem('preferredLang') || 'en') === 'sk'; }
            catch (e) { return false; }
        })();
        var text = sk
            ? 'Pre jazyk ' + lang + ' nie je v zariadení nainštalovaný hlas — čítanie nemusí znieť správne.'
            : 'No voice for ' + lang + ' is installed on this device — playback may sound wrong.';

        var box = global.document.createElement('div');
        box.setAttribute('role', 'status');
        box.style.cssText = [
            'position:fixed', 'left:50%', 'bottom:1.25rem', 'transform:translateX(-50%)',
            'z-index:2000', 'max-width:min(90vw,26rem)', 'padding:.75rem 1rem',
            'border-radius:14px', 'font-size:.85rem', 'line-height:1.45', 'font-weight:600',
            'text-align:center', 'box-shadow:0 8px 28px rgba(15,23,42,.25)',
            'background:var(--card,#fff)', 'color:var(--text-main,#0f172a)',
            'border:1px solid var(--border,#e2e8f0)',
        ].join(';');
        box.textContent = '🔇 ' + text;
        global.document.body.appendChild(box);
        setTimeout(function () { box.remove(); }, 6000);
    }

    function buildUtterance(text, lang, rate) {
        var u = new global.SpeechSynthesisUtterance(text);
        if (lang) u.lang = lang;
        u.rate = typeof rate === 'number' ? rate : getRate();
        var voice = pickVoice(lang);
        if (voice) u.voice = voice;
        else warnMissingVoice(lang);
        return u;
    }

    /* ── Serverové hlasy ──────────────────────────────────────────────────
       Neurónové MP3 z `/api/v1/tts/...`. Znie to rovnako na každom zariadení,
       na rozdiel od systémových hlasov (Windows číta robotom, pre sk/hr/sl
       často nemá hlas vôbec).

       Zvuk ide z našej domény zámerne — CSP má `default-src 'self'` bez
       `media-src`, takže cudzí origin ani `blob:` by prehliadač zablokoval.

       Toto je vylepšenie, nie závislosť: čokoľvek zlyhá (vypnuté TTS, offline,
       blokované autoplay) → padáme na `speechSynthesis` nižšie. */

    function wordAudioUrl(wordId, isOriginal) {
        // Stránka vypína serverové hlasy cez `window.LEXI_TTS` — bez toho by sme
        // pri vypnutom TTS strieľali 503-ku na každé slovo, kým naskočí fallback.
        if (global.LEXI_TTS === false) return null;
        // Offline slovo z cache nemá id — prečíta sa systémovým hlasom.
        if (wordId == null) return null;
        return '/api/v1/tts/word/' + wordId + '/' + (isOriginal ? 'original' : 'translation') + '.mp3';
    }

    /* Stiahne zvuk dopredu do HTTP cache prehliadača. Bez toho sa slovo
       syntetizuje až keď naň príde rad — a používateľ čaká na server. */
    function prefetch(src) {
        if (!src || global.LEXI_TTS === false) return;
        if (remoteFails >= REMOTE_FAIL_LIMIT || !global.fetch) return;
        try {
            global.fetch(src, { credentials: 'same-origin' }).catch(function () {});
        } catch (e) {}
    }

    var currentAudio = null;
    /* Prehrávanie sa zastavuje zvonku (`cancel()`), no `pause()` nevyvolá ani
       `onended` ani `onerror` — bez tohto by promise z `playRemote` nikdy
       nedobehol a `await` v auto-play slučke by zamrzol. */
    var currentSettle = null;
    /* Po sérii zlyhaní prestaneme server otravovať do konca relácie — inak by
       každé slovo pri vypnutom TTS znamenalo zbytočný request navyše. */
    var remoteFails = 0;
    var REMOTE_FAIL_LIMIT = 3;

    function stopRemote() {
        if (!currentAudio) return;
        try { currentAudio.pause(); } catch (e) {}
        currentAudio = null;
        /* Rezolvujeme, nie rejectujeme: zastavenie je zámer používateľa.
           Reject by spustil fallback a appka by po „stop" začala hovoriť. */
        var settle = currentSettle;
        currentSettle = null;
        if (settle) settle(true);
    }

    /* Koľko čakáme, kým zvuk vôbec začne hrať. Prvé slovo server syntetizuje
       za behu a Cloud Run k tomu môže pridať studený štart — ale keď to trvá
       dlhšie, je lepšie prečítať systémovým hlasom než nechať používateľa
       čakať. */
    var LOAD_TIMEOUT_MS = 6000;

    /* Rezolvuje po dohratí, rejectuje pri akomkoľvek probléme — volajúci to
       berie ako signál „skús systémový hlas".

       POZOR: samotné `onended`/`onerror` nestačia. Pomaly sa načítavajúce
       audio nevyvolá ani jedno — visí. Bez stropu nižšie potom `await` v
       auto-play slučke zamrzne natrvalo (stalo sa na prode 2026-08-15). */
    function playRemote(src, rate) {
        return new Promise(function (resolve, reject) {
            if (!src || !global.Audio || remoteFails >= REMOTE_FAIL_LIMIT) { reject(); return; }

            var audio = new global.Audio(src);
            audio.preload = 'auto';
            /* Tempo rieši prehrávač, nie syntéza — jedna nahrávka pokryje
               všetky rýchlosti a cache tak ostáva malá. */
            var r = typeof rate === 'number' ? rate : getRate();
            try { audio.playbackRate = (r >= 0.5 && r <= 2) ? r : 1; } catch (e) {}

            var done = false;
            var loadGuard = null, endGuard = null;

            var finish = function (ok) {
                if (done) return;
                done = true;
                clearTimeout(loadGuard);
                clearTimeout(endGuard);
                if (currentAudio === audio) { currentAudio = null; currentSettle = null; }
                if (!ok) {
                    // Zastav aj visiace sťahovanie, nech nezožiera spojenie.
                    try { audio.pause(); audio.src = ''; } catch (e) {}
                    remoteFails++;
                    reject();
                    return;
                }
                remoteFails = 0;
                resolve();
            };

            audio.onended = function () { finish(true); };
            audio.onerror = function () { finish(false); };

            /* Len čo zvuk reálne hrá, strop na načítanie zrušíme a nahradíme
               poistkou na dĺžku nahrávky — inak by dlhšie slovo spadlo do
               fallbacku uprostred prehrávania. */
            audio.onplaying = function () {
                clearTimeout(loadGuard);
                var dur = audio.duration;
                var ms = (isFinite(dur) && dur > 0)
                    ? (dur / (audio.playbackRate || 1)) * 1000 + 3000
                    : 15000;
                endGuard = setTimeout(function () { finish(true); }, ms);
            };

            loadGuard = setTimeout(function () { finish(false); }, LOAD_TIMEOUT_MS);

            stopRemote();
            currentAudio = audio;
            currentSettle = finish;
            var played = audio.play();
            // Blokované autoplay vracia odmietnutý promise — tiež fallback.
            if (played && played.catch) played.catch(function () { finish(false); });
        });
    }

    /* Jednorazové prečítanie (ťuknutie na 🔊). Predošlú reč ruší, ale `cancel()`
       a `speak()` v tom istom ticku Chrome občas zhltne — preto odklad. */
    function speak(text, lang, options) {
        var opts = options || {};

        if (opts.src) {
            cancel();  // ruší aj prebiehajúce audio (stopRemote vnútri)
            playRemote(opts.src, opts.rate).catch(function () {
                speak(text, lang, { rate: opts.rate });
            });
            return;
        }

        if (!synth || !text) return;
        var u = buildUtterance(text, lang, opts.rate);
        var start = function () { try { synth.speak(u); } catch (e) {} };
        if (synth.speaking || synth.pending) {
            try { synth.cancel(); } catch (e) {}
            setTimeout(start, 60);
        } else {
            start();
        }
        return u;
    }

    /* Vráti promise, ktorý dobehne až koncom reči — sekvenciu tak riadi skutočná
       dĺžka slova, nie pevný časovač. Nikdy neruší prebiehajúcu reč (volajúci
       si poradie serializuje sám). */
    function speakAsync(text, lang, rate, src) {
        if (src) {
            return playRemote(src, rate).catch(function () {
                return speakAsync(text, lang, rate);  // bez `src` → systémový hlas
            });
        }
        return new Promise(function (resolve) {
            if (!synth || !text) { resolve(); return; }
            var done = false;
            var guard;
            var finish = function () { if (done) return; done = true; clearTimeout(guard); resolve(); };
            var u = buildUtterance(text, lang, rate);
            u.onend = finish;
            u.onerror = finish;
            // Poistka: Chrome občas onend nezavolá a utterance sa stratí vo fronte.
            var estMs = (String(text).length / 12) * 1000 / (u.rate || 1);
            guard = setTimeout(finish, Math.max(2500, estMs + 4000));
            try { synth.speak(u); } catch (e) { finish(); }
        });
    }

    function cancel() {
        stopRemote();
        try { if (synth) synth.cancel(); } catch (e) {}
    }

    global.LexiSpeech = {
        available: !!synth,
        LOCALE_BY_CODE: LOCALE_BY_CODE,
        toLocale: toLocale,
        refreshVoices: refreshVoices,
        pickVoice: pickVoice,
        hasVoiceFor: hasVoiceFor,
        getRate: getRate,
        speak: speak,
        speakAsync: speakAsync,
        cancel: cancel,
        wordAudioUrl: wordAudioUrl,
        prefetch: prefetch,
    };
})(window);
