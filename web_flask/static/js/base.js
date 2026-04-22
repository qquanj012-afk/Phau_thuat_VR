/* TOAST NOTIFICATION */
let toastTimer = null;
function showToast(msg, isError = false) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.className = 'toast show' + (isError ? ' error' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3000);
}

/* MODAL VIEWER WITH DRAG & ZOOM */
let currentZoom = 1;
let isDragging = false;
let startX = 0, startY = 0, translateX = 0, translateY = 0;
let modalImg = null;

function openModal(imageSrc, title = 'Ảnh') {
  const modal = document.getElementById('modal');
  modalImg = document.getElementById('modal-img');
  const modalTitle = document.getElementById('modal-title');
  if (!modal || !modalImg) return;

  modalTitle.textContent = title;
  modalImg.src = imageSrc;

  // Reset transform
  currentZoom = 1;
  translateX = 0;
  translateY = 0;
  modalImg.style.transform = `scale(${currentZoom})`;
  modalImg.style.cursor = 'grab';

  modal.classList.add('show');
}

function closeModal() {
  const modal = document.getElementById('modal');
  if (modal) modal.classList.remove('show');
}

function applyTransform() {
  if (!modalImg) {
    modalImg = document.getElementById('modal-img');
  }
  if (modalImg) {
    modalImg.style.transform = `translate(${translateX}px, ${translateY}px) scale(${currentZoom})`;
  }
}

function zoomIn() {
  currentZoom = Math.min(currentZoom + 0.25, 3);
  applyTransform();
}

function zoomOut() {
  currentZoom = Math.max(currentZoom - 0.25, 0.5);
  applyTransform();
}

function resetZoom() {
  currentZoom = 1;
  translateX = 0;
  translateY = 0;
  applyTransform();
}

function initImageDrag() {
  const img = document.getElementById('modal-img');
  if (!img) return;

  img.addEventListener('mousedown', (e) => {
    // Chỉ kích hoạt kéo khi là ảnh 2D (không phải model-viewer)
    if (img.tagName !== 'IMG') return;

    isDragging = true;
    startX = e.clientX - translateX;
    startY = e.clientY - translateY;
    img.style.cursor = 'grabbing';
    e.preventDefault();
  });

  window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const img = document.getElementById('modal-img');
    if (!img || img.tagName !== 'IMG') return;

    translateX = e.clientX - startX;
    translateY = e.clientY - startY;
    img.style.transform = `translate(${translateX}px, ${translateY}px) scale(${currentZoom})`;
  });

  window.addEventListener('mouseup', () => {
    if (isDragging) {
      isDragging = false;
      const img = document.getElementById('modal-img');
      if (img) img.style.cursor = 'grab';
    }
  });
}

/* SCROLL TO TOP */
function initScrollToTop() {
  const btn = document.getElementById('scrollToTop');
  if (!btn) return;
  window.addEventListener('scroll', () => {
    btn.classList.toggle('show', window.scrollY > 300);
  });
  btn.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
}

/* MODAL OVERLAY CLICK */
function initModalOverlay() {
  const modal = document.getElementById('modal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }
}

/* INIT COMMON */
document.addEventListener('DOMContentLoaded', () => {
  initScrollToTop();
  initModalOverlay();
  initImageDrag();
});