/* AI tútor s pamäťou (/tutor).

   Hlas: rozpoznávanie reči (Web Speech API, SpeechRecognition) → text → server
   → odpoveď → prečítanie nahlas (LexiSpeech). Oboje beží v prehliadači, zadarmo
   a bez posielania zvuku na náš server. Kde rozpoznávanie nie je (Firefox),
   mikrofón sa skryje a ostáva písanie.

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
            noMic: 'Tento prehliadač nevie rozpoznávať reč — píš, prosím. (Funguje v Chrome, Edge a Safari.)',
            micDenied: 'Prístup k mikrofónu je zakázaný. Povoľ ho v nastaveniach prehliadača.',
            newSession: 'Nový rozhovor', level: 'Úroveň',
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
            noMic: 'This browser cannot recognise speech — please type. (Works in Chrome, Edge and Safari.)',
            micDenied: 'Microphone access is blocked. Allow it in your browser settings.',
            newSession: 'New conversation', level: 'Level',
        },
    };
    function t(key) { return (T[lang] || T.sk)[key]; }

    var $ = function (id) { return document.getElementById(id); };
    var avatar = $('tutorAvatar');
    var statusEl = $('tutorStatus');

    var state = {
        sessionId: null,
        languageFrom: 'en',
        level: 'A2',
        busy: false,
        listening: false,
        messagesLeft: 0,
        messagesLeftToday: 0,
    };

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

    function addBubble(role, text, correction) {
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
        if (role !== 'user' && window.LexiSpeech && LexiSpeech.available) {
            var replay = document.createElement('button');
            replay.type = 'button';
            replay.className = 'bubble-replay';
            replay.setAttribute('aria-label', '🔊');
            replay.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
            replay.addEventListener('click', function () { say(text); });
            bubble.appendChild(replay);
        }
        chatLog.appendChild(bubble);
        chatLog.scrollTop = chatLog.scrollHeight;
        bubble.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    /* Správa z histórie môže mať opravu v prvom riadku („✔ …") — ako pri živej odpovedi. */
    function addStoredMessage(message) {
        if (message.role === 'assistant') {
            var lines = message.text.split('\n');
            if (lines[0].trim().indexOf('✔') === 0 && lines.length > 1) {
                addBubble('assistant', lines.slice(1).join('\n').trim(), lines[0].replace('✔', '').trim());
                return;
            }
        }
        addBubble(message.role, message.text);
    }

    function updateLeft() {
        $('chatLeft').textContent = t('left')(state.messagesLeft, state.messagesLeftToday);
    }

    /* ── hlas von ── */
    function say(text) {
        if (!window.LexiSpeech || !LexiSpeech.available || !text) return Promise.resolve();
        LexiSpeech.cancel();
        resetLip();
        setAvatar('speaking', t('speaking'));
        var locale = LexiSpeech.toLocale(state.languageFrom, 'en-US');
        var onBoundary = reduceMotion ? null : function (event) { onWord(event, text); };
        return LexiSpeech.speakAsync(text, locale, 0.95, onBoundary).then(function () {
            resetLip();
            setAvatar('idle', t('yourTurn'));
        });
    }

    function respond(text, correction) {
        addBubble('assistant', text, correction);
        var mood = moodFor(text, correction);
        setMood(mood);
        var settle = function () { if (mood !== 'neutral') setMood(mood, 3500); };
        if ($('voiceToggle').checked) {
            return say(text).then(function () {
                settle();
                if ($('handsFreeToggle').checked && state.sessionId && state.messagesLeft > 0) startListening();
            });
        }
        setAvatar('idle', t('yourTurn'));
        settle();
        return Promise.resolve();
    }

    /* ── hlas dnu ── */
    var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    var recognizer = null;

    function startListening() {
        if (!Recognition) { toast(t('noMic'), 'error'); return; }
        if (state.listening || state.busy) return;
        if (window.LexiSpeech) LexiSpeech.cancel();

        recognizer = new Recognition();
        recognizer.lang = window.LexiSpeech ? LexiSpeech.toLocale(state.languageFrom, 'en-US') : 'en-US';
        recognizer.interimResults = true;
        recognizer.continuous = false;
        recognizer.maxAlternatives = 1;

        var input = $('messageInput');
        var finalText = '';
        state.listening = true;
        $('micBtn').setAttribute('aria-pressed', 'true');
        setMood('neutral');
        setAvatar('listening', t('listening'));

        recognizer.onresult = function (event) {
            var interim = '';
            for (var i = event.resultIndex; i < event.results.length; i++) {
                var chunk = event.results[i][0].transcript;
                if (event.results[i].isFinal) finalText += chunk; else interim += chunk;
            }
            input.value = (finalText + interim).trim();
            autosize();
        };
        recognizer.onerror = function (event) {
            if (event.error === 'not-allowed' || event.error === 'service-not-allowed') toast(t('micDenied'), 'error');
        };
        recognizer.onend = function () {
            state.listening = false;
            $('micBtn').setAttribute('aria-pressed', 'false');
            var text = (finalText || input.value).trim();
            if (text) {
                sendMessage(text);
            } else if (!state.busy) {
                setAvatar('idle', t('yourTurn'));
            }
        };
        try { recognizer.start(); } catch (e) { state.listening = false; setAvatar('idle', t('yourTurn')); }
    }

    function stopListening() {
        if (recognizer && state.listening) { try { recognizer.stop(); } catch (e) {} }
    }

    /* ── akcie ── */
    function startSession() {
        if (state.busy) return;
        state.busy = true;
        $('startBtn').disabled = true;
        setAvatar('thinking', t('thinking'));
        // Prvá reč musí začať v ťuknutí používateľa (iOS) — „odomkneme" syntézu prázdnou vetou.
        if (window.LexiSpeech && LexiSpeech.available) { try { LexiSpeech.speak(' ', 'en-US'); } catch (e) {} }

        api('/sessions', {
            method: 'POST',
            body: JSON.stringify({ level: $('levelSelect').value, language_from: $('languageSelect').value }),
        }).then(function (body) {
            state.sessionId = body.session_id;
            state.languageFrom = body.language_from;
            state.level = body.level;
            state.messagesLeft = body.messages_left;
            state.messagesLeftToday = body.messages_left_today;
            chatLog.innerHTML = '';
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

    function sendMessage(text) {
        text = (text || '').trim();
        if (!text || state.busy || !state.sessionId) return;
        state.busy = true;
        $('sendBtn').disabled = true;
        $('messageInput').value = '';
        autosize();
        addBubble('user', text);
        setAvatar('thinking', t('thinking'));

        api('/sessions/' + state.sessionId + '/messages', {
            method: 'POST', body: JSON.stringify({ text: text }),
        }).then(function (body) {
            state.messagesLeft = body.messages_left;
            state.messagesLeftToday = body.messages_left_today;
            updateLeft();
            state.busy = false;
            return respond(body.reply, body.correction);
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
        stopListening();
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
        api('/memory', { method: 'DELETE' }).then(function () {
            toast(t('forgotten'), 'success');
            state.sessionId = null;
            chatLog.innerHTML = '';
            return loadState();
        }).catch(function (err) { toast(err.message, 'error'); });
    }

    /* ── zobrazenie ── */
    function showChat() {
        $('setupCard').hidden = true;
        $('chatCard').hidden = false;
        $('handsFreeWrap').hidden = !Recognition;
        $('micBtn').hidden = !Recognition;
        $('tutorMeta').textContent = t('level') + ' ' + state.level + ' · ' + state.languageFrom.toUpperCase();
    }

    function showSetup() {
        $('chatCard').hidden = true;
        $('setupCard').hidden = false;
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
        return api('/state').then(function (body) {
            if (!body.available) {
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
            state.level = profile.level;
            state.messagesLeftToday = body.messages_left_today;
            $('levelSelect').value = profile.level;
            $('languageSelect').value = profile.language_from;

            $('memoryCard').hidden = false;
            fillList($('memoryFacts'), profile.facts);
            fillList($('memoryMistakes'), profile.mistakes);
            $('tutorMeta').textContent = profile.sessions_count ? t('sessions')(profile.sessions_count) : '';

            if (body.session) {
                state.sessionId = body.session.id;
                state.messagesLeft = body.session.messages_left;
                chatLog.innerHTML = '';
                body.session.messages.forEach(addStoredMessage);
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

    window.logout = function () {
        fetch('/api/v1/logout', { method: 'POST' }).then(function () { window.location.href = '/login'; });
    };

    /* ── väzby ── */
    $('menuToggle').addEventListener('click', function () {
        var nav = $('mobileNav');
        nav.classList.toggle('open');
        this.textContent = nav.classList.contains('open') ? '✕' : '☰';
    });
    document.querySelectorAll('.lang-btn').forEach(function (b) {
        b.addEventListener('click', function () { setLang(b.dataset.lang); });
    });
    $('startBtn').addEventListener('click', startSession);
    $('endBtn').addEventListener('click', endSession);
    $('forgetBtn').addEventListener('click', forgetEverything);
    $('micBtn').addEventListener('click', function () {
        if (state.listening) stopListening(); else startListening();
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
