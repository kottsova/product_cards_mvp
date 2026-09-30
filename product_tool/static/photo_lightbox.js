(() => {
  const buttons = Array.from(document.querySelectorAll('.photo-open'));
  const dialog = document.getElementById('photo-lightbox');
  if (!dialog || !buttons.length) return;
  const image = dialog.querySelector('.lightbox-image');
  const caption = dialog.querySelector('.lightbox-caption');
  const metadata = dialog.querySelector('.lightbox-metadata');
  const counter = dialog.querySelector('.lightbox-counter');
  let current = 0;
  function show(index) {
    current = (index + buttons.length) % buttons.length;
    const item = buttons[current].dataset;
    image.src = item.url;
    image.alt = item.source;
    caption.textContent = item.source + ' · ' + item.identity;
    metadata.textContent = 'Разрешение: ' + item.resolution + ' · Размер файла: ' + item.size + ' · Формат: ' + item.format;
    counter.textContent = (current + 1) + ' / ' + buttons.length;
  }
  buttons.forEach((button, index) => button.addEventListener('click', () => {
    show(index);
    dialog.showModal();
  }));
  dialog.querySelector('.lightbox-close').addEventListener('click', () => dialog.close());
  dialog.querySelector('.lightbox-prev').addEventListener('click', () => show(current - 1));
  dialog.querySelector('.lightbox-next').addEventListener('click', () => show(current + 1));
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft') { event.preventDefault(); show(current - 1); }
    if (event.key === 'ArrowRight') { event.preventDefault(); show(current + 1); }
  });
  dialog.addEventListener('close', () => { image.removeAttribute('src'); });
})();
