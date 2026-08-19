/* Presunute z profile.html — inline JS sa nedalo cachovat. */
let currentLang = localStorage.getItem('preferredLang') || 'sk';
    let _userId = null, _userEmail = null;          // pre Paddle checkout
    let _paddleConfig = null, _paddleReady = false;

    document.addEventListener('DOMContentLoaded', async () => {
        loadUserProfile();
        // Config (billing_enabled) musí byť načítaný pred renderom predplatného,
        // inak by kúpne tlačidlá na chvíľu blikli aj pri vypnutom predaji.
        await initPaddle();
        loadSubscription();
        setupLanguages();
        setupPasswordCheck();
        setupInquiryForm();

        // Návrat z checkoutu — webhook mohol prísť s krátkym oneskorením.
        if (new URLSearchParams(location.search).get('upgraded') === '1') {
            showMessage(currentLang === 'sk' ? 'Ďakujeme! Aktivujem predplatné…' : 'Thank you! Activating subscription…', 'success');
            setTimeout(loadSubscription, 2500);
            history.replaceState({}, '', '/profile');
        }
    });

    /* ── MOBILE MENU ── */
    const menuToggle = document.getElementById('menuToggle');
    const mobileNav  = document.getElementById('mobileNav');
    menuToggle.addEventListener('click', () => {
        mobileNav.classList.toggle('open');
        menuToggle.textContent = mobileNav.classList.contains('open') ? '✕' : '☰';
    });


    /* ── OFFLINE ── */
    function ensureOfflineBanner() {
        if (document.getElementById('offlineBanner')) return;
        const b = document.createElement('div'); b.id = 'offlineBanner';
        b.style.cssText = 'background:#f59e0b;color:#fff;text-align:center;padding:8px;font-weight:600;position:sticky;top:64px;z-index:9999;';
        b.textContent = '⚠️ Offline – zobrazujú sa uložené dáta';
        document.body.prepend(b);
    }

    async function loadUserProfile() {
        try {
            const res  = await fetch('/api/user');
            const user = await res.json();
            if (!res.ok || user.offline || user.error === 'offline') {
                ensureOfflineBanner();
                document.getElementById('userId').textContent    = '#' + (localStorage.getItem('wk_user_id') || '-');
                document.getElementById('userEmail').textContent = localStorage.getItem('wk_user_name') || 'Offline';
                document.getElementById('memberSince').textContent = '-';
                const isPlus = localStorage.getItem('wk_user_is_plus') === 'true';
                updatePlusBadge(isPlus); loadUserStats(isPlus); return;
            }
            localStorage.setItem('wk_user_id',     String(user.id || ''));
            localStorage.setItem('wk_user_name',   user.name || user.email || '');
            localStorage.setItem('wk_user_is_plus', String(!!user.is_plus));
            document.getElementById('userId').textContent    = '#' + user.id;
            document.getElementById('userEmail').textContent = user.email;
            _userId = user.id; _userEmail = user.email;
            if (user.created_at) {
                try {
                    const d = new Date(user.created_at.replace(' ','T').split('.')[0]);
                    const locale = currentLang === 'sk' ? 'sk-SK' : 'en-US';
                    document.getElementById('memberSince').textContent = isNaN(d) ? user.created_at.split(' ')[0] : d.toLocaleDateString(locale);
                } catch { document.getElementById('memberSince').textContent = user.created_at; }
            }
            if (user.dark_mode) { document.documentElement.setAttribute('data-theme','dark'); localStorage.setItem('darkMode','true'); }
            else { document.documentElement.removeAttribute('data-theme'); localStorage.setItem('darkMode','false'); }
            prefillInquiry(user.name || '', user.email || '');
            updatePlusBadge(user.is_plus);
            loadUserStats(user.is_plus);
        } catch {
            ensureOfflineBanner();
            document.getElementById('userId').textContent    = '#' + (localStorage.getItem('wk_user_id') || '-');
            document.getElementById('userEmail').textContent = localStorage.getItem('wk_user_name') || 'Offline';
            document.getElementById('memberSince').textContent = '-';
            const isPlus = localStorage.getItem('wk_user_is_plus') === 'true';
            updatePlusBadge(isPlus); loadUserStats(isPlus);
        }
    }

    function prefillInquiry(name, email) {
        const nameEl = document.getElementById('inquiryName');
        const emailEl = document.getElementById('inquiryEmail');
        if (nameEl && !nameEl.value) nameEl.value = name;
        if (emailEl) emailEl.value = email;
    }

    async function loadUserStats(isPlus) {
        const limit = isPlus ? '∞' : '5';
        try {
            const res   = await fetch('/api/user/stats');
            const stats = await res.json();
            if (stats && !stats.offline && stats.error !== 'offline') {
                localStorage.setItem('wk_cached_stats', JSON.stringify(stats));
                renderProfileStats(stats, limit);
            } else {
                const c = localStorage.getItem('wk_cached_stats');
                if (c) renderProfileStats(JSON.parse(c), limit);
            }
        } catch {
            const c = localStorage.getItem('wk_cached_stats');
            if (c) renderProfileStats(JSON.parse(c), limit);
        }
    }

    function renderProfileStats(stats, limit) {
        document.getElementById('categoriesUsage').textContent = `${stats.total_categories ?? '-'} / ${limit}`;
    }

    function updatePlusBadge(isPlus) {
        const b = document.getElementById('plusStatusBadge');
        b.textContent = isPlus ? 'PLUS ACTIVATED' : 'Standard';
        b.style.background = isPlus ? '#FFD700' : 'var(--muted)';
        b.style.color = isPlus ? '#000' : '#fff';
    }

    async function toggleDarkMode() {
        await fetch('/api/user/dark-mode', { method:'PATCH' });
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        if (!isDark) { document.documentElement.setAttribute('data-theme','dark'); localStorage.setItem('darkMode','true'); }
        else { document.documentElement.removeAttribute('data-theme'); localStorage.setItem('darkMode','false'); }
    }

    /* ── PREDPLATNÉ (Paddle) ── */
    async function initPaddle() {
        try {
            const res = await fetch('/api/v1/billing/config');
            if (!res.ok) return;
            _paddleConfig = await res.json();
            if (!_paddleConfig.configured || !window.Paddle) return;
            Paddle.Environment.set(_paddleConfig.environment === 'production' ? 'production' : 'sandbox');
            Paddle.Initialize({
                token: _paddleConfig.token,
                eventCallback: (ev) => {
                    if (ev && ev.name === 'checkout.completed') {
                        const sk = currentLang === 'sk';
                        showMessage(sk ? 'Ďakujeme! Aktivujem predplatné…' : 'Thank you! Activating subscription…', 'success');
                        setTimeout(loadSubscription, 2500);
                    }
                }
            });
            _paddleReady = true;
        } catch { /* platby ostanú neaktívne */ }
    }

    async function loadSubscription() {
        try {
            const res = await fetch('/api/v1/subscription');
            if (!res.ok) return;
            renderSubscription(await res.json());
        } catch { /* offline – ponecháme základný badge */ }
    }

    function renderSubscription(s) {
        const sk = currentLang === 'sk';
        const badge = document.getElementById('plusStatusBadge');
        const info  = document.getElementById('subInfo');
        const upBox = document.getElementById('upgradeBox');
        const soon  = document.getElementById('comingSoonBox');
        const manage = document.getElementById('manageBtn');
        const cancel = document.getElementById('cancelBtn');
        const billingOn = !!(_paddleConfig && _paddleConfig.billing_enabled);

        if (s.is_plus) {
            badge.textContent = 'PLUS';
            badge.style.background = '#FFD700'; badge.style.color = '#000';
            let txt = '';
            if (s.expires_at) {
                const d = new Date(s.expires_at).toLocaleDateString(sk ? 'sk-SK' : 'en-US');
                txt = s.cancelled_at
                    ? (sk ? `Zrušené – prístup do ${d}` : `Cancelled – access until ${d}`)
                    : (sk ? `Aktívne do ${d}` : `Active until ${d}`);
            }
            info.textContent = txt;
            upBox.style.display = 'none';
            soon.style.display = 'none';
            manage.style.display = 'block';
            // „Zrušiť" len ak ešte nie je zrušené
            const alreadyCancelled = s.cancelled_at || s.status === 'canceled';
            cancel.style.display = alreadyCancelled ? 'none' : 'block';
        } else {
            badge.textContent = 'Standard';
            badge.style.background = 'var(--muted)'; badge.style.color = '#fff';
            info.textContent = '';
            // Predaj vypnutý (BILLING_ENABLED=false) → „Už čoskoro" namiesto kúpy.
            upBox.style.display = billingOn ? 'block' : 'none';
            soon.style.display  = billingOn ? 'none' : 'block';
            manage.style.display = 'none';
            cancel.style.display = 'none';
        }
        loadUserStats(s.is_plus);
    }

    function startCheckout(plan, btn) {
        const sk = currentLang === 'sk';
        const priceId = _paddleConfig && _paddleConfig.prices ? _paddleConfig.prices[plan] : null;
        if (!_paddleReady || !priceId || !_paddleConfig.billing_enabled) {
            showMessage(sk ? 'Platby zatiaľ nie sú dostupné.' : 'Payments are not available yet.', 'error');
            return;
        }
        const dark = document.documentElement.getAttribute('data-theme') === 'dark';
        Paddle.Checkout.open({
            items: [{ priceId: priceId, quantity: 1 }],
            customer: _userEmail ? { email: _userEmail } : undefined,
            customData: { user_id: String(_userId || '') },
            settings: {
                displayMode: 'overlay',
                theme: dark ? 'dark' : 'light',
                locale: sk ? 'sk' : 'en',
                successUrl: location.origin + '/profile?upgraded=1'
            }
        });
    }

    async function openPortal(btn) {
        const sk = currentLang === 'sk';
        btn.disabled = true;
        try {
            const res = await fetch('/api/v1/billing/portal');
            const data = await res.json();
            if (res.ok && data.url) { window.open(data.url, '_blank', 'noopener'); btn.disabled = false; return; }
            showMessage(data.detail || (sk ? 'Nepodarilo sa otvoriť správu predplatného.' : 'Could not open portal.'), 'error');
        } catch { showMessage(sk ? 'Chyba spojenia.' : 'Connection error.', 'error'); }
        btn.disabled = false;
    }

    function cancelSubscription() {
        document.getElementById('cancelSubModal').style.display = 'flex';
    }
    function closeCancelSubModal() {
        document.getElementById('cancelSubModal').style.display = 'none';
    }

    async function confirmCancelSubscription() {
        closeCancelSubModal();
        const sk = currentLang === 'sk';
        const btn = document.getElementById('cancelBtn');
        const orig = btn.textContent;
        btn.disabled = true; btn.textContent = sk ? 'Ruším…' : 'Cancelling…';
        try {
            const res = await fetch('/api/v1/billing/cancel', { method: 'POST' });
            const data = await res.json();
            if (res.ok) {
                showMessage(sk ? 'Predplatné zrušené – prístup máš do konca obdobia.' : 'Subscription cancelled – access until period end.', 'success');
                loadSubscription();
                return;
            }
            showMessage(data.detail || (sk ? 'Nepodarilo sa zrušiť predplatné.' : 'Could not cancel subscription.'), 'error');
        } catch { showMessage(sk ? 'Chyba spojenia.' : 'Connection error.', 'error'); }
        btn.disabled = false; btn.textContent = orig;
    }

    function setupPasswordCheck() {
        document.getElementById('newPassword').addEventListener('input', function() {
            const v = this.value;
            document.getElementById('reqLength').classList.toggle('met', v.length >= 8);
            document.getElementById('reqUpper').classList.toggle('met',  /[A-Z]/.test(v));
            document.getElementById('reqLower').classList.toggle('met',  /[a-z]/.test(v));
            document.getElementById('reqNum').classList.toggle('met',    /[0-9]/.test(v));
        });
    }

    document.getElementById('changePasswordForm').addEventListener('submit', async e => {
        e.preventDefault();
        const currentPw = document.getElementById('currentPassword').value;
        const newPw     = document.getElementById('newPassword').value;
        try {
            const res  = await fetch('/api/user/change-password', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({ current_password:currentPw, new_password:newPw })
            });
            const data = await res.json();
            showMessage(res.ok ? (currentLang==='sk'?'Heslo zmenené!':'Password changed!') : (data.detail || 'Error'), res.ok ? 'success' : 'error');
            if (res.ok) e.target.reset();
        } catch { showMessage('Connection error.', 'error'); }
    });

    /* ── LANG ── */
    function setupLanguages() {
        document.querySelectorAll('.lang-btn').forEach(b => b.addEventListener('click', () => {
            currentLang = b.dataset.lang; setLang(currentLang);
        }));
        setLang(currentLang);
    }
    function setLang(lang) {
        localStorage.setItem('preferredLang', lang);
        document.querySelectorAll('.lang-btn').forEach(b => b.classList.toggle('active', b.dataset.lang === lang));
        document.querySelectorAll('[data-en]').forEach(el => { const t = el.getAttribute(`data-${lang}`); if(t) el.textContent = t; });
    }

    /* ── UTILS ── */
    function showMessage(text, type) {
        const m = document.getElementById('message');
        m.textContent = text;
        m.style.background = type === 'success' ? '#38a169' : 'var(--danger)';
        m.style.display = 'block';
        setTimeout(() => m.style.display = 'none', 3000);
    }

    function openDeleteModal()  { document.getElementById('deleteModal').style.display = 'flex'; }
    function closeDeleteModal() { document.getElementById('deleteModal').style.display = 'none'; }

    async function confirmDeleteAccount() {
        const res = await fetch('/api/user', { method:'DELETE' });
        if (res.ok) window.location.href = '/login';
    }

    function logout() { fetch('/api/v1/logout', {method:'POST'}).then(() => window.location.href = '/login'); }

    function setupInquiryForm() {
        const btn = document.getElementById('inquirySubmit');
        const statusEl = document.getElementById('inquiryStatus');
        if (!btn) return;
        btn.addEventListener('click', async () => {
            const msg = document.getElementById('inquiryMessage').value.trim();
            if (msg.length < 2) {
                statusEl.style.display = 'block';
                statusEl.style.color = 'var(--danger)';
                statusEl.textContent = currentLang === 'sk' ? 'Napíš nám prosím správu.' : 'Please write a message.';
                return;
            }
            btn.disabled = true;
            statusEl.style.display = 'block';
            statusEl.style.color = 'var(--muted)';
            statusEl.textContent = currentLang === 'sk' ? 'Odosielam…' : 'Sending…';
            try {
                const res = await fetch('/api/inquiry', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: document.getElementById('inquiryName').value.trim(),
                        email: document.getElementById('inquiryEmail').value.trim(),
                        message: msg,
                        page: window.location.pathname
                    })
                });
                if (res.ok) {
                    statusEl.style.color = '#38a169';
                    statusEl.textContent = currentLang === 'sk' ? 'Ďakujeme! Správa bola odoslaná.' : 'Thank you! Message sent.';
                    document.getElementById('inquiryMessage').value = '';
                } else {
                    statusEl.style.color = 'var(--danger)';
                    statusEl.textContent = currentLang === 'sk' ? 'Nepodarilo sa odoslať. Skús to znova.' : 'Failed to send. Please try again.';
                }
            } catch {
                statusEl.style.color = 'var(--danger)';
                statusEl.textContent = currentLang === 'sk' ? 'Chyba siete. Skús to znova.' : 'Network error. Please try again.';
            } finally {
                btn.disabled = false;
            }
        });
    }

    async function exportData() {
        const res  = await fetch('/api/user/export');
        const blob = await res.blob();
        const a    = document.createElement('a');
        a.href = URL.createObjectURL(blob); a.download = 'flashcards_data.json'; a.click();
    }
