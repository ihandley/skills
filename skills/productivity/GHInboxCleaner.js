javascript:(function(){
  /* Backend Core GitHub logins, from ~/.claude/aliases.yaml (backend_core members, then qa). */
  const targetAuthors = [
    "wttLVT",
    "rcollins112",
    "melo2day",
    "SwaAvula",
    "ianhandley-lvt",
    "gregkeys-lvt",
    "kmarsh-lvt",
    "prestondelano-lvt",
    "rodrigomf24",
    "seunghee-lvt",
    "proslambanomenos",
    "kbeck-lvt"
  ];

  const targetSelectors = [
    '.octicon-git-merge',              /* Merged PRs */
    '.octicon-git-pull-request-closed', /* Closed PRs */
    '.octicon-issue-closed',            /* Closed Issues */
    '.octicon-git-pull-request-draft',  /* Draft PRs */
    '.octicon-tag',                     /* Releases / Tags */
    '[aria-label*="Merged"]',
    '[aria-label*="Closed"]',
    '[aria-label*="Draft"]',
    '[aria-label*="Release"]'
  ];

  const team = targetAuthors.map(author => author.toLowerCase().trim());

  /* Avatar alt text and hovercard links are not part of textContent, so include them. */
  const identityText = item => [
    item.textContent,
    ...Array.from(item.querySelectorAll('img[alt]'), img => img.alt),
    ...Array.from(item.querySelectorAll('[data-hovercard-url], a[href]'), el => el.getAttribute('data-hovercard-url') || el.getAttribute('href'))
  ].join(' ').toLowerCase();

  const all = Array.from(document.querySelectorAll('.notifications-list-item'));
  const items = all.filter(item => {
    const isNoise = targetSelectors.some(selector => item.querySelector(selector));
    if (isNoise) return true;

    const text = identityText(item);
    return !team.some(author => text.includes(author));
  });

  if (items.length === 0) {
    alert('Nothing to clear: every notification is an open PR from Backend Core.');
    return;
  }

  if (!confirm(`Mark ${items.length} of ${all.length} notifications as Done?`)) return;

  items.forEach(item => {
    const checkbox = item.querySelector('input[type="checkbox"]');
    if (checkbox && !checkbox.checked) checkbox.click();
  });

  const doneButton = document.querySelector('button[aria-label="Done"], button[data-hotkey="e"], button[data-hotkey="E"]');
  if (doneButton) {
    doneButton.click();
  } else {
    alert(`Selected ${items.length} notifications. Press E to mark them Done.`);
  }
})();
