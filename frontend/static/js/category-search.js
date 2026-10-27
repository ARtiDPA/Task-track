/* Search existing native category selectors without changing form values or API payloads. */
(() => {
  'use strict';
  const enhanced = new WeakSet();
  const normalize = text => text.toLocaleLowerCase('ru').replaceAll('ё', 'е').trim();
  function enhance(select) {
    if (enhanced.has(select) || /emoji/i.test(select.id)) return;
    enhanced.add(select);
    const wrap = document.createElement('div');
    wrap.className = 'category-search';
    const input = document.createElement('input');
    input.type = 'search';
    input.placeholder = 'Найти категорию…';
    input.autocomplete = 'off';
    input.setAttribute('aria-label', 'Поиск категории');
    input.setAttribute('aria-controls', select.id);
    const status = document.createElement('small');
    status.className = 'category-search-status';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    status.hidden = true;
    select.before(wrap);
    wrap.append(input, select, status);
    let source = [...select.options].map(option => option.cloneNode(true));
    const observer = new MutationObserver(() => {
      // Business modules may rebuild options on profile, kind or category changes.
      source = [...select.options].map(option => option.cloneNode(true));
      filter();
    });
    function filter() {
      const selected = select.value;
      const query = normalize(input.value);
      const matches = source.filter(option => normalize(option.textContent).includes(query));
      const choices = matches.map(option => option.cloneNode(true));
      const current = source.find(option => option.value === selected);
      if (current && !choices.some(option => option.value === selected)) {
        const pinned = current.cloneNode(true);
        pinned.textContent = 'Выбрано: ' + current.textContent;
        choices.unshift(pinned);
      }
      observer.disconnect();
      select.replaceChildren(...choices);
      if (choices.some(option => option.value === selected)) select.value = selected;
      observer.observe(select, {childList: true, subtree: true, characterData: true});
      status.hidden = !query;
      status.textContent = matches.length ? `Найдено: ${matches.length}` : 'Ничего не найдено. Текущий выбор сохранён.';
    }
    input.addEventListener('input', filter);
    select.addEventListener('change', filter);
    select.form?.addEventListener('reset', () => setTimeout(() => { input.value = ''; filter(); }));
    observer.observe(select, {childList: true, subtree: true, characterData: true});
  }
  function discover() {
    document.querySelectorAll('select[id*="category"]').forEach(enhance);
  }
  discover();
  new MutationObserver(discover).observe(document.body, {childList: true, subtree: true});
})();
