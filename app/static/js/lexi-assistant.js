/* Lexi na nástenke: pokyn hlasom alebo písaním → akcia appky.

   POST /api/v1/assistant/command povie, čo používateľ chce:
   - create_set → návrh cez /categories/ai-preview (rovnaký ako „AI z textu");
     do účtu ide cez /ai-save až po potvrdení (tlačidlo alebo „áno"),
   - practice → test zo sady, talk → rozhovor s Lexi (aj nad sadou),
   - clarify → Lexi sa dopýta.

   Hlas: jednorazová nahrávka — ticho po vete ju ukončí — a prepis cez
   /api/v1/tutor/transcribe (Whisper sám pozná slovenčinu aj angličtinu).
   Lexi odpovedá nahlas jazykom rozhrania. */
(function () {
    'use strict';

    var panel = document.getElementById('lexiPanel');
    if (!panel) return;

    var $ = function (id) { return document.getElementById(id); };
    var avatar = $('lexiAvatar');
    function uiLang() { try { return localStorage.getItem('preferredLang') === 'en' ? 'en' : 'sk'; } catch (e) { return 'sk'; } }

    var T = {
        sk: {
            hello: 'Ahoj! Čo dnes spravíme?', thinking: 'Premýšľam…', listening: 'Počúvam…',
            transcribing: 'Prepisujem…', preparing: 'Pripravujem návrh sady…', saving: 'Ukladám sadu…',
            proposal: function (name, n) { return 'Tu je návrh: „' + name + '“, ' + n + ' ' + (n >= 2 && n <= 4 ? 'slovíčka' : 'slovíčok') + '. Mám ju uložiť?'; },
            words: function (n) { return n + ' ' + (n === 1 ? 'slovíčko' : n >= 2 && n <= 4 ? 'slovíčka' : 'slovíčok'); },
            saved: 'Hotovo, sada je uložená. Otváram ju.', cancelled: 'Dobre, nič som neuložila. Čo spravíme?',
            notHeard: 'Nepočula som ťa. Skús to znova.', noMic: 'Hlasový vstup tento prehliadač nevie — napíš mi, prosím.',
            micDenied: 'Mikrofón je zakázaný. Povoľ ho v nastaveniach prehliadača, alebo mi napíš.',
            error: 'Niečo sa pokazilo. Skús to prosím znova.', placeholder: 'Povedz alebo napíš, čo chceš…',
        },
        en: {
            hello: 'Hi! What shall we do today?', thinking: 'Thinking…', listening: 'Listening…',
            transcribing: 'Transcribing…', preparing: 'Preparing a set…', saving: 'Saving the set…',
            proposal: function (name, n) { return 'Here is a draft: “' + name + '”, ' + n + ' words. Shall I save it?'; },
            words: function (n) { return n === 1 ? '1 word' : n + ' words'; },
            saved: 'Done, the set is saved. Opening it.', cancelled: "OK, I didn't save anything. What next?",
            notHeard: "I didn't hear you. Please try again.", noMic: 'This browser cannot record your voice — please type.',
            micDenied: 'The microphone is blocked. Allow it in your browser settings, or type to me.',
            error: 'Something went wrong. Please try again.', placeholder: 'Say or type what you want…',
        },
    };
    function t(key) { return T[uiLang()][key]; }

    // Krátke „áno / nie", keď čaká návrh sady na potvrdenie.
    var YES = /^(áno|ano|hej|jasné|jasne|ok|okej|uložiť|ulož|uloz|ulozit|super|dobre|môže|moze|yes|yeah|yep|sure|save|do it|go ahead)\b/i;
    var NO = /^(nie|ne|zruš|zrus|zrušiť|zrusit|netreba|no|nope|cancel|stop)\b/i;

    var state = { busy: false, pending: null };

    /* ── avatar a reč ── */
    function setAvatar(mode) { avatar.setAttribute('data-state', mode); }

    function show(text) { $('lexiSay').textContent = text; }

    /* Povie text nahlas (ak to zariadenie vie) a vráti promise, ktorý dobehne s koncom reči. */
    function say(text) {
        show(text);
        if (!window.LexiSpeech || !LexiSpeech.available || !text) { setAvatar('idle'); return Promise.resolve(); }
        LexiSpeech.cancel();
        setAvatar('speaking');
        return LexiSpeech.speakAsync(text, uiLang() === 'en' ? 'en-US' : 'sk-SK', 1).then(function () { setAvatar('idle'); });
    }

    function blinkLater() {
        setTimeout(function () {
            if (!document.hidden) {
                avatar.classList.add('blink');
                setTimeout(function () { avatar.classList.remove('blink'); }, 120);
            }
            blinkLater();
        }, 2500 + Math.random() * 3500);
    }

    function post(url, body) {
        return fetch(url, {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        }).then(function (res) {
            return res.json().catch(function () { return {}; }).then(function (data) {
                if (!res.ok) {
                    var detail = data && data.detail;
                    if (Array.isArray(detail)) detail = detail.map(function (d) { return d.msg; }).join(', ');
                    throw new Error(detail || t('error'));
                }
                return data;
            });
        });
    }

    function setBusy(on) {
        state.busy = on;
        $('lexiSend').disabled = on;
        $('lexiMic').disabled = on && mic.phase === 'off';
    }

    function fail(err) {
        setBusy(false);
        setAvatar('idle');
        say((err && err.message) || t('error'));
    }

    /* ── pokyn ── */
    function handle(text) {
        text = (text || '').trim();
        if (!text || state.busy) return;
        $('lexiText').value = '';
        if (state.pending) {
            if (YES.test(text)) { saveProposal(); return; }
            if (NO.test(text)) { cancelProposal(); return; }
            hideProposal(); // nový pokyn namiesto potvrdenia — návrh zahodíme
        }
        setBusy(true);
        setAvatar('thinking');
        show(t('thinking'));
        post('/api/v1/assistant/command', { text: text, ui_lang: uiLang() }).then(function (cmd) {
            if (cmd.action === 'create_set') return prepareSet(cmd);
            setBusy(false);
            if ((cmd.action === 'practice' || cmd.action === 'talk') && cmd.url) {
                // Presmerovanie po dohovorení, najneskôr o 4 s (keby reč nedobehla).
                var go = function () { window.location.href = cmd.url; };
                setTimeout(go, 4000);
                return say(cmd.reply || '…').then(go);
            }
            return say(cmd.reply || t('hello'));
        }).catch(fail);
    }

    function prepareSet(cmd) {
        say(cmd.reply || t('preparing'));
        setAvatar('thinking');
        return post('/api/v1/categories/ai-preview', {
            prompt: cmd.topic, count: cmd.count,
            language_from: cmd.language_from, language_to: cmd.language_to,
        }).then(function (data) {
            setBusy(false);
            state.pending = { data: data, language_from: cmd.language_from, language_to: cmd.language_to };
            renderProposal(data);
            return say(t('proposal')(data.category_name, (data.words || []).length));
        });
    }

    function renderProposal(data) {
        var words = data.words || [];
        var name = $('lexiProposalName');
        name.textContent = data.category_name + ' ';
        var count = document.createElement('span');
        count.textContent = '· ' + t('words')(words.length) + ' · ' +
            (state.pending.language_from || '').toUpperCase() + ' → ' + (state.pending.language_to || '').toUpperCase();
        name.appendChild(count);
        var box = $('lexiProposalWords');
        box.innerHTML = '';
        words.slice(0, 10).forEach(function (w) {
            var chip = document.createElement('span');
            chip.textContent = w.original_word + ' — ' + w.translation;
            box.appendChild(chip);
        });
        if (words.length > 10) {
            var more = document.createElement('span');
            more.textContent = '+' + (words.length - 10);
            box.appendChild(more);
        }
        $('lexiProposal').hidden = false;
    }

    function hideProposal() {
        state.pending = null;
        $('lexiProposal').hidden = true;
    }

    function saveProposal() {
        var pending = state.pending;
        if (!pending || state.busy) return;
        setBusy(true);
        setAvatar('thinking');
        show(t('saving'));
        post('/api/v1/categories/ai-save', {
            category_name: pending.data.category_name,
            category_description: pending.data.category_description || null,
            language_from: pending.language_from, language_to: pending.language_to,
            words: pending.data.words,
        }).then(function (saved) {
            hideProposal();
            var go = function () { window.location.href = '/category/' + saved.category_id + '/words'; };
            setTimeout(go, 4000);
            return say(t('saved')).then(go);
        }).catch(fail);
    }

    function cancelProposal() {
        hideProposal();
        say(t('cancelled'));
    }

    /* ── hlas: jedna nahrávka, ticho po vete ju ukončí ── */
    var canRecord = !!(window.MediaRecorder && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    var VAD = { frameMs: 50, startMs: 150, endSilenceMs: 1100, maxMs: 20000, waitMs: 8000 };
    var mic = { phase: 'off', stream: null, ctx: null, analyser: null, buf: null, timer: 0, recorder: null,
                chunks: [], noise: 0.006, loudMs: 0, quietMs: 0, heard: false, startedAt: 0 };

    function closeMic() {
        clearInterval(mic.timer);
        if (mic.stream) mic.stream.getTracks().forEach(function (track) { track.stop(); });
        if (mic.ctx) { try { mic.ctx.close(); } catch (e) {} }
        mic.stream = mic.ctx = mic.analyser = null;
        mic.phase = 'off';
        $('lexiMic').setAttribute('aria-pressed', 'false');
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
        var thr = Math.max(0.012, mic.noise * 3);
        if (r < thr) mic.noise = mic.noise * 0.97 + r * 0.03;
        var elapsed = Date.now() - mic.startedAt;
        if (mic.phase === 'armed') {
            mic.loudMs = r > thr ? mic.loudMs + VAD.frameMs : 0;
            if (mic.loudMs >= VAD.startMs) { mic.phase = 'speech'; mic.heard = true; mic.quietMs = 0; }
            else if (elapsed > VAD.waitMs) stopRecording(false);
        } else if (mic.phase === 'speech') {
            mic.quietMs = r < thr ? mic.quietMs + VAD.frameMs : 0;
            if (mic.quietMs >= VAD.endSilenceMs || elapsed > VAD.maxMs) stopRecording(true);
        }
    }

    function pickMime() {
        var types = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4', 'audio/webm', 'audio/ogg'];
        for (var i = 0; i < types.length; i++) {
            if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(types[i])) return types[i];
        }
        return '';
    }

    function startRecording() {
        if (!canRecord) { show(t('noMic')); return; }
        if (state.busy || mic.phase !== 'off') return;
        if (window.LexiSpeech) LexiSpeech.cancel();
        navigator.mediaDevices.getUserMedia({
            audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        }).then(function (stream) {
            mic.stream = stream;
            var AudioCtx = window.AudioContext || window.webkitAudioContext;
            mic.ctx = new AudioCtx();
            mic.analyser = mic.ctx.createAnalyser();
            mic.analyser.fftSize = 1024;
            mic.ctx.createMediaStreamSource(stream).connect(mic.analyser);
            mic.buf = new Float32Array(mic.analyser.fftSize);
            var mime = pickMime();
            var recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
            mic.recorder = recorder;
            mic.chunks = [];
            recorder.ondataavailable = function (e) { if (e.data && e.data.size) mic.chunks.push(e.data); };
            recorder.start();
            mic.startedAt = Date.now();
            mic.loudMs = mic.quietMs = 0;
            mic.heard = false;
            mic.phase = 'armed';
            mic.timer = setInterval(tick, VAD.frameMs);
            $('lexiMic').setAttribute('aria-pressed', 'true');
            setAvatar('listening');
            show(t('listening'));
        }).catch(function (err) {
            closeMic();
            var denied = err && (err.name === 'NotAllowedError' || err.name === 'SecurityError');
            show(denied ? t('micDenied') : t('noMic'));
        });
    }

    function stopRecording(send) {
        var recorder = mic.recorder;
        var heard = mic.heard;
        mic.recorder = null;
        if (!recorder || recorder.state === 'inactive') { closeMic(); return; }
        recorder.onstop = function () {
            var blob = new Blob(mic.chunks, { type: recorder.mimeType || 'audio/webm' });
            closeMic();
            if (send && heard && blob.size) transcribe(blob);
            else { setAvatar('idle'); show(t('notHeard')); }
        };
        try { recorder.stop(); } catch (e) { closeMic(); }
    }

    function transcribe(blob) {
        setBusy(true);
        setAvatar('thinking');
        show(t('transcribing'));
        fetch('/api/v1/tutor/transcribe', {
            method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': blob.type }, body: blob,
        }).then(function (res) {
            return res.json().catch(function () { return {}; }).then(function (data) {
                if (!res.ok) throw new Error((data && data.detail) || t('error'));
                return data;
            });
        }).then(function (data) {
            setBusy(false);
            var text = (data.text || '').trim();
            if (!text) { setAvatar('idle'); show(t('notHeard')); return; }
            $('lexiText').value = text;
            handle(text);
        }).catch(fail);
    }

    /* ── väzby ── */
    $('lexiForm').addEventListener('submit', function (e) { e.preventDefault(); handle($('lexiText').value); });
    $('lexiMic').addEventListener('click', function () {
        if (mic.phase === 'speech') stopRecording(true);
        else if (mic.phase === 'armed') stopRecording(false);
        else startRecording();
    });
    $('lexiSave').addEventListener('click', saveProposal);
    $('lexiCancel').addEventListener('click', cancelProposal);
    document.addEventListener('visibilitychange', function () {
        if (document.hidden && mic.phase !== 'off') stopRecording(false);
    });
    document.querySelectorAll('.lang-btn').forEach(function (b) {
        b.addEventListener('click', function () {
            $('lexiText').placeholder = t('placeholder');
            if (!state.busy && !state.pending) show(t('hello'));
        });
    });

    if (!canRecord) $('lexiMic').hidden = true;
    $('lexiText').placeholder = t('placeholder');
    show(t('hello'));
    var reduceMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    if (!reduceMotion) blinkLater();
})();
