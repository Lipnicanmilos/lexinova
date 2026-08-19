/* Presunute z admin.html — inline JS sa nedalo cachovat. */
const errBox = document.getElementById('errorBox');
    function showErr(msg){ errBox.textContent = msg; errBox.style.display='block'; }
    function clearErr(){ errBox.style.display='none'; }
    // Natvrdo sk-SK: admin je slovenský a bez locale vypisoval prehliadač
    // americký formát (10/11/2025, 11:32:47 PM) v slovenskom rozhraní.
    function fmtDate(iso){ return iso ? new Date(iso).toLocaleString('sk-SK') : '-'; }
    function fmtDay(iso){ return iso ? new Date(iso).toLocaleDateString('sk-SK') : '-'; }
    function subCell(u){
      if(!u.is_plus && !u.plus_status) return '<span class="muted">—</span>';
      const plan = u.plus_plan === 'annual' ? 'Ročne' : (u.plus_plan === 'monthly' ? 'Mesačne' : '');
      let html = plan ? `<div style="font-weight:800">${plan}</div>` : '';
      if(u.plus_cancelled_at) html += `<div class="muted" style="font-size:.8rem">zrušené · do ${fmtDay(u.plus_expires_at)}</div>`;
      else if(u.plus_expires_at) html += `<div class="muted" style="font-size:.8rem">do ${fmtDay(u.plus_expires_at)}</div>`;
      if(u.plus_status) html += `<div class="muted" style="font-size:.72rem">${esc(u.plus_status)}</div>`;
      return html || '<span class="muted">—</span>';
    }
    function esc(s){ return (s ?? '').toString().replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

    function switchTab(which){
      const map = {
        users:     ['tabUsers','tabUsersBtn'],
        payments:  ['tabPayments','tabPaymentsBtn'],
        inquiries: ['tabInquiries','tabInquiriesBtn'],
        logs:      ['tabLogs','tabLogsBtn'],
        jobs:      ['tabJobs','tabJobsBtn'],
      };
      for(const key in map){
        const [panel, btn] = map[key];
        const active = key === which;
        document.getElementById(panel).classList.toggle('hidden', !active);
        document.getElementById(btn).classList.toggle('active', active);
      }
      if(which === 'payments')  loadPayments();
      if(which === 'inquiries') loadInquiries();
      if(which === 'logs')      loadLogs();
      if(which === 'jobs')      loadJobs();
      if(which !== 'logs')      stopLogAuto();   // auto-obnova beží len na záložke Logy
    }

    /* ---------- JOBS (denné joby) ---------- */
    async function loadJobs(){
      clearErr();
      const tbody = document.getElementById('jobsTbody');
      try{
        const res = await fetch('/api/admin/jobs');
        const data = await res.json();
        if(!res.ok){ showErr(data.detail || 'Načítanie jobov zlyhalo'); return; }

        const jobs = Array.isArray(data.jobs) ? data.jobs : [];
        tbody.innerHTML = '';
        if(jobs.length === 0){
          tbody.innerHTML = `<tr><td colspan="6" class="muted empty">Žiadne registrované joby.</td></tr>`;
          return;
        }
        for(const j of jobs){
          const statusPill =
            j.last_status === 'ok'      ? `<span class="pill ok">OK</span>` :
            j.last_status === 'error'   ? `<span class="pill fail">Chyba</span>` :
            j.last_status === 'running' ? `<span class="pill warn">Beží…</span>` :
                                          `<span class="muted">zatiaľ nebežal</span>`;
          const hourCell = j.hour_override !== null
            ? `<b>${j.hour_override}:00</b> <span class="muted" style="font-size:.78rem">(override, default ${j.default_hour}:00)</span>`
            : `${j.effective_hour}:00 <span class="muted" style="font-size:.78rem">(default)</span>`;
          const lastRun = j.last_run_at ? fmtDate(j.last_run_at) : '—';
          const errCell = j.last_error
            ? `<span style="color:#c53030;font-size:.82rem;white-space:pre-wrap;">${esc(j.last_error)}</span>`
            : '<span class="muted">—</span>';
          tbody.insertAdjacentHTML('beforeend', `
            <tr id="jobrow-${esc(j.name)}">
              <td>
                <div style="font-weight:800">${esc(j.name)}</div>
                <div class="muted" style="font-size:.82rem">${esc(j.description)}</div>
              </td>
              <td id="jobhour-${esc(j.name)}">${hourCell}</td>
              <td>${lastRun}</td>
              <td>${statusPill}</td>
              <td style="max-width:280px;">${errCell}</td>
              <td>
                <div class="actions">
                  <button class="iconbtn plus" title="Spustiť teraz" onclick="runJob('${esc(j.name)}')"><i class="fa-solid fa-play"></i></button>
                  <button class="iconbtn edit" title="Prestaviť cieľovú hodinu" onclick="editJobHour('${esc(j.name)}', ${j.hour_override}, ${j.default_hour})"><i class="fa-solid fa-clock"></i></button>
                  <button class="iconbtn grant" title="História behov" onclick="toggleJobHistory('${esc(j.name)}')"><i class="fa-solid fa-clock-rotate-left"></i></button>
                </div>
              </td>
            </tr>
          `);
        }
      }catch(e){ showErr('Network error: '+(e?.message||e)); }
    }

    async function runJob(name){
      if(!confirm(`Spustiť job „${name}" teraz?\n\nBeh sa započíta ako dnešný (auto-beh dnes už nenaskočí).`)) return;
      clearErr();
      try{
        const res = await fetch(`/api/admin/jobs/${encodeURIComponent(name)}/run`, { method:'POST' });
        const data = await res.json().catch(()=>({}));
        if(!res.ok){ showErr(data.detail || 'Spustenie zlyhalo'); return; }
        if(data.status === 'error') showErr(`Job „${name}" zlyhal: ${data.error || 'neznáma chyba'}`);
        loadJobs();
      }catch(e){ showErr('Network error: '+(e?.message||e)); }
    }

    let _hourJob = null;   // job, ktorému sa práve nastavuje hodina

    function editJobHour(name, override, defaultHour){
      _hourJob = name;
      document.getElementById('hourJobName').textContent = name;
      document.getElementById('hourDefaultBtn').innerHTML =
        `<i class="fa-solid fa-rotate-left"></i>&nbsp;Default (${defaultHour}:00)`;

      const grid = document.getElementById('hourGrid');
      grid.innerHTML = '';
      const effective = override !== null ? override : defaultHour;
      for(let h = 0; h < 24; h++){
        const label = `${h}:00`.padStart(5, '0');
        const cls = 'hour-chip'
          + (h === effective ? ' selected' : '')
          + (h === defaultHour ? ' isdefault' : '');
        const title = h === defaultHour ? `default (${defaultHour}:00)` : label;
        grid.insertAdjacentHTML('beforeend',
          `<button class="${cls}" title="${title}" onclick="pickJobHour(${h})">${label}</button>`);
      }
      document.getElementById('hourOverlay').classList.add('open');
    }

    function closeHourPicker(){
      document.getElementById('hourOverlay').classList.remove('open');
      _hourJob = null;
    }

    async function pickJobHour(value){
      if(_hourJob === null) return;
      const name = _hourJob;
      clearErr();
      try{
        const res = await fetch(`/api/admin/jobs/${encodeURIComponent(name)}`, {
          method:'PATCH', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ run_after_hour: value })
        });
        const data = await res.json().catch(()=>({}));
        if(!res.ok){ showErr(data.detail || 'Uloženie zlyhalo'); return; }
        closeHourPicker();
        loadJobs();
      }catch(e){ showErr('Network error: '+(e?.message||e)); }
    }

    document.addEventListener('keydown', (e) => {
      if(e.key === 'Escape' && document.getElementById('hourOverlay').classList.contains('open')){
        closeHourPicker();
      }
    });

    async function toggleJobHistory(name){
      const histId = `jobhist-${name}`;
      const existing = document.getElementById(histId);
      if(existing){ existing.remove(); return; }   // druhý klik históriu skryje
      clearErr();
      try{
        const res = await fetch(`/api/admin/jobs/${encodeURIComponent(name)}/history?limit=20`);
        const data = await res.json();
        if(!res.ok){ showErr(data.detail || 'Načítanie histórie zlyhalo'); return; }

        const items = Array.isArray(data.history) ? data.history : [];
        const rows = items.length === 0
          ? `<tr><td colspan="4" class="muted">Zatiaľ žiadne zaznamenané behy.</td></tr>`
          : items.map(h => {
              const pill = h.status === 'ok' ? `<span class="pill ok">OK</span>` : `<span class="pill fail">Chyba</span>`;
              const trig = h.triggered_by === 'manual' ? 'manuálne' : 'auto';
              const err = h.error ? `<div style="color:#c53030;font-size:.8rem;white-space:pre-wrap;">${esc(h.error)}</div>` : '';
              return `<tr>
                <td>${fmtDate(h.started_at)}</td>
                <td>${fmtDate(h.finished_at)}</td>
                <td>${pill} <span class="muted" style="font-size:.78rem">(${trig})</span></td>
                <td>${err || '<span class="muted">—</span>'}</td>
              </tr>`;
            }).join('');

        const row = document.getElementById(`jobrow-${name}`);
        row.insertAdjacentHTML('afterend', `
          <tr id="${histId}">
            <td colspan="6" style="background:rgba(64,121,255,.04);">
              <div class="k" style="margin-bottom:.5rem;">História behov — ${esc(name)} (posledných ${items.length})</div>
              <table style="box-shadow:none;">
                <thead><tr><th>Začiatok</th><th>Koniec</th><th>Stav</th><th>Chyba</th></tr></thead>
                <tbody>${rows}</tbody>
              </table>
            </td>
          </tr>
        `);
      }catch(e){ showErr('Network error: '+(e?.message||e)); }
    }

    /* ---------- LOGS ---------- */
    let _logAutoTimer = null, _logSearchTimer = null;
    function debouncedLogs(){
      clearTimeout(_logSearchTimer);
      _logSearchTimer = setTimeout(loadLogs, 350);
    }
    async function loadLogs(){
      clearErr();
      const n = document.getElementById('logLines').value;
      const level = document.getElementById('logLevel').value;
      const q = document.getElementById('logSearch').value.trim();
      const view = document.getElementById('logView');
      try{
        const params = new URLSearchParams({ lines: n, level, q });
        const res = await fetch(`/api/admin/logs?${params}`);
        const data = await res.json();
        if(!res.ok){ showErr(data.detail || 'Načítanie logov zlyhalo'); return; }

        document.getElementById('logNote').textContent = data.note || '';
        const lines = Array.isArray(data.lines) ? data.lines : [];
        const filtered = data.filtered ? ' (filtrované)' : '';
        document.getElementById('logCount').textContent = `${lines.length} riadkov${filtered}`;
        view.textContent = lines.length ? lines.join('\n') : '(žiadne zodpovedajúce logy)';
        view.scrollTop = view.scrollHeight;   // scroll na najnovšie
      }catch(e){ showErr('Chyba spojenia pri načítaní logov.'); }
    }

    function toggleLogAuto(){
      if(document.getElementById('logAuto').checked){
        _logAutoTimer = setInterval(loadLogs, 10000);
      } else {
        stopLogAuto();
      }
    }
    function stopLogAuto(){
      if(_logAutoTimer){ clearInterval(_logAutoTimer); _logAutoTimer = null; }
      const cb = document.getElementById('logAuto');
      if(cb) cb.checked = false;
    }

    /* ---------- USERS ---------- */
    async function loadUsers(){
      clearErr();
      const q = document.getElementById('searchInput').value.trim();
      const plus = document.getElementById('plusFilter').value;
      try{
        const res = await fetch(`/api/admin/users?q=${encodeURIComponent(q)}&plus=${plus}`);
        const data = await res.json();
        if(!res.ok){ showErr(data.detail || 'Admin request failed'); return; }

        const s = data.stats || {};
        document.getElementById('statUsers').textContent = s.total_users ?? 0;
        document.getElementById('statPlus').textContent  = s.total_plus ?? 0;
        document.getElementById('statStd').textContent   = s.total_standard ?? 0;
        document.getElementById('statWords').textContent = s.total_words_all_users ?? 0;
        document.getElementById('statCats').textContent  = s.total_categories_all ?? 0;
        document.getElementById('statNew7').textContent  = s.new_users_7d ?? 0;
        document.getElementById('statNew30').textContent = s.new_users_30d ?? 0;

        const users = Array.isArray(data.users) ? data.users : [];
        document.getElementById('resultCount').textContent = `${users.length} výsledkov`;

        const tbody = document.getElementById('usersTbody');
        tbody.innerHTML = '';
        if(users.length === 0){
          tbody.innerHTML = `<tr><td colspan="8" class="muted empty">Žiadni používatelia.</td></tr>`;
          return;
        }

        for(const u of users){
          const plusPill = u.is_plus
            ? `<span class="pill plus"><i class="fa-solid fa-crown"></i> PLUS</span>`
            : `<span class="pill std">Standard</span>`;
          const nameLine = u.name ? `<div class="muted" style="font-size:.85rem">${esc(u.name)}</div>` : '';
          const revokeBtn = (u.is_plus || u.plus_status)
            ? `<button class="iconbtn revoke" title="Zrušiť PLUS (teraz)" onclick="revokePlus(${u.id}, '${esc(u.email)}')"><i class="fa-solid fa-ban"></i></button>`
            : '';
          tbody.insertAdjacentHTML('beforeend', `
            <tr>
              <td><div style="font-weight:800">${esc(u.email)}</div>${nameLine}</td>
              <td>${plusPill}</td>
              <td>${subCell(u)}</td>
              <td>${fmtDate(u.created_at)}</td>
              <td>${fmtDate(u.last_login)}</td>
              <td style="font-weight:900">${u.categories_count ?? 0}</td>
              <td style="font-weight:900">${u.words_count ?? 0}</td>
              <td>
                <div class="actions">
                  <button class="iconbtn plus" title="Prepnúť Plus" onclick="togglePlus(${u.id}, ${u.is_plus})"><i class="fa-solid fa-wand-magic-sparkles"></i></button>
                  <button class="iconbtn grant" title="Grant PLUS (+/− dni)" onclick="grantPlus(${u.id}, '${esc(u.email)}')"><i class="fa-solid fa-calendar-plus"></i></button>
                  ${revokeBtn}
                  <button class="iconbtn edit" title="Upraviť email" onclick="editEmail(${u.id}, '${esc(u.email)}')"><i class="fa-solid fa-pen"></i></button>
                  <button class="iconbtn del" title="Zmazať" onclick="deleteUser(${u.id}, '${esc(u.email)}', ${u.words_count ?? 0}, ${u.categories_count ?? 0})"><i class="fa-solid fa-trash"></i></button>
                </div>
              </td>
            </tr>
          `);
        }
      }catch(e){ showErr('Network error: ' + (e?.message || e)); }
    }

    let searchTimer;
    function debouncedSearch(){ clearTimeout(searchTimer); searchTimer = setTimeout(loadUsers, 300); }

    async function togglePlus(userId, currentIsPlus){
      clearErr();
      try{
        const res = await fetch(`/api/admin/users/${userId}`, {
          method:'PATCH', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ is_plus: !currentIsPlus })
        });
        const data = await res.json().catch(()=>({}));
        if(!res.ok){ showErr(data.detail || 'Update failed'); return; }
        loadUsers();
      }catch(e){ showErr('Network error: '+(e?.message||e)); }
    }

    async function grantPlus(userId, email){
      const input = prompt(`Grant PLUS pre ${email}\n\nO koľko dní upraviť?  (+predĺži, −skráti)\nAk ešte platí, pripočíta sa k zostatku.`, '30');
      if(input === null) return;
      const days = parseInt(input, 10);
      if(!Number.isFinite(days) || days === 0 || Math.abs(days) > 3650){ showErr('Zadaj počet dní −3650 až 3650 (≠ 0).'); return; }
      clearErr();
      try{
        const res = await fetch(`/api/admin/users/${userId}/grant-plus`, {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ days })
        });
        const data = await res.json().catch(()=>({}));
        if(!res.ok){ showErr(data.detail || 'Grant zlyhal'); return; }
        loadUsers();
      }catch(e){ showErr('Network error: '+(e?.message||e)); }
    }

    async function revokePlus(userId, email){
      if(!confirm(`Zrušiť PLUS pre ${email} teraz?\n\nPrístup sa okamžite ukončí.`)) return;
      clearErr();
      try{
        const res = await fetch(`/api/admin/users/${userId}/revoke-plus`, { method:'POST' });
        const data = await res.json().catch(()=>({}));
        if(!res.ok){ showErr(data.detail || 'Zrušenie zlyhalo'); return; }
        loadUsers();
      }catch(e){ showErr('Network error: '+(e?.message||e)); }
    }

    async function editEmail(userId, currentEmail){
      const next = prompt('Nový email:', currentEmail);
      if(next === null) return;
      const trimmed = next.trim();
      if(!trimmed || trimmed === currentEmail) return;
      clearErr();
      try{
        const res = await fetch(`/api/admin/users/${userId}`, {
          method:'PATCH', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ email: trimmed })
        });
        const data = await res.json().catch(()=>({}));
        if(!res.ok){ showErr(data.detail || 'Update failed'); return; }
        loadUsers();
      }catch(e){ showErr('Network error: '+(e?.message||e)); }
    }

    async function deleteUser(userId, email, words, cats){
      if(!confirm(`Naozaj zmazať používateľa ${email}?\n\nNenávratne sa zmaže: ${words} slov a ${cats} kategórií.`)) return;
      clearErr();
      try{
        const res = await fetch(`/api/admin/users/${userId}`, { method:'DELETE' });
        const data = await res.json().catch(()=>({}));
        if(!res.ok){ showErr(data.detail || 'Delete failed'); return; }
        loadUsers();
      }catch(e){ showErr('Network error: '+(e?.message||e)); }
    }

    /* ---------- PAYMENTS ---------- */
    async function loadPayments(){
      clearErr();
      try{
        const res = await fetch('/api/admin/payments');
        const data = await res.json();
        if(!res.ok){ showErr(data.detail || 'Payments request failed'); return; }

        // Predplatné + MRR sú dostupné vždy (aj bez tabuľky payments).
        const sub = data.subscriptions || {};
        document.getElementById('paySubs').textContent = sub.active_subscriptions ?? 0;
        document.getElementById('payMrr').textContent  = `€${(sub.mrr ?? 0).toFixed(2)}`;
        document.getElementById('payArr').textContent  = `€${(sub.arr ?? 0).toFixed(2)}`;
        document.getElementById('paySubsBreakdown').textContent =
          `${sub.monthly_active ?? 0} / ${sub.annual_active ?? 0}`;

        const disabled = document.getElementById('paymentsDisabled');
        const content = document.getElementById('paymentsContent');
        if(!data.enabled){
          disabled.classList.remove('hidden');
          content.classList.add('hidden');
          return;
        }
        disabled.classList.add('hidden');
        content.classList.remove('hidden');

        const s = data.stats || {};
        document.getElementById('payRevenue').textContent   = `€${(s.total_revenue ?? 0).toFixed(2)}`;
        document.getElementById('payRev30').textContent     = `€${(s.revenue_30d ?? 0).toFixed(2)}`;
        document.getElementById('paySucceeded').textContent = s.succeeded_count ?? 0;
        document.getElementById('payRefunded').textContent  =
          `${s.refunded_count ?? 0} (€${(s.refunded_amount ?? 0).toFixed(2)})`;

        const tbody = document.getElementById('paymentsTbody');
        tbody.innerHTML = '';
        const payments = Array.isArray(data.payments) ? data.payments : [];
        if(payments.length === 0){
          tbody.innerHTML = `<tr><td colspan="6" class="muted empty">Zatiaľ žiadne platby.</td></tr>`;
          return;
        }
        for(const p of payments){
          const statusPill =
            p.status === 'succeeded'      ? `<span class="pill ok">Uhradené</span>` :
            p.status === 'pending'        ? `<span class="pill warn">Čaká</span>` :
            p.status === 'refunded'       ? `<span class="pill fail">Refundované</span>` :
            p.status === 'refund_pending' ? `<span class="pill warn">Refund čaká</span>` :
            p.status === 'chargeback'     ? `<span class="pill fail">Chargeback</span>` :
                                            `<span class="pill fail">${esc(p.status)}</span>`;
          tbody.insertAdjacentHTML('beforeend', `
            <tr>
              <td>${fmtDate(p.created_at)}</td>
              <td style="font-weight:800">${esc(p.email)}</td>
              <td style="font-weight:900">${(p.amount ?? 0).toFixed(2)} ${esc(p.currency || 'EUR')}</td>
              <td>${statusPill}</td>
              <td>${esc(p.provider)}</td>
              <td class="muted">${esc(p.description)}</td>
            </tr>
          `);
        }
      }catch(e){ showErr('Network error: '+(e?.message||e)); }
    }

    /* ---------- INQUIRIES (DOTAZY) ---------- */
    let inquirySearchTimer;
    function debouncedInquiry(){ clearTimeout(inquirySearchTimer); inquirySearchTimer = setTimeout(loadInquiries, 250); }

    async function loadInquiries(){
      clearErr();
      try{
        const res = await fetch('/api/admin/inquiries');
        const data = await res.json();
        if(!res.ok){ showErr(data.detail || 'Inquiries request failed'); return; }

        const s = data.stats || {};
        document.getElementById('inqTotal').textContent  = s.total ?? 0;
        document.getElementById('inqUnread').textContent = s.unread ?? 0;
        updateInquiryBadge(s.unread ?? 0);

        const tbody = document.getElementById('inquiriesTbody');
        tbody.innerHTML = '';

        let items = Array.isArray(data.inquiries) ? data.inquiries : [];

        // Filter prečítané / neprečítané
        const filter = document.getElementById('inqFilter').value;
        if(filter === 'unread') items = items.filter(q => !q.is_read);
        else if(filter === 'read') items = items.filter(q => q.is_read);

        // Hľadanie v mene / e-maile / správe
        const term = (document.getElementById('inqSearch').value || '').trim().toLowerCase();
        if(term){
          items = items.filter(q =>
            (q.name || '').toLowerCase().includes(term) ||
            (q.email || '').toLowerCase().includes(term) ||
            (q.message || '').toLowerCase().includes(term)
          );
        }

        document.getElementById('inqResultCount').textContent =
          `${items.length} ${items.length === 1 ? 'dotaz' : (items.length >= 2 && items.length <= 4 ? 'dotazy' : 'dotazov')}`;

        if(items.length === 0){
          tbody.innerHTML = `<tr><td colspan="6" class="muted empty">Žiadne dotazy pre tento filter.</td></tr>`;
          return;
        }
        for(const q of items){
          const mailLink = q.email
            ? `<a href="mailto:${esc(q.email)}" style="color:#4079ff;font-weight:700">${esc(q.email)}</a>`
            : '<span class="muted">—</span>';
          const readPill = q.is_read
            ? `<span class="pill ok">Prečítané</span>`
            : `<span class="pill warn">Nové</span>`;
          tbody.insertAdjacentHTML('beforeend', `
            <tr style="${q.is_read ? '' : 'font-weight:600;'}">
              <td>${fmtDate(q.created_at)}<br>${readPill}</td>
              <td>${esc(q.name) || '<span class="muted">—</span>'}</td>
              <td>${mailLink}</td>
              <td style="max-width:340px;white-space:pre-wrap;">${esc(q.message)}</td>
              <td class="muted">${esc(q.page) || '—'}</td>
              <td>
                <button class="btn" onclick="toggleInquiry(${q.id})">${q.is_read ? 'Označiť nové' : 'Prečítané'}</button>
                <button class="btn danger" onclick="deleteInquiry(${q.id})">Zmazať</button>
              </td>
            </tr>
          `);
        }
      }catch(e){ showErr('Network error: '+(e?.message||e)); }
    }

    async function toggleInquiry(id){
      try{
        const res = await fetch(`/api/admin/inquiries/${id}`, { method:'PATCH' });
        if(!res.ok){ const d = await res.json().catch(()=>({})); showErr(d.detail||'Update failed'); return; }
        loadInquiries();
      }catch(e){ showErr('Network error: '+(e?.message||e)); }
    }

    async function deleteInquiry(id){
      if(!confirm('Naozaj zmazať tento dotaz?')) return;
      try{
        const res = await fetch(`/api/admin/inquiries/${id}`, { method:'DELETE' });
        if(!res.ok){ const d = await res.json().catch(()=>({})); showErr(d.detail||'Delete failed'); return; }
        loadInquiries();
      }catch(e){ showErr('Network error: '+(e?.message||e)); }
    }

    function updateInquiryBadge(unread){
      const b = document.getElementById('inqBadge');
      if(!b) return;
      b.textContent = unread > 0 ? `(${unread})` : '';
      b.style.color = unread > 0 ? '#dc2626' : '';
      b.style.fontWeight = unread > 0 ? '900' : '';
    }

    async function refreshInquiryBadge(){
      try{
        const res = await fetch('/api/admin/inquiries');
        if(!res.ok) return;
        const data = await res.json();
        updateInquiryBadge(data?.stats?.unread ?? 0);
      }catch(e){ /* ticho */ }
    }

    function refreshAll(){
      loadUsers();
      if(!document.getElementById('tabPayments').classList.contains('hidden')) loadPayments();
      if(!document.getElementById('tabInquiries').classList.contains('hidden')) loadInquiries();
      if(!document.getElementById('tabLogs').classList.contains('hidden')) loadLogs();
      if(!document.getElementById('tabJobs').classList.contains('hidden')) loadJobs();
    }

    loadUsers();
    refreshInquiryBadge();
