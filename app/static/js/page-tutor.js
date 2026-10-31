/* AI tútor s pamäťou (/tutor).

   Hlas dnu: prehliadač nahráva (MediaRecorder) a sám pozná, kedy hovoríš —
   hlasitosť z mikrofónu porovnáva s hlukom v miestnosti. Po vete a krátkom
   tichu pošle nahrávku na /transcribe; Whisper vráti text aj jazyk, takže sa dá
   hovoriť po anglicky aj po slovensky bez prepínania. Funguje aj vo Firefoxe.
   „Plynulý rozhovor" nechá mikrofón zapnutý: po odpovedi Lexi sa znova počúva
   a keď začneš hovoriť počas jej reči, Lexi stíchne (skočenie do reči).

   Hlas von: LexiSpeech (syntéza reči prehliadača). Odpoveď číta hlas jazyka,
   ktorý sa učíš; pomoc po slovensky („ⓘ …") slovenský hlas, ak ho zariadenie má.

   Avatar má štyri stavy (data-state): idle, listening, thinking, speaking
   a náladu (data-mood): neutral, happy (pochvala), correcting (oprava chyby).
   Vzhľad je v CSS; JS len prepína atribúty, žmurká v náhodných intervaloch
   a hýbe perami podľa slov, ktoré hlas práve číta (udalosť `onboundary`).
   Presný lip-sync podľa hlások by potreboval zvuk, a ten hlas prehliadača
   nedáva — tvar úst sa preto odhaduje zo samohlások slova.

   Rozhovor drží server; po načítaní stránky sa rozbehnutá relácia obnoví
   z /api/v1/tutor/state. Zavretie stránky reláciu neukončí — zhrnie sa pri
   ďalšom štarte, takže sa nič nestratí. */
(function () {
    'use strict';

    var API = '/api/v1/tutor';
    var lang = (function () { try { return localStorage.getItem('preferredLang') || 'sk'; } catch (e) { return 'sk'; } })();

    /* 1 slovíčko, 2–4 slovíčka, 5+ slovíčok */
    function skPlural(n, one, few, many) { return n === 1 ? one : (n >= 2 && n <= 4 ? few : many); }

    var T = {
        sk: {
            loading: 'Načítavam…', ready: 'Som pripravená. Začneme?', listening: 'Počúvam…',
            thinking: 'Premýšľam…', speaking: 'Hovorím…', yourTurn: 'Tvoj rad.',
            unavailable: 'AI tútor nie je dostupný.', ended: 'Rozhovor je uložený v pamäti.',
            saving: 'Ukladám rozhovor do pamäte…', netError: 'Chyba spojenia. Skús to znova.',
            correction: 'Oprava', you: 'Ty', sessions: function (n) { return n + ' ' + skPlural(n, 'rozhovor', 'rozhovory', 'rozhovorov') + ' v pamäti'; },
            left: function (s, d) { return 'Zostáva ' + s + ' správ v rozhovore · ' + d + ' dnes'; },
            nothingYet: 'Zatiaľ nič — porozprávajte sa.', confirmForget: 'Naozaj má Lexi zabudnúť všetko, čo si o tebe pamätá? Nedá sa to vrátiť.',
            forgotten: 'Lexi zabudla všetko.', wordsAdded: function (n) { return n ? ' Do sady „AI tútor“ ' + (n === 1 ? 'pribudlo' : n < 5 ? 'pribudli' : 'pribudlo') + ' ' + n + ' ' + skPlural(n, 'slovíčko', 'slovíčka', 'slovíčok') + '.' : ''; },
            noMic: 'Hlasový vstup tento prehliadač nevie — píš, prosím. Funguje v aktuálnom Chrome, Edge, Firefoxe aj Safari.',
            micDenied: 'Prístup k mikrofónu je zakázaný. Povoľ ho v nastaveniach prehliadača (ikona zámku vedľa adresy) a skús znova.',
            newSession: 'Nový rozhovor', level: 'Úroveň',
            speakNow: 'Počúvam — hovor po anglicky alebo po slovensky.', transcribing: 'Prepisujem…',
            notHeard: 'Nepočula som ťa. Skús to znova, trochu bližšie k mikrofónu.',
            continuousOn: 'Mikrofón ostáva zapnutý. Keď začneš hovoriť, Lexi stíchne. Najlepšie to ide so slúchadlami.',
            setFocus: function (name) { return 'Rozhovor nad sadou „' + name + '“ — Lexi do neho zapojí jej slovíčka.'; },
            help: 'Po slovensky',
        },
        en: {
            loading: 'Loading…', ready: "I'm ready. Shall we start?", listening: 'Listening…',
            thinking: 'Thinking…', speaking: 'Speaking…', yourTurn: 'Your turn.',
            unavailable: 'The AI tutor is not available.', ended: 'The conversation is saved to memory.',
            saving: 'Saving the conversation to memory…', netError: 'Connection error. Please try again.',
            correction: 'Correction', you: 'You', sessions: function (n) { return n === 1 ? '1 conversation in memory' : n + ' conversations in memory'; },
            left: function (s, d) { return s + ' messages left in this conversation · ' + d + ' today'; },
            nothingYet: 'Nothing yet — have a chat.', confirmForget: 'Really make Lexi forget everything about you? This cannot be undone.',
            forgotten: 'Lexi forgot everything.', wordsAdded: function (n) { return n ? ' ' + n + (n === 1 ? ' new word was' : ' new words were') + ' added to your “AI tútor” set.' : ''; },
            noMic: 'This browser cannot record your voice — please type. Works in current Chrome, Edge, Firefox and Safari.',
            micDenied: 'Microphone access is blocked. Allow it in your browser settings (lock icon next to the address) and try again.',
            newSession: 'New conversation', level: 'Level',
            speakNow: 'Listening — speak English or Slovak.', transcribing: 'Transcribing…',
            notHeard: "I didn't hear you. Try again, a bit closer to the microphone.",
            continuousOn: 'The microphone stays on. When you start talking, Lexi stops. Works best with headphones.',
            setFocus: function (name) { return 'Conversation over your set “' + name + '” — Lexi will weave in its words.'; },
            help: 'In Slovak',
        },
    };
    function t(key) { return (T[lang] || T.sk)[key]; }

    var $ = function (id) { return document.getElementById(id); };
    var avatar = $('tutorAvatar');
    var statusEl = $('tutorStatus');

    var state = {
        sessionId: null,
        languageFrom: 'en',
        languageTo: 'sk',
        level: 'A2',
        busy: false,
        messagesLeft: 0,
        messagesLeftToday: 0,
        // Sada, zo stránky ktorej používateľ prišiel (?set=), a slovíčka relácie nad ňou.
        setId: null,
        focus: null,
        // Zvyšuje sa pri každom začatí aj prerušení reči — dobehnutá stará reč
        // tak nezmení stav avatara ani nezapne mikrofón.
        speechTurn: 0,
    };
    var urlSet = parseInt(new URLSearchParams(window.location.search).get('set'), 10) || null;

    /* ── stav avatara ── */
    function setAvatar(mode, text) {
        avatar.setAttribute('data-state', mode);
        if (text) statusEl.textContent = text;
    }

    var reduceMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

    /* Nálada po odpovedi: oprava → sústredený výraz, pochvala → úsmev. `ms` = po
       koľkých milisekundách sa vráti na neutral (0 = ostane). */
    var PRAISE = /\b(great|well done|good job|nice|excellent|perfect|awesome|wonderful|fantastic|exactly|super|toll|prima|genau|sehr gut|très bien|parfait|bravo|génial|muy bien|perfecto|excelente|genial|ottimo|perfetto|esatto)\b/i;
    var moodTimer = null;
    function setMood(mood, ms) {
        clearTimeout(moodTimer);
        avatar.setAttribute('data-mood', mood);
        if (ms) moodTimer = setTimeout(function () { avatar.setAttribute('data-mood', 'neutral'); }, ms);
    }
    function moodFor(text, correction) {
        if (correction) return 'correcting';
        return PRAISE.test(text || '') ? 'happy' : 'neutral';
    }

    /* Žmurkanie v náhodných intervaloch, občas dvakrát — pravidelné pôsobí strojovo. */
    function blinkOnce() {
        avatar.classList.add('blink');
        setTimeout(function () { avatar.classList.remove('blink'); }, 120);
    }
    function scheduleBlink() {
        setTimeout(function () {
            if (!document.hidden) {
                blinkOnce();
                if (Math.random() < 0.2) setTimeout(blinkOnce, 260);
            }
            scheduleBlink();
        }, 2500 + Math.random() * 3500);
    }

    /* Pery: na začiatku každého slova sa rozvrhnú tvary úst podľa jeho
       samohlások (jedna skupina samohlások ≈ jedna slabika). Dĺžka slabiky sa
       priebežne dolaďuje podľa skutočného odstupu medzi slovami. */
    var lip = { timers: [], msPerSyllable: 210, lastAt: 0, lastSyllables: 0 };
    var VOWELS = /[aáàâäåeéèêëěiíìîïyýoóòôöőuúùûüůű]+/g;

    function mouthShapes(word) {
        return (word.toLowerCase().match(VOWELS) || ['e']).map(function (group) {
            var c = group.charAt(0);
            if ('aáàâäå'.indexOf(c) >= 0) return 'a';
            if ('oóòôöő'.indexOf(c) >= 0) return 'o';
            if ('uúùûüůű'.indexOf(c) >= 0) return 'u';
            return 'e';
        });
    }
    function clearLip() {
        lip.timers.forEach(clearTimeout);
        lip.timers = [];
    }
    function resetLip() {
        clearLip();
        lip.lastAt = 0;
        avatar.removeAttribute('data-lipsync');
        avatar.setAttribute('data-mouth', 'rest');
    }
    function onWord(event, text) {
        if (event.name && event.name !== 'word') return;
        var match = text.slice(event.charIndex || 0).match(/^[^\s.,!?;:"“”„()…–-]+/);
        if (!match) return;
        var shapes = mouthShapes(match[0]);
        var now = Date.now();
        if (lip.lastAt && lip.lastSyllables) {
            var perSyllable = (now - lip.lastAt) / lip.lastSyllables;
            // Odstup cez čiarku či bodku je pauza, nie rýchlosť reči — ten ignorujeme.
            if (perSyllable >= 100 && perSyllable <= 400) lip.msPerSyllable = lip.msPerSyllable * 0.6 + perSyllable * 0.4;
        }
        lip.lastAt = now;
        lip.lastSyllables = shapes.length;
        avatar.setAttribute('data-lipsync', '');
        clearLip();
        var step = lip.msPerSyllable;
        shapes.forEach(function (shape, i) {
            lip.timers.push(setTimeout(function () { avatar.setAttribute('data-mouth', shape); }, i * step));
        });
        lip.timers.push(setTimeout(function () { avatar.setAttribute('data-mouth', 'rest'); }, (shapes.length - 0.35) * step));
    }

    /* ── API ── */
    function api(path, options) {
        var opts = options || {};
        opts.headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {});
        opts.credentials = 'same-origin';
        return fetch(API + path, opts).then(function (res) {
            if (res.status === 401) { window.location.href = '/login'; throw new Error('401'); }
            return res.json().catch(function () { return {}; }).then(function (body) {
                if (!res.ok) {
                    var detail = body && body.detail;
                    if (Array.isArray(detail)) detail = detail.map(function (d) { return d.msg; }).join(', ');
                    var err = new Error(detail || t('netError'));
                    err.status = res.status;
                    throw err;
                }
                return body;
            });
        });
    }

    /* ── prepis rozhovoru ── */
    var chatLog = $('chatLog');

    /* Odpoveď tútora: prvý riadok „✔ …" = oprava, riadky „ⓘ …" = pomoc po
       slovensky. Rovnako ako `split_reply` na serveri (pre správy z histórie). */
    function splitReply(raw) {
        var lines = String(raw || '').split('\n');
        var correction = null;
        if (lines.length > 1 && lines[0].trim().indexOf('✔') === 0) correction = lines.shift().replace('✔', '').trim() || null;
        var isHelp = function (l) { return l.trim().indexOf('ⓘ') === 0; };
        var help = lines.filter(isHelp).map(function (l) { return l.replace('ⓘ', '').trim(); }).filter(Boolean).join(' ');
        var rest = lines.filter(function (l) { return !isHelp(l); }).join('\n').trim();
        if (!rest) return { reply: raw, correction: null, help: null };
        return { reply: rest, correction: correction, help: help || null };
    }

    function addBubble(role, text, correction, help, spokenLang) {
        if (correction) {
            var fix = document.createElement('div');
            fix.className = 'bubble-correction';
            var label = document.createElement('span');
            label.textContent = '✔ ' + t('correction') + ': ';
            fix.appendChild(label);
            fix.appendChild(document.createTextNode(correction));
            chatLog.appendChild(fix);
        }
        var bubble = document.createElement('div');
        bubble.className = 'bubble ' + (role === 'user' ? 'from-user' : 'from-tutor');
        var body = document.createElement('div');
        body.className = 'bubble-text';
        body.textContent = text;
        bubble.appendChild(body);
        // Hovoril po slovensky (podľa Whispera) — nech vidí, že to Lexi pochopila.
        if (role === 'user' && spokenLang && spokenLang !== state.languageFrom) {
            var tag = document.createElement('span');
            tag.className = 'bubble-lang';
            tag.textContent = spokenLang.toUpperCase();
            bubble.appendChild(tag);
        }
        if (role !== 'user' && window.LexiSpeech && LexiSpeech.available) {
            var replay = document.createElement('button');
            replay.type = 'button';
            replay.className = 'bubble-replay';
            replay.setAttribute('aria-label', '🔊');
            replay.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
            replay.addEventListener('click', function () { say(text, help); });
            bubble.appendChild(replay);
        }
        chatLog.appendChild(bubble);
        if (help) {
            var note = document.createElement('div');
            note.className = 'bubble-help';
            var label = document.createElement('span');
            label.textContent = 'ⓘ ' + t('help') + ': ';
            note.appendChild(label);
            note.appendChild(document.createTextNode(help));
            chatLog.appendChild(note);
        }
        chatLog.scrollTop = chatLog.scrollHeight;
        (chatLog.lastElementChild || bubble).scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    function addStoredMessage(message) {
        if (message.role === 'assistant') {
            var parts = splitReply(message.text);
            addBubble('assistant', parts.reply, parts.correction, parts.help);
            return;
        }
        addBubble(message.role, message.text);
    }

    function renderFocus() {
        var box = $('focusWords');
        box.innerHTML = '';
        box.hidden = !(state.focus && state.focus.words && state.focus.words.length);
        if (box.hidden) return;
        state.focus.words.forEach(function (w) {
            var chip = document.createElement('span');
            chip.className = 'focus-chip';
            chip.textContent = w.word;
            chip.title = w.translation;
            box.appendChild(chip);
        });
    }

    function updateLeft() {
        $('chatLeft').textContent = t('left')(state.messagesLeft, state.messagesLeftToday);
    }

    /* ── hlas von ── */
    function speakPart(text, locale) {
        var onBoundary = reduceMotion ? null : function (event) { onWord(event, text); };
        return LexiSpeech.speakAsync(text, locale, 0.95, onBoundary);
    }

    /* Prečíta odpoveď a po nej pomoc po slovensky (iným hlasom). Ak reč prerušíš
       (skočíš do nej), `speechTurn` sa zmení a zvyšok sa už nevykoná. */
    function say(text, help) {
        if (!window.LexiSpeech || !LexiSpeech.available || !text) return Promise.resolve();
        LexiSpeech.cancel();
        resetLip();
        var turn = ++state.speechTurn;
        setAvatar('speaking', t('speaking'));
        if (mic.phase === 'paused') mic.phase = 'watch';
        return speakPart(text, LexiSpeech.toLocale(state.languageFrom, 'en-US')).then(function () {
            if (turn !== state.speechTurn || !help) return;
            var nativeLocale = LexiSpeech.toLocale(state.languageTo, 'sk-SK');
            if (!LexiSpeech.hasVoiceFor(nativeLocale)) return;
            resetLip();
            return speakPart(help, nativeLocale);
        }).then(function () {
            if (turn !== state.speechTurn) return;
            resetLip();
            if (mic.phase === 'watch') mic.phase = 'paused';
            setAvatar('idle', t('yourTurn'));
        });
    }

    function continuous() { return $('handsFreeToggle').checked && canRecord; }

    function respond(text, correction, help) {
        addBubble('assistant', text, correction, help);
        var mood = moodFor(text, correction);
        setMood(mood);
        var settle = function () { if (mood !== 'neutral') setMood(mood, 3500); };
        var turn = state.speechTurn;
        var spoken = $('voiceToggle').checked ? say(text, help) : Promise.resolve();
        if (!$('voiceToggle').checked) setAvatar('idle', t('yourTurn'));
        return spoken.then(function () {
            settle();
            // Skočil do reči → už sa nahráva, netreba nič zapínať.
            if (mic.phase === 'armed' || mic.phase === 'speech') return;
            if (state.speechTurn !== turn + ($('voiceToggle').checked ? 1 : 0)) return;
            if (continuous() && state.sessionId && state.messagesLeft > 0) listen();
        });
    }

    /* ── hlas dnu: nahrávka → /transcribe (Whisper) ──
       Fázy mikrofónu: off (zatvorený), paused (otvorený, nepočúva — čaká sa na
       AI), armed (nahráva, čaká na začiatok reči), speech (hovoríš, čaká sa na
       ticho), watch (hovorí Lexi, sleduje sa, či do nej neskočíš). */
    var canRecord = !!(window.MediaRecorder && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    var VAD = {
        frameMs: 50,
        startMs: 150,        // toľko hlasitej reči za sebou = začal hovoriť
        endSilenceMs: 1100,  // toľko ticha po reči = dohovoril
        maxMs: 30000,        // najdlhšia nahrávka
        idleRestartMs: 15000, // nahrávka bez reči sa zahodí a začne nová (nech nerastie)
        bargeMs: 350,        // toľko hlasitej reči počas Lexi = skáčeš jej do reči
    };
    var mic = {
        phase: 'off', stream: null, ctx: null, analyser: null, buf: null, timer: 0,
        recorder: null, chunks: [], noise: 0.006, echo: 0, loudMs: 0, quietMs: 0,
        heard: false, startedAt: 0,
    };

    function showVoiceHint(text) {
        var hint = $('voiceHint');
        hint.textContent = text || '';
        hint.hidden = !text;
    }

    function setMicButton(on) { $('micBtn').setAttribute('aria-pressed', on ? 'true' : 'false'); }

    function openMic() {
        if (mic.stream) return Promise.resolve();
        return navigator.mediaDevices.getUserMedia({
            audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        }).then(function (stream) {
            mic.stream = stream;
            var AudioCtx = window.AudioContext || window.webkitAudioContext;
            mic.ctx = new AudioCtx();
            var source = mic.ctx.createMediaStreamSource(stream);
            mic.analyser = mic.ctx.createAnalyser();
            mic.analyser.fftSize = 1024;
            source.connect(mic.analyser);
            mic.buf = new Float32Array(mic.analyser.fftSize);
            mic.phase = 'paused';
            mic.timer = setInterval(tick, VAD.frameMs);
            showVoiceHint('');
        });
    }

    function closeMic() {
        clearInterval(mic.timer);
        if (mic.recorder && mic.recorder.state !== 'inactive') {
            mic.recorder.onstop = null;
            try { mic.recorder.stop(); } catch (e) {}
        }
        mic.recorder = null;
        if (mic.stream) mic.stream.getTracks().forEach(function (track) { track.stop(); });
        if (mic.ctx) { try { mic.ctx.close(); } catch (e) {} }
        mic.stream = mic.ctx = mic.analyser = null;
        mic.phase = 'off';
        setMicButton(false);
    }

    function level() {
        mic.analyser.getFloatTimeDomainData(mic.buf);
        var sum = 0;
        for (var i = 0; i < mic.buf.length; i++) sum += mic.buf[i] * mic.buf[i];
        return Math.sqrt(sum / mic.buf.length);
    }

    function tick() {
        if (!mic.analyser) return;
        var r = level();
        var speakThr = Math.max(0.012, mic.noise * 3);
        // Počas reči Lexi mikrofón počuje aj ju (z reproduktora) — prah na
        // skočenie do reči je preto vysoko nad jej ozvenou.
        var bargeThr = Math.max(0.04, mic.noise * 6, mic.echo * 2.5);
        if (r < speakThr && mic.phase !== 'watch') mic.noise = mic.noise * 0.97 + r * 0.03;
        var now = Date.now();

        if (mic.phase === 'armed') {
            mic.loudMs = r > speakThr ? mic.loudMs + VAD.frameMs : 0;
            if (mic.loudMs >= VAD.startMs) {
                mic.phase = 'speech';
                mic.heard = true;
                mic.quietMs = 0;
            } else if (now - mic.startedAt > VAD.idleRestartMs) {
                restartRecording();
            }
        } else if (mic.phase === 'speech') {
            mic.quietMs = r < speakThr ? mic.quietMs + VAD.frameMs : 0;
            if (mic.quietMs >= VAD.endSilenceMs || now - mic.startedAt > VAD.maxMs) finishRecording(true);
        } else if (mic.phase === 'watch') {
            if (r < bargeThr) mic.echo = mic.echo * 0.9 + r * 0.1;
            mic.loudMs = r > bargeThr ? mic.loudMs + VAD.frameMs : 0;
            if (mic.loudMs >= VAD.bargeMs) bargeIn();
        }
    }

    function pickMime() {
        var types = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4', 'audio/webm', 'audio/ogg'];
        for (var i = 0; i < types.length; i++) {
            if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(types[i])) return types[i];
        }
        return '';
    }

    function startRecording(alreadySpeaking) {
        var mime = pickMime();
        var recorder = mime ? new MediaRecorder(mic.stream, { mimeType: mime }) : new MediaRecorder(mic.stream);
        mic.recorder = recorder;
        mic.chunks = [];
        recorder.ondataavailable = function (e) { if (e.data && e.data.size) mic.chunks.push(e.data); };
        recorder.start();
        mic.startedAt = Date.now();
        mic.loudMs = mic.quietMs = 0;
        mic.heard = !!alreadySpeaking;
        mic.phase = alreadySpeaking ? 'speech' : 'armed';
        setMicButton(true);
        setAvatar('listening', t('speakNow'));
    }

    function restartRecording() {
        var old = mic.recorder;
        if (old) { old.onstop = null; try { old.stop(); } catch (e) {} }
        startRecording(false);
    }

    /* Dohovoril (alebo ťukol na mikrofón): nahrávka ide na prepis, ak v nej
       bola reč. `send=false` ju len zahodí. */
    function finishRecording(send) {
        var recorder = mic.recorder;
        var heard = mic.heard;
        mic.phase = mic.stream ? 'paused' : 'off';
        mic.recorder = null;
        setMicButton(false);
        if (!recorder || recorder.state === 'inactive') return;
        recorder.onstop = function () {
            var blob = new Blob(mic.chunks, { type: recorder.mimeType || 'audio/webm' });
            if (!continuous()) closeMic();
            if (send && heard && blob.size) transcribe(blob);
            else if (!state.busy) setAvatar('idle', t('yourTurn'));
        };
        try { recorder.stop(); } catch (e) {}
    }

    function bargeIn() {
        state.speechTurn++;
        if (window.LexiSpeech) LexiSpeech.cancel();
        resetLip();
        startRecording(true);
    }

    function transcribe(blob) {
        state.busy = true;
        setAvatar('thinking', t('transcribing'));
        api('/transcribe', { method: 'POST', body: blob, headers: { 'Content-Type': blob.type } }).then(function (body) {
            state.busy = false;
            var text = (body.text || '').trim();
            if (!text) {
                toast(t('notHeard'), 'error');
                if (continuous()) listen(); else setAvatar('idle', t('yourTurn'));
                return;
            }
            sendMessage(text, body.language);
        }).catch(function (err) {
            state.busy = false;
            setAvatar('idle', t('yourTurn'));
            toast(err.message, 'error');
        });
    }

    /* Začni počúvať (ťuknutie na mikrofón alebo po odpovedi v plynulom režime). */
    function listen() {
        if (!canRecord) { showVoiceHint(t('noMic')); return; }
        if (state.busy || !state.sessionId) return;
        if (mic.phase === 'armed' || mic.phase === 'speech') return;
        if (window.LexiSpeech) LexiSpeech.cancel();
        state.speechTurn++;
        resetLip();
        setMood('neutral');
        openMic().then(function () { startRecording(false); }).catch(function (err) {
            closeMic();
            $('handsFreeToggle').checked = false;
            var denied = err && (err.name === 'NotAllowedError' || err.name === 'SecurityError');
            showVoiceHint(denied ? t('micDenied') : t('noMic'));
            setAvatar('idle', t('yourTurn'));
        });
    }

    function stopListening() {
        if (mic.phase === 'speech') finishRecording(true);
        else if (mic.phase === 'armed') finishRecording(false);
    }

    /* ── akcie ── */
    function startSession() {
        if (state.busy) return;
        state.busy = true;
        $('startBtn').disabled = true;
        setAvatar('thinking', t('thinking'));
        // Prvá reč musí začať v ťuknutí používateľa (iOS) — „odomkneme" syntézu prázdnou vetou.
        if (window.LexiSpeech && LexiSpeech.available) { try { LexiSpeech.speak(' ', 'en-US'); } catch (e) {} }
        // Mikrofón (a AudioContext) treba otvoriť v ťuknutí — neskôr by ho prehliadač nemusel pustiť.
        if (continuous()) openMic().catch(function () { $('handsFreeToggle').checked = false; showVoiceHint(t('micDenied')); });

        api('/sessions', {
            method: 'POST',
            body: JSON.stringify({
                level: $('levelSelect').value, language_from: $('languageSelect').value, category_id: state.setId,
            }),
        }).then(function (body) {
            state.sessionId = body.session_id;
            state.languageFrom = body.language_from;
            state.level = body.level;
            state.messagesLeft = body.messages_left;
            state.messagesLeftToday = body.messages_left_today;
            state.focus = body.focus || null;
            chatLog.innerHTML = '';
            renderFocus();
            showChat();
            updateLeft();
            state.busy = false;
            return respond(body.reply);
        }).catch(function (err) {
            state.busy = false;
            setAvatar('idle', t('ready'));
            toast(err.message, 'error');
        }).then(function () { $('startBtn').disabled = false; });
    }

    /* `spokenLang` = jazyk, ktorý rozpoznal Whisper (pri písaní nič). */
    function sendMessage(text, spokenLang) {
        text = (text || '').trim();
        if (!text || state.busy || !state.sessionId) return;
        // Napísal správu, kým mikrofón počúval — nahrávka sa zahodí.
        if (mic.phase === 'armed' || mic.phase === 'speech') finishRecording(false);
        state.busy = true;
        $('sendBtn').disabled = true;
        $('messageInput').value = '';
        autosize();
        addBubble('user', text, null, null, spokenLang);
        setAvatar('thinking', t('thinking'));

        api('/sessions/' + state.sessionId + '/messages', {
            method: 'POST', body: JSON.stringify({ text: text }),
        }).then(function (body) {
            state.messagesLeft = body.messages_left;
            state.messagesLeftToday = body.messages_left_today;
            updateLeft();
            state.busy = false;
            return respond(body.reply, body.correction, body.help);
        }).catch(function (err) {
            state.busy = false;
            // Neodoslaná správa sa vráti do poľa, nech ju netreba písať znova.
            var last = chatLog.lastElementChild;
            if (last && last.classList.contains('from-user')) last.remove();
            $('messageInput').value = text;
            autosize();
            setAvatar('idle', t('yourTurn'));
            toast(err.message, 'error');
        }).then(function () { $('sendBtn').disabled = false; });
    }

    function endSession() {
        if (state.busy || !state.sessionId) return;
        state.busy = true;
        closeMic();
        state.speechTurn++;
        if (window.LexiSpeech) LexiSpeech.cancel();
        $('endBtn').disabled = true;
        setAvatar('thinking', t('saving'));

        api('/sessions/' + state.sessionId + '/end', { method: 'POST' }).then(function (body) {
            state.sessionId = null;
            state.busy = false;
            toast(t('ended') + t('wordsAdded')(body.words_added || 0), 'success');
            return loadState();
        }).catch(function (err) {
            state.busy = false;
            setAvatar('idle', t('yourTurn'));
            toast(err.message, 'error');
        }).then(function () { $('endBtn').disabled = false; });
    }

    function forgetEverything() {
        if (!window.confirm(t('confirmForget'))) return;
        closeMic();
        api('/memory', { method: 'DELETE' }).then(function () {
            toast(t('forgotten'), 'success');
            state.sessionId = null;
            chatLog.innerHTML = '';
            return loadState();
        }).catch(function (err) { toast(err.message, 'error'); });
    }

    /* ── zobrazenie ── */
    /* Výška hlavičky do CSS — rozhovor sa podľa nej zmestí presne na obrazovku. */
    function measureHeader() {
        var header = document.querySelector('.header');
        if (header) document.documentElement.style.setProperty('--header-h', header.offsetHeight + 'px');
    }

    function showChat() {
        $('setupCard').hidden = true;
        $('chatCard').hidden = false;
        measureHeader();
        document.querySelector('.tutor-page').classList.add('chatting');
        window.scrollTo(0, 0);
        // Bez nahrávania tlačidlo neschovávame potichu — povieme prečo.
        $('handsFreeWrap').hidden = !canRecord;
        $('micBtn').hidden = !canRecord;
        if (!canRecord) showVoiceHint(t('noMic'));
        $('continuousNote').hidden = !continuous();
        var meta = t('level') + ' ' + state.level + ' · ' + state.languageFrom.toUpperCase();
        if (state.focus && state.focus.name) meta += ' · ' + state.focus.name;
        $('tutorMeta').textContent = meta;
    }

    function showSetup() {
        document.querySelector('.tutor-page').classList.remove('chatting');
        $('chatCard').hidden = true;
        $('setupCard').hidden = false;
        $('setupFocus').hidden = !state.setId;
        if (state.setId) $('setupFocus').textContent = t('setFocus')(state.setName);
        // Nad sadou sa hovorí jazykom jej slovíčok — výber jazyka by klamal.
        $('languageSelect').disabled = !!state.setId;
        setAvatar('idle', t('ready'));
    }

    function fillList(el, text) {
        el.innerHTML = '';
        var items = (text || '').split('\n').map(function (l) { return l.replace(/^-\s*/, '').trim(); }).filter(Boolean);
        if (!items.length) {
            var li = document.createElement('li');
            li.className = 'muted';
            li.textContent = t('nothingYet');
            el.appendChild(li);
            return;
        }
        items.forEach(function (item) {
            var li = document.createElement('li');
            li.textContent = item;
            el.appendChild(li);
        });
    }

    function loadState() {
        setAvatar('thinking', t('loading'));
        return api('/state' + (urlSet ? '?set=' + urlSet : '')).then(function (body) {
            if (!body.available) {
                document.querySelector('.tutor-page').classList.remove('chatting');
                $('unavailableCard').hidden = false;
                $('unavailableReason').textContent = body.reason || t('unavailable');
                $('unavailablePlus').hidden = !/PLUS/.test(body.reason || '');
                $('setupCard').hidden = true;
                $('chatCard').hidden = true;
                $('memoryCard').hidden = true;
                setAvatar('idle', t('unavailable'));
                return;
            }
            var profile = body.profile;
            state.languageFrom = profile.language_from;
            state.languageTo = profile.language_to || 'sk';
            state.level = profile.level;
            // Cudzia či neexistujúca sada v adrese sa ticho ignoruje.
            state.setId = body.set ? body.set.id : null;
            state.setName = body.set ? body.set.name : '';
            state.messagesLeftToday = body.messages_left_today;
            $('levelSelect').value = profile.level;
            $('languageSelect').value = profile.language_from;

            $('memoryCard').hidden = false;
            fillList($('memoryFacts'), profile.facts);
            fillList($('memoryMistakes'), profile.mistakes);
            $('tutorMeta').textContent = profile.sessions_count ? t('sessions')(profile.sessions_count) : '';

            // Prišiel zo stránky inej sady, než nad ktorou beží rozbehnutý rozhovor →
            // ponúkneme nový nad touto sadou (starý sa pri štarte zhrnie do pamäte).
            var sessionFocusId = body.session && body.session.focus ? body.session.focus.category_id : null;
            var resume = body.session && (!state.setId || sessionFocusId === state.setId);
            if (resume) {
                state.sessionId = body.session.id;
                state.messagesLeft = body.session.messages_left;
                state.focus = body.session.focus || null;
                chatLog.innerHTML = '';
                body.session.messages.forEach(addStoredMessage);
                renderFocus();
                showChat();
                updateLeft();
                setAvatar('idle', t('yourTurn'));
            } else {
                showSetup();
            }
        }).catch(function (err) {
            setAvatar('idle', t('netError'));
            toast(err.message, 'error');
        });
    }

    /* ── drobnosti ── */
    function autosize() {
        var el = $('messageInput');
        el.style.height = 'auto';
        el.style.height = Math.min(el.scrollHeight, 140) + 'px';
    }

    var toastTimer = null;
    function toast(text, kind) {
        var box = $('toast');
        $('toastText').textContent = text;
        $('toastIcon').className = 'fa-solid ' + (kind === 'error' ? 'fa-triangle-exclamation' : 'fa-check-circle');
        box.className = 'show ' + (kind || '');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(function () { box.className = ''; }, 5000);
    }

    function setLang(next) {
        lang = next;
        try { localStorage.setItem('preferredLang', next); } catch (e) {}
        document.documentElement.lang = next;
        document.querySelectorAll('.lang-btn').forEach(function (b) { b.classList.toggle('active', b.dataset.lang === next); });
        document.querySelectorAll('[data-en]').forEach(function (el) {
            var value = el.getAttribute('data-' + next);
            if (value) el.textContent = value;
        });
        document.querySelectorAll('[data-en-label]').forEach(function (el) {
            var value = el.getAttribute('data-' + next + '-label');
            if (value) { el.title = value; el.setAttribute('aria-label', value); }
        });
        document.querySelectorAll('[data-en-placeholder]').forEach(function (el) {
            var value = el.getAttribute('data-' + next + '-placeholder');
            if (value) el.placeholder = value;
        });
        if (state.sessionId) updateLeft();
    }

    /* ── väzby ── */
    $('startBtn').addEventListener('click', startSession);
    $('endBtn').addEventListener('click', endSession);
    $('forgetBtn').addEventListener('click', forgetEverything);
    $('micBtn').addEventListener('click', function () {
        if (mic.phase === 'armed' || mic.phase === 'speech') stopListening(); else listen();
    });
    $('handsFreeToggle').addEventListener('change', function () {
        $('continuousNote').hidden = !this.checked;
        if (this.checked) {
            if (state.sessionId && !state.busy && mic.phase !== 'watch') listen();
            else if (canRecord) openMic().catch(function () { showVoiceHint(t('micDenied')); });
        } else {
            closeMic();
            if (!state.busy) setAvatar('idle', t('yourTurn'));
        }
    });
    window.addEventListener('resize', measureHeader);
    // Skrytá karta nemá počúvať — mikrofón sa zavrie (plynulý režim treba zapnúť znova).
    document.addEventListener('visibilitychange', function () {
        if (document.hidden && mic.phase !== 'off') {
            closeMic();
            $('handsFreeToggle').checked = false;
            $('continuousNote').hidden = true;
            if (!state.busy) setAvatar('idle', t('yourTurn'));
        }
    });
    $('composer').addEventListener('submit', function (e) {
        e.preventDefault();
        sendMessage($('messageInput').value);
    });
    $('messageInput').addEventListener('input', autosize);
    $('messageInput').addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(this.value); }
    });
    $('voiceToggle').addEventListener('change', function () {
        if (!this.checked && window.LexiSpeech) { LexiSpeech.cancel(); resetLip(); setAvatar('idle', t('yourTurn')); }
    });

    // Preferencie hlasu si pamätáme len v tomto prehliadači.
    try {
        var saved = JSON.parse(localStorage.getItem('wk_tutor_voice') || '{}');
        if (typeof saved.voice === 'boolean') $('voiceToggle').checked = saved.voice;
        if (typeof saved.handsFree === 'boolean') $('handsFreeToggle').checked = saved.handsFree;
    } catch (e) {}
    ['voiceToggle', 'handsFreeToggle'].forEach(function (id) {
        $(id).addEventListener('change', function () {
            try {
                localStorage.setItem('wk_tutor_voice', JSON.stringify({
                    voice: $('voiceToggle').checked, handsFree: $('handsFreeToggle').checked,
                }));
            } catch (e) {}
        });
    });

    setLang(lang);
    setMood('neutral');
    resetLip();
    if (!reduceMotion) scheduleBlink();
    loadState();
})();
