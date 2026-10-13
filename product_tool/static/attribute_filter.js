(() => {
  const query = document.getElementById('attribute-search');
  const role = document.getElementById('attribute-role');
  if (!query || !role) return;
  const update = () => {
    const term = query.value.trim().toLocaleLowerCase('ru');
    for (const group of document.querySelectorAll('.attribute-group')) {
      let visible = 0;
      for (const row of group.querySelectorAll('tbody > tr')) {
        const matches = (role.value === 'all' || group.dataset.role === role.value) && row.textContent.toLocaleLowerCase('ru').includes(term);
        row.hidden = !matches;
        if (matches) visible++;
      }
      group.hidden = visible === 0;
    }
  };
  query.addEventListener('input', update);
  role.addEventListener('change', update);
})();
