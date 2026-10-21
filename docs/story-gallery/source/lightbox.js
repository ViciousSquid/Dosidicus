(function () {
  var box = document.getElementById('lightbox');
  if (!box || typeof box.showModal !== 'function') return;
  var img = box.querySelector('img');
  var caption = box.querySelector('.lb-caption');
  document.querySelectorAll('.zoom').forEach(function (button) {
    button.addEventListener('click', function () {
      img.src = button.dataset.full;
      img.alt = button.dataset.caption;
      caption.textContent = button.dataset.caption;
      box.showModal();
    });
  });
  box.addEventListener('click', function (event) {
    if (event.target === box) box.close();
  });
})();
