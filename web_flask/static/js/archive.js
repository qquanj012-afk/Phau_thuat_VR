/* ARCHIVE PAGE LOGIC */
document.addEventListener('DOMContentLoaded', function() {
  /* TAB SWITCHING */
  const tabs = document.querySelectorAll('.tab');
  const tabRaw = document.getElementById('tab-raw');
  const tabProcessed = document.getElementById('tab-processed');
  const tabMeshes = document.getElementById('tab-meshes');
  const tabTrash = document.getElementById('tab-trash');

  window.switchTab = function(tabId) {
    tabs.forEach(t => t.classList.remove('active'));
    document.querySelector(`.tab[data-tab="${tabId}"]`).classList.add('active');
    tabRaw.style.display = tabId === 'raw' ? '' : 'none';
    tabProcessed.style.display = tabId === 'processed' ? '' : 'none';
    tabMeshes.style.display = tabId === 'meshes' ? '' : 'none';
    tabTrash.style.display = tabId === 'trash' ? '' : 'none';

    if (tabId === 'trash') {
      loadTrashItems();
    } else {
      // Khi chuyển tab, áp dụng lại bộ lọc hiện tại
      filterCards();
    }
  };

  tabs.forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });

  /* SORTING */
  const sortSelect = document.getElementById('sortSelect');
  sortSelect.addEventListener('change', function() {
    const url = new URL(window.location);
    url.searchParams.set('sort', this.value);
    window.location = url.toString();
  });

  /* MODAL STATE */
  let currentFile = { filepath: '', type: '', url: '' };

  window.openModal = function(name, type, date, size, url, thumbUrl, filepath) {
    currentFile = { filepath, type, url };
    document.getElementById('modal-title').textContent = name;
    document.getElementById('modal-meta').textContent = `${date} · ${size}`;

    const modalBody = document.querySelector('.modal-body');
    const isMesh = name.toLowerCase().endsWith('.obj') || type === 'meshes';

    // Xóa nội dung cũ
    modalBody.innerHTML = '';

    if (isMesh && url && url !== '#') {
      // Tạo model-viewer cho file .obj
      const viewer = document.createElement('model-viewer');
      viewer.setAttribute('src', url);
      viewer.setAttribute('alt', name);
      viewer.setAttribute('camera-controls', '');
      viewer.setAttribute('auto-rotate', '');
      viewer.setAttribute('rotation-per-second', '30deg');
      viewer.setAttribute('style', 'width:100%; height:70vh; background:var(--bg3);');
      viewer.setAttribute('exposure', '1');
      viewer.setAttribute('shadow-intensity', '0');
      viewer.id = 'modal-viewer';
      modalBody.appendChild(viewer);

      // Ẩn nút zoom (không cần cho 3D)
      document.querySelectorAll('.modal-controls .modal-btn').forEach(btn => {
        if (btn.textContent !== '✕') btn.style.display = 'none';
      });
    } else {
      // Hiển thị ảnh 2D như cũ
      const img = document.createElement('img');
      img.src = thumbUrl;
      img.alt = name;
      img.className = 'modal-img';
      img.id = 'modal-img';
      img.style.transform = 'scale(1)';
      img.style.cursor = 'grab';
      modalBody.appendChild(img);

      // Reset biến zoom (được định nghĩa trong common.js)
      if (typeof currentZoom !== 'undefined') currentZoom = 1;
      if (typeof translateX !== 'undefined') translateX = 0;
      if (typeof translateY !== 'undefined') translateY = 0;

      // Hiện lại nút zoom
      document.querySelectorAll('.modal-controls .modal-btn').forEach(btn => {
        if (btn.textContent !== '✕') btn.style.display = 'flex';
      });
    }

    document.getElementById('modal').classList.add('show');
  };

  /* ATTACH CARD EVENTS */
  function attachCardEvents(container) {
    container.querySelectorAll('.img-card').forEach(card => {
      const name = card.dataset.name;
      const type = card.dataset.type;
      const date = card.dataset.date;
      const size = card.dataset.size;
      const url = card.dataset.url;
      const filepath = card.dataset.filepath;
      const imgElement = card.querySelector('.img-thumb-img');
      const getCurrentThumb = () => imgElement ? imgElement.src : card.dataset.thumb;

      card.addEventListener('click', (e) => {
        if (e.target.closest('.overlay-btn')) return;
        openModal(name, type, date, size, url, getCurrentThumb(), filepath);
      });

      card.querySelector('.view-btn')?.addEventListener('click', (e) => {
        e.stopPropagation();
        openModal(name, type, date, size, url, getCurrentThumb(), filepath);
      });

      card.querySelector('.download-btn')?.addEventListener('click', (e) => {
        e.stopPropagation();
        if (url && url !== '#') window.open(url, '_blank');
      });

      card.querySelector('.del-btn')?.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteFile(filepath, type);
      });
    });
  }

  attachCardEvents(document);

  /* FILE DELETION (move to trash) */
  window.deleteFile = function(filepath, type) {
    if (!confirm(`Chuyển file vào thùng rác?`)) return;
    fetch(`/archive/delete/${type}/${encodeURIComponent(filepath)}`, { method: 'DELETE' })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          showToast(`Đã chuyển vào thùng rác`);
          setTimeout(() => location.reload(), 500);
        } else {
          showToast(data.error || 'Lỗi khi xóa', true);
        }
      })
      .catch(() => showToast('Lỗi kết nối', true));
  };

  /* TRASH FUNCTIONS */
  async function loadTrashItems() {
    const grid = document.getElementById('trash-grid');
    grid.innerHTML = '<div style="color:var(--text3);padding:20px;">Đang tải...</div>';
    try {
      const res = await fetch(window.TRASH_API.items + '?sort=' + sortSelect.value);
      const items = await res.json();
      grid.innerHTML = '';
      items.forEach(item => {
        const card = createTrashCard(item);
        grid.appendChild(card);
      });
      attachCardEvents(grid);
      observeThumbnails(grid);
    } catch(e) {
      grid.innerHTML = '<div style="color:var(--danger);padding:20px;">Lỗi tải thùng rác</div>';
    }
  }

  function createTrashCard(item) {
    const div = document.createElement('div');
    div.className = 'img-card';
    div.dataset.name = item.name;
    div.dataset.type = item.original_type;
    div.dataset.subtype = item.subtype || '';  // <-- thêm subtype cho trash
    div.dataset.date = item.date_str;
    div.dataset.size = item.size;
    div.dataset.url = '#';
    div.dataset.thumb = item.thumb;
    div.dataset.filepath = item.file_path;
    div.dataset.originalType = item.original_type;

    let typeIcon = '📄';
    let typeLabel = 'Raw';
    if (item.original_type === 'processed') {
      typeIcon = '⚙️';
      typeLabel = 'Processed';
    } else if (item.original_type === 'meshes') {
      typeIcon = '◈';
      typeLabel = 'Mesh';
    }

    div.innerHTML = `
      <div class="img-thumb">
        <img class="img-thumb-img" src="${item.thumb}" data-file="${item.file_path}" alt="${item.name}"
             onerror="this.onerror=null; this.src='data:image/svg+xml,%3Csvg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'100\\' height=\\'100\\' viewBox=\\'0 0 100 100\\'%3E%3Crect width=\\'100\\' height=\\'100\\' fill=\\'%23171b26\\'/%3E%3Ctext x=\\'50\\' y=\\'55\\' font-family=\\'monospace\\' font-size=\\'12\\' fill=\\'%235a6280\\' text-anchor=\\'middle\\'%3E${typeIcon} ${typeLabel}%3C/text%3E%3C/svg%3E';">
        <div class="img-overlay">
          <div class="overlay-btn restore-btn" title="Khôi phục">↩️</div>
          <div class="overlay-btn permanent-btn" title="Xóa vĩnh viễn">❌</div>
        </div>
      </div>
      <div class="img-meta">
        <div class="img-name">${item.name}</div>
        <div class="img-date">${item.date_str} · ${typeLabel}</div>
      </div>
    `;

    div.querySelector('.restore-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      restoreFile(item.file_path);
    });

    div.querySelector('.permanent-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      permanentDelete(item.file_path);
    });

    return div;
  }

  window.restoreFile = async function(filepath) {
    if (!confirm(`Khôi phục file này?`)) return;
    try {
      const res = await fetch(window.TRASH_API.restore + encodeURIComponent(filepath), { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        showToast('Đã khôi phục');
        setTimeout(() => location.reload(), 500);
      } else {
        showToast(data.error, true);
      }
    } catch(e) {
      showToast('Lỗi kết nối', true);
    }
  };

  window.permanentDelete = async function(filepath) {
    if (!confirm(`Xóa vĩnh viễn file này? Hành động không thể hoàn tác!`)) return;
    try {
      const res = await fetch(window.TRASH_API.permanent + encodeURIComponent(filepath), { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        showToast('Đã xóa vĩnh viễn');
        setTimeout(() => location.reload(), 500);
      } else {
        showToast(data.error, true);
      }
    } catch(e) {
      showToast('Lỗi kết nối', true);
    }
  };

  /* ADD NEW BUTTON -> GO TO TRAIN */
  document.getElementById('addNewBtn').addEventListener('click', () => {
    window.location.href = '/train';
  });

  /* FILTER & SEARCH (combined) */
  const filterTypeSelect = document.getElementById('filterTypeSelect');
  const searchInput = document.getElementById('searchInput');

  function filterCards() {
    const activeTab = document.querySelector('.tab.active')?.dataset.tab;
    const container = activeTab ? document.getElementById(`tab-${activeTab}`) : document.querySelector('.tab-content:not([style*="none"])');
    if (!container) return;

    const searchKeyword = searchInput.value.toLowerCase();
    const filterType = filterTypeSelect.value;

    container.querySelectorAll('.img-card').forEach(card => {
      const name = card.querySelector('.img-name')?.textContent.toLowerCase() || '';
      const subtype = card.dataset.subtype || '';
      const matchesSearch = name.includes(searchKeyword);
      const matchesType = (filterType === 'all') || (subtype === filterType);
      card.style.display = (matchesSearch && matchesType) ? '' : 'none';
    });
  }

  filterTypeSelect.addEventListener('change', filterCards);
  searchInput.addEventListener('input', filterCards);

  /* LAZY LOADING THUMBNAILS */
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target;
        const filePath = img.dataset.file;
        if (filePath && !img.src.includes('/static/thumbnails/')) {
          fetch(`/archive/api/thumbnail?file=${encodeURIComponent(filePath)}`)
            .then(res => res.json())
            .then(data => {
              if (data.thumb_url) img.src = data.thumb_url;
            })
            .catch(() => {});
        }
        observer.unobserve(img);
      }
    });
  }, { rootMargin: '200px' });

  function observeThumbnails(container) {
    container.querySelectorAll('.img-thumb-img[data-file]').forEach(img => observer.observe(img));
  }
  observeThumbnails(document);

  /* MODAL DELETE BUTTON */
  document.getElementById('deleteModalBtn').addEventListener('click', () => {
    if (currentFile.filepath) {
      deleteFile(currentFile.filepath, currentFile.type);
      closeModal();
    }
  });
});