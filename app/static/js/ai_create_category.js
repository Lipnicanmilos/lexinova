async function aiCreateCategory() {
  const prompt = document.getElementById('aiCategoryPrompt')?.value?.trim();
  const languageFrom = document.getElementById('aiLanguageFrom')?.value || 'en';
  const languageTo = document.getElementById('aiLanguageTo')?.value || 'sk';
  const count = parseInt(document.getElementById('aiWordCount')?.value || '25', 10);

  if (!prompt) {
    alert('Prompt is required');
    return;
  }

  const res = await fetch('/api/v1/categories/ai-create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt,
      language_from: languageFrom,
      language_to: languageTo,
      count
    })
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const sk = (localStorage.getItem('preferredLang') || 'en') === 'sk';
    let msg;
    if (res.status === 429) {
      msg = (sk && data?.detail) ? data.detail
        : sk ? 'Vyčerpal si limit AI generovaní. Skús to neskôr.'
             : 'AI generation limit reached. Please try again later.';
    } else if (res.status === 502) {
      msg = (sk && data?.detail) ? data.detail
        : sk ? 'AI generovanie zlyhalo. Skús to znova.'
             : 'AI generation failed. Please try again.';
    } else if (res.status >= 500) {
      msg = sk ? 'Chyba servera. Skús to o chvíľu.' : 'Server error. Please try again shortly.';
    } else {
      msg = data?.detail || data?.error || (sk ? 'Požiadavka zlyhala.' : 'Request failed.');
    }
    alert(msg);
    return;
  }

  // Ak dashboard používa local funkciu loadCategories, zavolaj ju.
  if (typeof loadCategories === 'function') await loadCategories();
  if (typeof loadUserStats === 'function') await loadUserStats();

  alert(`Generated category: ${data.category_name}. Inserted: ${data.inserted_words}, skipped: ${data.skipped_words}`);
}

