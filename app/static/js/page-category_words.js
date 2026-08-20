/* Presunute z category_words.html — inline JS sa nedalo cachovat. */
const currentCategoryId = PAGE_DATA.categoryId;
// Sada triedy: len na čítanie (slová patria učiteľovi)
const READONLY = PAGE_DATA.readonly;
let allWordsData = [];


// Štatistiky slovíčka sa vykresľujú z JS, takže data-en/data-sk atribúty
// na ne nesiahnu — texty musia byť tu.
const WORD_ACTIONS = {
  en: { edit: 'Edit word', del: 'Delete word' },
  sk: { edit: 'Upraviť slovíčko', del: 'Zmazať slovíčko' },
};

const WORD_STATS = {
  en: { tested: (n) => `Tested: ${n}\u00d7`, success: (p) => `Success: ${p}%` },
  sk: { tested: (n) => `Testované: ${n}\u00d7`, success: (p) => `Úspešnosť: ${p}%` },
};

// Language
const langButtons = document.querySelectorAll('.lang-btn');
const currentLang = localStorage.getItem('preferredLang') || 'en';

/* Jazyk v momente použitia — prepínač EN/SK nemení konštantu vyššie, takže
   texty skladané v JS by inak ostali v pôvodnom jazyku až do reloadu.
   Hodnotu drží premenná, nie localStorage: klik na prepínač volá
   setActiveLanguage() ešte pred zápisom voľby, takže z localStorage by sme
   pri prekreslení prečítali predchádzajúci jazyk. */
let activeLang = localStorage.getItem('preferredLang') || 'en';
function uiLang() { return activeLang; }
setActiveLanguage(currentLang);
langButtons.forEach(b=>b.addEventListener('click', ()=>{ const l=b.dataset.lang; setActiveLanguage(l); localStorage.setItem('preferredLang', l); refreshOfflinePercentages(); }));

function setActiveLanguage(lang){
  activeLang = lang;
  langButtons.forEach(b=>b.classList.toggle('active', b.dataset.lang===lang));
  document.querySelectorAll('[data-en], [data-sk]').forEach(el=>{
    if (el.hasAttribute(`data-${lang}`)){
      if (el.tagName==='TITLE') document.title = el.getAttribute(`data-${lang}`);
      else el.textContent = el.getAttribute(`data-${lang}`);
    }
  });
  document.querySelectorAll('[data-en-placeholder], [data-sk-placeholder]').forEach(el=>{
    if (el.hasAttribute(`data-${lang}-placeholder`)) el.placeholder = el.getAttribute(`data-${lang}-placeholder`);
  });
  // Ikonové tlačidlá nemajú text — názov pre čítačky obrazovky sa prekladá zvlášť.
  document.querySelectorAll('[data-en-label]').forEach(el=>{
    const t = el.getAttribute(`data-${lang}-label`);
    if (t) { el.title = t; el.setAttribute('aria-label', t); }
  });
  // Riadky zoznamu sa skladajú v JS — po prepnutí jazyka ich treba prekresliť.
  if (typeof allWordsData !== 'undefined' && allWordsData.length) applyFilters(true);
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .catch(err => console.error('SW error:', err));
  });
}

/* Prihlásený používateľ sa na tejto stránke už nevypisuje — je to obrazovka,
   ktorú učiteľ premieta triede. Identita je v hlavičke pod logom appky. */

/* Názov vybraného súboru — natívne pole je skryté, takže ho musíme vypísať. */
document.getElementById('excelFile')?.addEventListener('change', (e) => {
  const el = document.getElementById('excelFileName');
  const file = e.target.files && e.target.files[0];
  el.textContent = file ? file.name
    : (el.getAttribute(`data-${currentLang}`) || 'Žiadny súbor');
});

async function loadCategories(){
  try {
    const res = await fetch('/api/v1/categories');
    const data = await res.json();
    // API vracia buď pole priamo alebo { categories: [...] }
    const cats = Array.isArray(data) ? data : (data.categories || []);
    const isOffline = res.headers.get('X-Offline') === 'true';

    let finalCats = cats;
    if (isOffline || cats.length === 0) {
      const cached = localStorage.getItem('wk_cached_categories');
      if (cached) finalCats = JSON.parse(cached);
    }

    const select = document.getElementById('editCategory');
    select.innerHTML = '<option value="">Select Category</option>';
    finalCats.forEach(cat => {
      const option = document.createElement('option');
      option.value = cat.id;
      option.textContent = cat.name;
      if (cat.id === currentCategoryId) option.selected = true;
      select.appendChild(option);
    });
  } catch(e) {
    // Offline fallback z localStorage cache (uložené dashboardom)
    const cached = localStorage.getItem('wk_cached_categories');
    if (cached) {
      const cats = JSON.parse(cached);
      const select = document.getElementById('editCategory');
      select.innerHTML = '<option value="">Select Category</option>';
      cats.forEach(cat => {
        const option = document.createElement('option');
        option.value = cat.id;
        option.textContent = cat.name;
        if (cat.id === currentCategoryId) option.selected = true;
        select.appendChild(option);
      });
    }
    console.warn('[WK] loadCategories offline fallback použitý');
  }
}

async function loadCategory(){
  try {
    const res = await fetch(`/api/v1/categories/${currentCategoryId}`);
    if(!res.ok) { console.error('Failed loading category stats'); return; }
    const isOffline = res.headers.get('X-Offline') === 'true';
    if (isOffline) return; // offline — nič neaktualizujeme, Jinja hodnoty sú v HTML

    const categoryData = await res.json();
    const lang = localStorage.getItem('preferredLang') || 'en';
    const dontKnowText = lang === 'sk' ? '😕 Neviem' : "😕 Don't Know";
    const knowText     = lang === 'sk' ? '✅ Viem'   : '✅ Know';
    const buttonsContainer = document.getElementById('overallTestButtons');
    const dontKnowBtn = buttonsContainer.querySelector('a[href*="level=dont_know"]');
    const knowBtn = buttonsContainer.querySelector('a[href*="level=know"]');
    // Merge learning% into dont_know%
    const dontKnowPct = (categoryData.level_percentages?.dont_know || 0) + (categoryData.level_percentages?.learning || 0);
    if (dontKnowBtn) dontKnowBtn.textContent = `${dontKnowText} (${Math.round(dontKnowPct)}%)`;
    if (knowBtn)     knowBtn.textContent     = `${knowText} (${categoryData.level_percentages?.know || 0}%)`;
  } catch(e) {
    // Offline — Jinja hodnoty v HTML zostávajú, nič nerobíme
    console.warn('[WK] loadCategory offline, používajú sa server-rendered hodnoty');
  }
}

async function loadWords(){
  const cacheKey = `wk_words_cat_${currentCategoryId}`;
  try{
    const res = await fetch(`/api/v1/words?category_id=${currentCategoryId}`);
    const isOffline = res.headers.get('X-Offline') === 'true';

    if(!res.ok || isOffline){
      // Offline: použi lokálnu kópiu
      const cached = localStorage.getItem(cacheKey);
      if (cached) {
        allWordsData = JSON.parse(cached);
        ensureWordsOfflineBanner();
      } else {
        allWordsData = [];
      }
      applyFilters();
      return;
    }

    const data = await res.json();
    allWordsData = data.words || [];
    // ✅ Uložiť do localStorage ako záloha pre offline
    try { localStorage.setItem(cacheKey, JSON.stringify(allWordsData)); } catch(e) {}
    applyFilters();
  }catch(e){
    // Sieťová chyba — offline fallback z localStorage
    const cached = localStorage.getItem(cacheKey);
    if (cached) {
      allWordsData = JSON.parse(cached);
      ensureWordsOfflineBanner();
    } else {
      allWordsData = [];
    }
    applyFilters();
    console.warn('[WK] loadWords offline fallback použitý');
  }
}

function ensureWordsOfflineBanner() {
  if (document.getElementById('offlineBanner')) return;
  const banner = document.createElement('div');
  banner.id = 'offlineBanner';
  banner.style.cssText = 'background:#f59e0b;color:#fff;text-align:center;padding:8px;font-weight:600;position:sticky;top:0;z-index:9999;';
  banner.textContent = '⚠️ Offline režim – zobrazujú sa uložené dáta';
  document.body.prepend(banner);
}

/* Koľko riadkov sa vykreslí naraz. Zvyšok si používateľ dobehne tlačidlom —
   kategória so 139 slovami inak vysypala všetkých 139 riadkov naraz. */
const WORDS_PAGE_SIZE = 50;
let visibleCount = WORDS_PAGE_SIZE;
let filteredWords = [];

/* Hľadá sa bez ohľadu na diakritiku aj veľkosť písmen: „cerven" nájde
   „červený". Diakritiku zahadzujeme len pri porovnaní, nie v dátach. */
function searchKey(text) {
  return (text || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

function applyFilters(keepVisible = false) {
  if (!keepVisible) visibleCount = WORDS_PAGE_SIZE;
  let result = [...allWordsData];

  const query = searchKey(document.getElementById('searchWords')?.value.trim());
  if (query) {
    result = result.filter(w =>
      searchKey(w.original_word).includes(query) || searchKey(w.translation).includes(query));
  }

  const level = document.getElementById('filterLevel').value;
  // Staršie riadky môžu mať zrušenú úroveň 'learning' — patria pod "Neviem".
  if (level !== 'all') {
    result = result.filter(w => {
      const wordLevel = w.knowledge_level === 'learning' ? 'dont_know' : w.knowledge_level;
      return wordLevel === level;
    });
  }
  const sort = document.getElementById('sortBy').value;
  if (sort === 'newest') { result.sort((a, b) => b.id - a.id); }
  else if (sort === 'oldest') { result.sort((a, b) => a.id - b.id); }
  else if (sort === 'az') { result.sort((a, b) => a.original_word.localeCompare(b.original_word)); }
  else if (sort === 'za') { result.sort((a, b) => b.original_word.localeCompare(a.original_word)); }
  filteredWords = result;
  renderWords(result.slice(0, visibleCount));
  renderListFooter();
  updateBulkUI();
  refreshOfflinePercentages();
}

function renderListFooter() {
  const footer = document.getElementById('listFooter');
  const total = filteredWords.length;
  const shown = Math.min(visibleCount, total);
  if (!footer) return;
  if (total <= WORDS_PAGE_SIZE) { footer.style.display = 'none'; return; }

  const sk = uiLang() === 'sk';
  footer.style.display = 'flex';
  document.getElementById('listCount').textContent = sk
    ? `Zobrazených ${shown} zo ${total}` : `Showing ${shown} of ${total}`;

  const btn = document.getElementById('loadMoreBtn');
  const rest = total - shown;
  if (rest <= 0) { btn.style.display = 'none'; return; }
  btn.style.display = 'inline-flex';
  const next = Math.min(WORDS_PAGE_SIZE, rest);
  btn.textContent = sk ? `Zobraziť ďalších ${next}` : `Show ${next} more`;
}

function showMoreWords() {
  visibleCount += WORDS_PAGE_SIZE;
  applyFilters(true);
}

// Offline: percentá na test tlačidlách prepočítaj z lokálne uložených slovíčok.
// Server-rendered (Jinja) hodnoty v cachovanej HTML sú staré a neodrážajú offline
// zmeny úrovní. Online sa o správne hodnoty stará loadCategory() z API.
function refreshOfflinePercentages() {
  if (navigator.onLine) return;
  const buttons = document.getElementById('overallTestButtons');
  if (!buttons) return;
  const lang = localStorage.getItem('preferredLang') || 'en';
  const dontKnowText = lang === 'sk' ? '😕 Neviem' : "😕 Don't Know";
  const knowText     = lang === 'sk' ? '✅ Viem'   : '✅ Know';
  const total = allWordsData.length;
  if (total === 0) return;   // žiadne lokálne dáta → nechaj posledné známe hodnoty
  let known = 0;
  for (const w of allWordsData) { if (w.knowledge_level === 'know') known++; }
  const dontKnow = total - known;   // dont_know + learning zlúčené
  const knowPct     = total ? Math.round(known / total * 100) : 0;
  const dontKnowPct = total ? Math.round(dontKnow / total * 100) : 0;
  const dontKnowBtn = buttons.querySelector('a[href*="level=dont_know"]');
  const knowBtn     = buttons.querySelector('a[href*="level=know"]');
  if (dontKnowBtn) dontKnowBtn.textContent = `${dontKnowText} (${dontKnowPct}%)`;
  if (knowBtn)     knowBtn.textContent     = `${knowText} (${knowPct}%)`;
}

function renderWords(words){
  const list = document.getElementById('wordsList');
  if(!words || words.length===0){
    list.innerHTML = `<li class="no-words" data-en="No words found." data-sk="Nenašli sa žiadne slovíčka.">No words found.</li>`;
    translateElements();
    return;
  }
  const levelBadge = w => w.knowledge_level==='know'
    ? '<span style="font-weight:600;color:#38a169;">✅</span>'
    : '<span style="font-weight:600;color:#e53e3e;">😕</span>';
  list.innerHTML = words.map(w=>`
    <li class="word-item" data-word-id="${w.id}">
      ${READONLY ? '' : `<input type="checkbox" class="word-checkbox" value="${w.id}" onchange="updateBulkUI()">`}
      <div class="word-content">
        <div class="word-original">${escapeHtml(w.original_word)}</div>
        <div class="word-translation">${escapeHtml(w.translation)}</div>
        <div class="word-stats">
          ${READONLY ? levelBadge(w) : `<select class="level-select" onchange="changeKnowledgeLevel(${w.id}, this.value)">
            <option value="dont_know" ${(w.knowledge_level==='dont_know'||w.knowledge_level==='learning')?'selected':''} data-en="😕 Don't Know" data-sk="😕 Neviem">😕 Don't Know</option>
            <option value="know" ${w.knowledge_level==='know'?'selected':''} data-en="✅ Know" data-sk="✅ Viem">✅ Know</option>
          </select>`}
          <span>${WORD_STATS[uiLang()].tested(w.times_tested || 0)}</span>
          <span>${WORD_STATS[uiLang()].success(w.success_rate || 0)}</span>
        </div>
      </div>
      ${READONLY ? '' : `<div class="word-actions">
        <button class="icon-btn" onclick="editWord(${w.id})" title="${WORD_ACTIONS[uiLang()].edit}" aria-label="${WORD_ACTIONS[uiLang()].edit}"><i class="fa-solid fa-pen"></i></button>
        <button class="icon-btn" style="color: var(--danger);" onclick="deleteWord(${w.id})" title="${WORD_ACTIONS[uiLang()].del}" aria-label="${WORD_ACTIONS[uiLang()].del}"><i class="fa-solid fa-trash"></i></button>
      </div>`}
    </li>
  `).join('');
}

function updateBulkUI() {
  const checked = document.querySelectorAll('.word-checkbox:checked');
  const bulkPanel = document.getElementById('bulkActions');
  if (checked.length > 0) { bulkPanel.style.display = 'flex'; }
  else { bulkPanel.style.display = 'none'; }
  const allCheckboxes = document.querySelectorAll('.word-checkbox');
  const selectAll = document.getElementById('selectAll');
  if (allCheckboxes.length > 0 && checked.length === allCheckboxes.length) {
    selectAll.checked = true; selectAll.indeterminate = false;
  } else if (checked.length > 0) {
    selectAll.checked = false; selectAll.indeterminate = true;
  } else {
    selectAll.checked = false; selectAll.indeterminate = false;
  }
}

function toggleSelectAll(source) {
  // Zámer si treba zapamätať hneď: dokreslenie skrytých riadkov nižšie spustí
  // updateBulkUI(), ktorá `source.checked` prepíše na false.
  const wanted = source.checked;
  // „Vybrať všetko" znamená všetko, čo prešlo filtrom — nie len prvú stránku.
  // Skryté riadky nemajú checkbox, takže ich najprv dokreslíme.
  if (wanted && filteredWords.length > visibleCount) {
    visibleCount = filteredWords.length;
    applyFilters(true);
  }
  document.querySelectorAll('.word-checkbox').forEach(cb => cb.checked = wanted);
  source.checked = wanted;
  updateBulkUI();
}

async function bulkChangeLevel() {
  const level = document.getElementById('bulkLevelSelect').value;
  if (!level) return;
  const checked = document.querySelectorAll('.word-checkbox:checked');
  const ids = Array.from(checked).map(cb => cb.value);
  if (ids.length === 0) return;

  // Offline podporujeme cez queue
  if (!navigator.onLine) {
    const queue = JSON.parse(localStorage.getItem('wk_offline_queue') || '[]');
    const now = Date.now();

    ids.forEach(wordId => {
      queue.push({ type: 'knowledge_level', wordId, newLevel: level, ts: now });
      const word = allWordsData.find(w => String(w.id) === String(wordId));
      if (word) word.knowledge_level = level;
    });

    localStorage.setItem('wk_offline_queue', JSON.stringify(queue));
    applyFilters();
    showMessage('Offline: hromadná zmena úrovne bude synchronizovaná po pripojení.', 'success');
    return;
  }

  const applyBtn = document.querySelector('#bulkActions .btn-primary');
  const label = applyBtn ? applyBtn.textContent : '';
  if (applyBtn) {
    applyBtn.disabled = true;
    applyBtn.innerHTML = '<span class="btn-spinner"></span>' + escapeHtml(label);
  }
  try {
    const failed = await runWithProgress(ids, async id => (await fetch(`/api/v1/words/${id}/knowledge-level`, {
      method:'PUT',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ knowledge_level:level })
    })).ok, () => {});
    if (failed) showMessage(`${getTranslatedMessage('failed_to_update_knowledge_level')} (${failed}/${ids.length})`, 'error');
    else showMessage(getTranslatedMessage('knowledge_level_updated_successfully'), 'success');
  } finally {
    if (applyBtn) { applyBtn.disabled = false; applyBtn.textContent = label; }
  }
  await loadWords();
  await loadCategory();
}

async function bulkDelete() {
  const checked = document.querySelectorAll('.word-checkbox:checked');
  if (checked.length === 0) return;
  const lang = localStorage.getItem('preferredLang')||'en';
  const modalMsg = document.getElementById('modalMessage');
  const confirmBtn = document.querySelector('.modal-btn.confirm');
  modalMsg.textContent = getTranslatedMessage('are_you_sure_bulk_delete');
  confirmBtn.textContent = lang === 'sk' ? 'Zmazať' : 'Delete';
  pendingAction = async () => {
    const ids = Array.from(checked).map(cb => cb.value);
    setModalProgress(0, ids.length);
    const failed = await runWithProgress(
      ids,
      async id => (await fetch(`/api/v1/words/${id}`, { method:'DELETE' })).ok,
      setModalProgress
    );
    if (failed) {
      showMessage(`${getTranslatedMessage('failed_to_delete_word')} (${failed}/${ids.length})`, 'error');
    } else {
      showMessage(getTranslatedMessage('word_deleted_successfully'), 'success');
    }
    await loadWords();
    await loadCategory();
    document.getElementById('selectAll').checked = false;
  };
  showModal();
}

function escapeHtml(unsafe){ return String(unsafe).replace(/[&<>"]+/g, function(m){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]; }); }

function translateElements(){
  const lang = localStorage.getItem('preferredLang')||'en';
  document.querySelectorAll('[data-en]:not(.no-translate), [data-sk]:not(.no-translate)').forEach(el=>{
    if(el.hasAttribute(`data-${lang}`)){ el.textContent = el.getAttribute(`data-${lang}`); }
  });
  document.querySelectorAll('[data-en-placeholder], [data-sk-placeholder]').forEach(el=>{
    if(el.hasAttribute(`data-${lang}-placeholder`)) el.placeholder = el.getAttribute(`data-${lang}-placeholder`);
  });
}

// Forms
// ?. — formulár v readonly (sada triedy) neexistuje
document.getElementById('addWordForm')?.addEventListener('submit', async function(e){
  e.preventDefault();
  const fd = new FormData(this);
  const payload = { original_word: fd.get('original_word'), translation: fd.get('translation'), category_id: currentCategoryId };

  if (!navigator.onLine) {
    const queue = JSON.parse(localStorage.getItem('wk_offline_queue') || '[]');
    const tempId = 'offline_' + Date.now();
    queue.push({ type: 'add_word', tempId, original_word: payload.original_word, translation: payload.translation, category_id: payload.category_id, ts: Date.now() });
    localStorage.setItem('wk_offline_queue', JSON.stringify(queue));

    allWordsData.unshift({
      id: tempId,
      original_word: payload.original_word,
      translation: payload.translation,
      category_id: payload.category_id,
      knowledge_level: 'dont_know'
    });
    applyFilters();
    this.reset();
    showMessage('Offline: slovíčko bude pridané po pripojení.', 'success');
    return;
  }

  try{
    const res = await fetch('/api/v1/words', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    if(res.ok){ showMessage(getTranslatedMessage('word_added_successfully'),'success'); this.reset(); await loadWords(); }
    else { const err = await res.json(); showMessage(err.detail || getTranslatedMessage('failed_to_add_word'),'error'); }
  }catch(e){ console.error(e); showMessage(getTranslatedMessage('error_adding_word'),'error'); }
});

document.getElementById('importForm')?.addEventListener('submit', async function(e){
  e.preventDefault();
  const fileInput = document.getElementById('excelFile');
  const file = fileInput.files[0];
  if(!file){ showMessage(getTranslatedMessage('no_file_selected'),'error'); return; }
  if (file.name.toLowerCase().endsWith('.txt')) { handleTxtImport(file); return; }
  if(file.size > 10*1024*1024){ showMessage(getTranslatedMessage('file_too_large'),'error'); return; }
  const progressDiv = document.getElementById('importProgress');
  const progressBar = document.getElementById('progressBar');
  progressDiv.style.display='block'; progressBar.style.width='0%';
  const formData = new FormData();
  formData.append('excelFile', file);
  formData.append('category_id', currentCategoryId);
  try{
    const res = await fetch('/api/v1/words/import', { method:'POST', body: formData });
    progressBar.style.width='100%';
    if(res.ok){ const result = await res.json(); showMessage(getTranslatedMessage('words_imported_successfully').replace('{count}', result.imported_count + (result.updated_count || 0)),'success'); this.reset(); await loadWords(); }
    else { const err = await res.json(); showMessage(err.detail || getTranslatedMessage('failed_to_import_words'),'error'); }
  }catch(e){ console.error(e); showMessage(getTranslatedMessage('error_importing_words'),'error'); }
  finally{ setTimeout(()=>{ progressDiv.style.display='none'; progressBar.style.width='0%'; },1200); }
});

function handleTxtImport(file) {
  const progressDiv = document.getElementById('importProgress');
  const progressBar = document.getElementById('progressBar');
  progressDiv.style.display = 'block'; progressBar.style.width = '0%';
  const reader = new FileReader();
  reader.onload = async function(e) {
    const lines = e.target.result.split('\n');
    let count = 0;
    for(let i=0; i<lines.length; i++) {
      const line = lines[i].trim();
      if(!line) continue;
      const parts = line.split(',');
      if(parts.length >= 2) {
        const original = parts[0].trim();
        const translation = parts.slice(1).join(',').trim();
        if(original && translation) {
          try { await fetch('/api/v1/words', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ original_word: original, translation: translation, category_id: currentCategoryId }) }); count++; } catch(err) {}
        }
      }
      progressBar.style.width = Math.round(((i+1)/lines.length)*100) + '%';
    }
    setTimeout(() => { progressDiv.style.display = 'none'; progressBar.style.width = '0%'; showMessage(getTranslatedMessage('words_imported_successfully').replace('{count}', count), 'success'); loadWords(); document.getElementById('importForm').reset(); }, 500);
  };
  reader.readAsText(file);
}

// Edit / Delete / Knowledge level
let currentEditWordId = null;

async function editWord(id){
  currentEditWordId = id;
  try {
    const res = await fetch(`/api/v1/words/${id}`);
    if(!res.ok) { showMessage(getTranslatedMessage('error_loading_word'),'error'); return; }
    const word = await res.json();
    document.getElementById('editOriginal').value = word.original_word;
    document.getElementById('editTranslation').value = word.translation;
    document.getElementById('editCategory').value = word.category_id;
    showEditModal();
  } catch(e) { console.error(e); showMessage(getTranslatedMessage('error_loading_word'),'error'); }
}

function showEditModal(){ document.getElementById('editModal').style.display='flex'; }
function closeEditModal(){ document.getElementById('editModal').style.display='none'; currentEditWordId=null; }

document.getElementById('editWordForm').addEventListener('submit', async function(e){
  e.preventDefault();
  if(!currentEditWordId) return;
  const fd = new FormData(this);
  const payload = { original_word: fd.get('editOriginal'), translation: fd.get('editTranslation'), category_id: parseInt(fd.get('editCategory')) };

  if (!navigator.onLine) {
    const queue = JSON.parse(localStorage.getItem('wk_offline_queue') || '[]');
    queue.push({ type: 'edit_word', wordId: currentEditWordId, ...payload, ts: Date.now() });
    localStorage.setItem('wk_offline_queue', JSON.stringify(queue));

    const word = allWordsData.find(w => String(w.id) === String(currentEditWordId));
    if (word) {
      word.original_word = payload.original_word;
      word.translation = payload.translation;
      word.category_id = payload.category_id;
    }

    applyFilters();
    closeEditModal();
    showMessage('Offline: zmena slovíčka bude synchronizovaná po pripojení.', 'success');
    return;
  }

  try{
    const res = await fetch(`/api/v1/words/${currentEditWordId}`, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    if(res.ok){ showMessage(getTranslatedMessage('word_updated_successfully'),'success'); closeEditModal(); await loadWords(); await loadCategory(); }
    else { const err = await res.json(); showMessage(err.detail || getTranslatedMessage('failed_to_update_word'),'error'); }
  }catch(e){ console.error(e); showMessage(getTranslatedMessage('error_updating_word'),'error'); }
});

document.getElementById('editModal').addEventListener('click',(e)=>{ if(e.target===document.getElementById('editModal')) closeEditModal(); });

async function changeKnowledgeLevel(wordId, newLevel) {
  // Offline queue pre knowledge-level update
  try {
    if (!navigator.onLine) {
      const queue = JSON.parse(localStorage.getItem('wk_offline_queue') || '[]');
      queue.push({ type: 'knowledge_level', wordId, newLevel, ts: Date.now() });
      localStorage.setItem('wk_offline_queue', JSON.stringify(queue));

      // UI update aspoň lokálne (bez fetch), aby aj offline bolo vidieť zmenu
      const word = allWordsData.find(w => String(w.id) === String(wordId));
      if (word) word.knowledge_level = newLevel;
      applyFilters();
      showMessage('Offline: zmena úrovne bude synchronizovaná po pripojení.', 'success');
      return;
    }

    const res = await fetch(`/api/v1/words/${wordId}/knowledge-level`, {
      method:'PUT',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ knowledge_level:newLevel })
    });

    if(res.ok){
      showMessage(getTranslatedMessage('knowledge_level_updated_successfully'),'success');
      await loadCategory();
      return;
    }

    const err = await res.json();
    showMessage(err.detail || getTranslatedMessage('failed_to_update_knowledge_level'),'error');
    await loadWords();
  } catch(e){
    console.error(e);
    showMessage(getTranslatedMessage('error_updating_knowledge_level'),'error');
    await loadWords();
  }
}

function syncOfflineQueue() {
  if (!navigator.onLine) return;
  const run = async () => {
    const queue = JSON.parse(localStorage.getItem('wk_offline_queue') || '[]');
    if (queue.length === 0) return;

    // Deduplication knowledge_level (ponechaj poslednú zmenu pre každý wordId)
    const klMap = queue.reduce((acc, item) => {
      if (!item || item.type !== 'knowledge_level') return acc;
      acc[String(item.wordId)] = item;
      return acc;
    }, {});

    const dedupedKnowledgeLevels = Object.values(klMap);
    if (dedupedKnowledgeLevels.length === 0 && !queue.some(i => i && i.type !== 'knowledge_level')) return;

    // Vezmime ostatné typy bez deduplikácie (okrem knowledge_level)
    const otherItems = queue.filter(i => i && i.type !== 'knowledge_level');
    const dedupedQueue = [
      ...otherItems,
      ...dedupedKnowledgeLevels
    ];

    // Poradie: add → edit → delete → knowledge_level
    const ordered = [
      ...dedupedQueue.filter(i => i.type === 'add_word'),
      ...dedupedQueue.filter(i => i.type === 'edit_word'),
      ...dedupedQueue.filter(i => i.type === 'delete_word'),
      ...dedupedQueue.filter(i => i.type === 'knowledge_level'),
    ];

    const remaining = [];
    for (const item of ordered) {
      if (item.type === 'knowledge_level') { } else if (item.type === 'add_word') {
        try {
          const res = await fetch('/api/v1/words', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              original_word: item.original_word,
              translation: item.translation,
              category_id: item.category_id
            })
          });
          if (!res.ok) remaining.push(item);
        } catch (e) {
          remaining.push(item);
        }
      } else if (item.type === 'edit_word') {
        try {
          if (String(item.wordId).startsWith('offline_')) {
            continue;
          }
          const res = await fetch(`/api/v1/words/${item.wordId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              original_word: item.original_word,
              translation: item.translation,
              category_id: item.category_id
            })
          });
          if (!res.ok) remaining.push(item);
        } catch (e) {
          remaining.push(item);
        }
      } else if (item.type === 'delete_word') {
        try {
          if (String(item.wordId).startsWith('offline_')) {
            continue;
          }
          const res = await fetch(`/api/v1/words/${item.wordId}`, { method: 'DELETE' });
          if (!res.ok) remaining.push(item);
        } catch (e) {
          remaining.push(item);
        }
      } else { 
        // Unknown item type => drop or keep? radšej ponechaj v remaining
        remaining.push(item);
      }
      if (item.type === 'knowledge_level') {
        try {
          const res = await fetch(`/api/v1/words/${item.wordId}/knowledge-level`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ knowledge_level: item.newLevel })
          });
          if (!res.ok) remaining.push(item);
        } catch (e) {
          remaining.push(item);
        }
      }

    }

    localStorage.setItem('wk_offline_queue', JSON.stringify(remaining));
    if (remaining.length === 0) {
      showMessage('Offline zmeny synchronizované.', 'success');
    } else {
      showMessage('Niektoré offline zmeny sa nepodarilo synchronizovať.', 'error');
    }

    await loadWords();
    await loadCategory();
  };

  run();
}

window.addEventListener('online', () => { syncOfflineQueue(); });

let pendingAction = null;

function deleteWord(wordId){
  const lang = localStorage.getItem('preferredLang')||'en';
  const modalMsg = document.getElementById('modalMessage');
  const confirmBtn = document.querySelector('.modal-btn.confirm');
  modalMsg.textContent = getTranslatedMessage('are_you_sure_delete_word');
  confirmBtn.textContent = lang === 'sk' ? 'Zmazať' : 'Delete';
  pendingAction = async ()=>{
    if (!navigator.onLine) {
      const queue = JSON.parse(localStorage.getItem('wk_offline_queue') || '[]');
      queue.push({ type: 'delete_word', wordId, ts: Date.now() });
      localStorage.setItem('wk_offline_queue', JSON.stringify(queue));

      allWordsData = allWordsData.filter(w => String(w.id) !== String(wordId));
      applyFilters();
      showMessage('Offline: slovíčko bude zmazané po pripojení.', 'success');
      return;
    }

    try{
      const res = await fetch(`/api/v1/words/${wordId}`, { method:'DELETE' });
      if(res.ok){ showMessage(getTranslatedMessage('word_deleted_successfully'),'success'); await loadWords(); await loadCategory(); }
      else { const err = await res.json(); showMessage(err.detail || getTranslatedMessage('failed_to_delete_word'),'error'); }
    }catch(e){ console.error(e); showMessage(getTranslatedMessage('error_deleting_word'),'error'); }
  };
  showModal();
}

function showModal(){ document.getElementById('confirmationModal').style.display='flex'; }
function closeModal(){ document.getElementById('confirmationModal').style.display='none'; pendingAction=null; }
let actionRunning = false;
async function confirmAction(){
  if (!pendingAction || actionRunning) return;
  const modal = document.getElementById('confirmationModal');
  const confirmBtn = modal.querySelector('.modal-btn.confirm');
  const cancelBtn  = modal.querySelector('.modal-btn.cancel');
  const label = confirmBtn.textContent;
  actionRunning = true;
  confirmBtn.disabled = cancelBtn.disabled = true;
  confirmBtn.innerHTML = '<span class="btn-spinner"></span>' + escapeHtml(label);
  try {
    await pendingAction();
  } finally {
    actionRunning = false;
    confirmBtn.disabled = cancelBtn.disabled = false;
    confirmBtn.textContent = label;
    closeModal();
  }
}

/* Priebeh v modáli: "Mazanie slovíčok… 3/12". Requesty púšťame po štvoriciach,
   nech to na väčšom výbere neotvorí stovky spojení naraz. */
function setModalProgress(done, total){
  const lang = localStorage.getItem('preferredLang') || 'en';
  const text = lang === 'sk' ? 'Mazanie slovíčok… ' : 'Deleting words… ';
  document.getElementById('modalMessage').textContent = text + done + '/' + total;
}

async function runWithProgress(ids, worker, onProgress){
  const queue = ids.slice();
  let done = 0, failed = 0;
  const runner = async () => {
    while (queue.length) {
      const id = queue.shift();
      try { if (!await worker(id)) failed++; } catch(e){ console.error(e); failed++; }
      onProgress(++done, ids.length);
    }
  };
  await Promise.all(Array.from({ length: Math.min(4, queue.length) }, runner));
  return failed;
}
document.getElementById('confirmationModal').addEventListener('click',(e)=>{ if(e.target===document.getElementById('confirmationModal')) closeModal(); });

function showMessage(msg,type){
  const el = document.getElementById('message');
  el.textContent = msg;
  el.className = type;
  el.style.display='block';
  setTimeout(()=>el.style.display='none',5000);
}

function getTranslatedMessage(key){
  const lang = localStorage.getItem('preferredLang')||'en';
  const messages = {
    'word_added_successfully':{en:'Word added successfully!',sk:'Slovíčko bolo úspešne pridané!'},
    'failed_to_add_word':{en:'Failed to add word',sk:'Nepodarilo sa pridať slovíčko'},
    'error_adding_word':{en:'Error adding word',sk:'Chyba pri pridávaní slovíčka'},
    'word_updated_successfully':{en:'Word updated successfully!',sk:'Slovíčko bolo úspešne aktualizované!'},
    'failed_to_update_word':{en:'Failed to update word',sk:'Nepodarilo sa aktualizovať slovíčko'},
    'error_updating_word':{en:'Error updating word',sk:'Chyba pri aktualizácii slovíčka'},
    'knowledge_level_updated_successfully':{en:'Knowledge level updated successfully!',sk:'Úroveň znalosti bola úspešne aktualizovaná!'},
    'failed_to_update_knowledge_level':{en:'Failed to update knowledge level',sk:'Nepodarilo sa aktualizovať úroveň znalosti'},
    'error_updating_knowledge_level':{en:'Error updating knowledge level',sk:'Chyba pri aktualizácii úrovne znalosti'},
    'word_deleted_successfully':{en:'Word deleted successfully!',sk:'Slovíčko bolo úspešne zmazané!'},
    'failed_to_delete_word':{en:'Failed to delete word',sk:'Nepodarilo sa zmazať slovíčko'},
    'error_deleting_word':{en:'Error deleting word',sk:'Chyba pri mazaní slovíčka'},
    'error_loading_word':{en:'Error loading word',sk:'Chyba pri načítaní slovíčka'},
    'no_file_selected':{en:'Please select a file to import',sk:'Vyberte súbor na importovanie'},
    'file_too_large':{en:'File size exceeds 10MB limit',sk:'Veľkosť súboru presahuje limit 10MB'},
    'words_imported_successfully':{en:'{count} words imported successfully!',sk:'{count} slovíčok bolo úspešne importovaných!'},
    'failed_to_import_words':{en:'Failed to import words',sk:'Nepodarilo sa importovať slovíčka'},
    'error_importing_words':{en:'Error importing words',sk:'Chyba pri importovaní slovíčok'},
    'are_you_sure_bulk_delete':{en:'Are you sure you want to delete selected words?',sk:'Ste si istý, že chcete zmazať vybrané slovíčka?'},
    'are_you_sure_delete_word':{en:'Are you sure you want to delete this word?',sk:'Ste si istý, že chcete zmazať toto slovíčko?'}
  };
  return messages[key] ? messages[key][lang] : key;
}

async function logout() {
  try { await fetch('/api/v1/logout', {method:'POST'}); } catch (e) { console.error(e); }
  localStorage.removeItem('access_token');
  localStorage.removeItem('user_email');
  localStorage.removeItem('user_name');
  localStorage.removeItem('user_id');
  window.location.href = '/login';
}

// ✅ OPRAVA 3: Dark mode sa číta z API a ukladá do localStorage pre budúce rýchle načítanie
async function loadDarkModePreference() {
  try {
    const response = await fetch('/api/user');
    if (response.ok) {
      const userData = await response.json();
      if (userData.dark_mode) {
        document.documentElement.setAttribute('data-theme', 'dark');
        localStorage.setItem('darkMode', 'true');
      } else {
        document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('darkMode', 'false');
      }
    }
  } catch (error) {
    console.error('Error loading dark mode preference:', error);
  }
}

// Návrat tlačidlom späť (typicky z testu kartičiek) obnoví stránku z bfcache —
// DOMContentLoaded už nebeží, takže percentá „Viem/Neviem" na testovacích tlačidlách
// aj úrovne slovíčok by ostali v stave spred testu. Dashboard to rieši tým, že celý
// init visí na pageshow; tu stačí dotiahnuť dáta zo servera.
window.addEventListener('pageshow', (e) => {
  if (!e.persisted) return;   // bežné načítanie už obslúžil DOMContentLoaded
  loadCategory();
  loadWords();
});

// Init
document.addEventListener('DOMContentLoaded', ()=>{
  loadDarkModePreference();
  loadCategories();
  loadCategory();
  loadWords();
  translateElements();

  // Ak existujú offline zmeny, synchronizuj ich hneď pri štarte stránky (ak už sme online)
  try { syncOfflineQueue(); } catch (e) { console.error('syncOfflineQueue init failed:', e); }
  
});
