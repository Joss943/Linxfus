document.querySelectorAll('[data-copy]').forEach(b => b.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(b.previousElementSibling.textContent.trim());
    b.textContent = 'Copié ✓';
  } catch { b.textContent = 'Ctrl+C'; }
  setTimeout(() => { b.textContent = 'Copier'; }, 1800);
}));
