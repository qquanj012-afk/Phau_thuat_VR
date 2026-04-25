/* ARCHIVE PAGE LOGIC */
document.addEventListener('DOMContentLoaded', function() {
  /* TAB SWITCHING */
  const tabs = document.querySelectorAll('.tab');
  const tabRaw = document.getElementById('tab-raw');
  const tabProcessed = document.getElementById('tab-processed');
  const tabMeshes = document.getElementById('tab-meshes');
  const tabTrash = document.getElementById('tab-trash');

  // Xác định tab đang active lúc load trang
  const activeTabOnLoad = document.querySelector('.tab.active')?.dataset.tab || 'raw';
  updateFilterCounts(activeTabOnLoad);

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
      filterCards();
      updateFilterCounts(tabId);
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

  /* ─────────────────────────────────────────────────────────────
   * THREE.JS OBJ VIEWER
   * FIX BUG 1: model-viewer không được import → không render gì
   * FIX BUG 2: model-viewer không đọc .obj, chỉ đọc .gltf/.glb
   * FIX BUG 3: không có cleanup → memory leak
   * ───────────────────────────────────────────────────────────── */
  let threeCleanup = null;   // FIX BUG 3: lưu hàm cleanup
  let compareCleanup = null;   // Dọn dẹp Three.js khi đóng modal so sánh

  function initOBJViewer(container, objUrl, filename, onCleanup) {
    // Cleanup scene cũ nếu có (FIX BUG 3)
    if (threeCleanup) { threeCleanup(); threeCleanup = null; }

    // Wrapper div
    const wrapper = document.createElement('div');
    wrapper.style.cssText = [
      'width:100%', 'height:70vh', 'position:relative',
      'background:#0d1117', 'border-radius:8px', 'overflow:hidden'
    ].join(';');
    container.appendChild(wrapper);

    // Loading overlay
    const loading = document.createElement('div');
    loading.style.cssText = [
      'position:absolute', 'inset:0', 'display:flex', 'flex-direction:column',
      'align-items:center', 'justify-content:center',
      'color:#00d4aa', 'font-family:monospace', 'font-size:0.85rem',
      'background:#0d1117', 'z-index:10', 'gap:12px'
    ].join(';');
    loading.innerHTML = `
      <div style="font-size:2rem">◈</div>
      <div>Đang tải mesh 3D…</div>
      <div style="color:#5a6280;font-size:0.75rem">${filename}</div>
    `;
    wrapper.appendChild(loading);

    // Hint controls (hiện sau khi load xong)
    const hint = document.createElement('div');
    hint.style.cssText = [
      'position:absolute', 'bottom:12px', 'left:50%', 'transform:translateX(-50%)',
      'color:#5a6280', 'font-family:monospace', 'font-size:0.72rem',
      'background:rgba(0,0,0,0.6)', 'padding:4px 12px', 'border-radius:20px',
      'pointer-events:none', 'opacity:0', 'transition:opacity 0.5s', 'z-index:5'
    ].join(';');
    hint.textContent = '🖱 Kéo để xoay · Scroll để zoom · Chuột phải để di chuyển';
    wrapper.appendChild(hint);

    /* ── Scene ── */
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0d1117);

    /* ── Camera ── */
    const W = wrapper.clientWidth || 600;
    const H = wrapper.clientHeight || 400;
    const camera = new THREE.PerspectiveCamera(45, W / H, 0.001, 2000);
    camera.position.set(0, 0, 5);

    /* ── Renderer ── */
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(W, H);
    renderer.shadowMap.enabled = true;
    wrapper.appendChild(renderer.domElement);

    /* ── Lights ── */
    scene.add(new THREE.AmbientLight(0xffffff, 0.7));

    const dir1 = new THREE.DirectionalLight(0xffffff, 0.9);
    dir1.position.set(3, 5, 5);
    scene.add(dir1);

    const dir2 = new THREE.DirectionalLight(0x00d4aa, 0.4);
    dir2.position.set(-4, -2, -3);
    scene.add(dir2);

    const rim = new THREE.DirectionalLight(0xffffff, 0.3);
    rim.position.set(0, -5, -5);
    scene.add(rim);

    /* ── Controls ── */
    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 1.2;
    controls.minDistance = 0.1;
    controls.maxDistance = 500;

    // Dừng auto-rotate khi người dùng tương tác
    renderer.domElement.addEventListener('pointerdown', () => {
      controls.autoRotate = false;
    });

   /* ── Default material (dùng khi không có MTL) ── */
    const defaultMat = new THREE.MeshPhongMaterial({
      color: 0x00d4aa,
      specular: 0x224433,
      shininess: 35,
      transparent: true,
      opacity: 0.92,
      side: THREE.DoubleSide
    });

    /* ── Hàm đặt object vào tâm scene và tự động zoom vừa màn hình ── */
    function centerAndFit(object) {
      const box = new THREE.Box3().setFromObject(object);
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z);

      // Đưa về tâm (0,0,0)
      object.position.sub(center);

      // Đặt camera vừa nhìn thấy toàn bộ mesh
      const fov = camera.fov * (Math.PI / 180);
      const fitDist = (maxDim / 2) / Math.tan(fov / 2) * 1.6;
      camera.position.set(0, 0, fitDist);
      controls.target.set(0, 0, 0);
      camera.near = fitDist / 100;
      camera.far = fitDist * 10;
      camera.updateProjectionMatrix();
      controls.update();
    }

    /* ── Load OBJ (+ thử MTL cùng thư mục) ── */
    function loadWithMaterials(materials) {
      const objLoader = new THREE.OBJLoader();
      if (materials) {
        materials.preload();
        objLoader.setMaterials(materials);
      }

      objLoader.load(
        objUrl,
        (object) => {
          // Nếu không có MTL, gán material mặc định màu teal
          if (!materials) {
            object.traverse(child => {
              if (child.isMesh) child.material = defaultMat;
            });
          }

          centerAndFit(object);
          scene.add(object);

          // Ẩn loading, hiện hint
          loading.style.opacity = '0';
          setTimeout(() => loading.remove(), 400);
          hint.style.opacity = '1';
          setTimeout(() => { hint.style.opacity = '0'; }, 4000);
        },
        (xhr) => {
          // Tiến trình load
          if (xhr.total > 0) {
            const pct = Math.round((xhr.loaded / xhr.total) * 100);
            const pctEl = loading.querySelector('div:nth-child(2)');
            if (pctEl) pctEl.textContent = `Đang tải mesh 3D… ${pct}%`;
          }
        },
        () => {
          // OBJ load thất bại
          loading.innerHTML = `
            <div style="font-size:2rem">❌</div>
            <div style="color:#ff4d6d">Không thể tải file OBJ</div>
            <div style="color:#5a6280;font-size:0.75rem">${objUrl}</div>
          `;
        }
      );
    }

    // Thử load MTL trước (cùng thư mục, cùng tên file)
    const mtlUrl = objUrl.replace(/\.obj$/i, '.mtl');
    const mtlLoader = new THREE.MTLLoader();
    mtlLoader.load(
      mtlUrl,
      (materials) => loadWithMaterials(null),  // Có MTL
      null,
      () => loadWithMaterials(null)                  // Không có MTL → dùng default
    );

    /* ── Animation loop ── */
    let animId;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    /* ── Responsive resize ── */
    const onResize = () => {
      if (!wrapper.isConnected) return;
      const w = wrapper.clientWidth;
      const h = wrapper.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', onResize);

    /* ── FIX BUG 3: Cleanup khi đóng modal ── */
        // Cleanup
    const cleanup = () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', onResize);
      controls.dispose();
      scene.traverse(obj => {
        if (obj.isMesh) {
          obj.geometry?.dispose();
          if (Array.isArray(obj.material)) {
            obj.material.forEach(m => m.dispose());
          } else {
            obj.material?.dispose();
          }
        }
      });
      renderer.dispose();
    };

    if (onCleanup) {
      onCleanup(cleanup);
    } else {
      threeCleanup = cleanup;
    }
  }

  /* ─────────────────────────────────────────────────────────────
   * MODAL STATE
   * ───────────────────────────────────────────────────────────── */
  let currentFile = { filepath: '', type: '', url: '' };

  window.openModal = function(name, type, date, size, url, thumbUrl, filepath) {
    currentFile = { filepath, type, url };
    document.getElementById('modal-title').textContent = name;
    document.getElementById('modal-meta').textContent = `${date} · ${size}`;

    const modalBody = document.querySelector('.modal-body');
    const ext = name.toLowerCase().split('.').pop();
    const isMesh = ['obj', 'stl', 'ply', 'glb', 'gltf'].includes(ext) || type === 'meshes';

    // Xóa nội dung cũ + cleanup Three.js nếu có
    modalBody.innerHTML = '';
    if (threeCleanup) { threeCleanup(); threeCleanup = null; }

    if (isMesh && url && url !== '#') {
      /* ── 3D Viewer: dùng Three.js (KHÔNG dùng model-viewer) ── */
      initOBJViewer(modalBody, url, name, null);

      // Ẩn nút zoom 2D (không cần cho 3D)
      document.querySelectorAll('.modal-controls .modal-btn').forEach(btn => {
        if (btn.id !== 'modalCloseBtn') btn.style.display = 'none';
      });

    } else if (isMesh && (!url || url === '#')) {
      /* Mesh nhưng chưa có URL (trash) */
      modalBody.innerHTML = `
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                    height:40vh;color:#5a6280;font-family:monospace;gap:12px;">
          <div style="font-size:3rem;color:#00d4aa">◈</div>
          <div>${name}</div>
          <div style="font-size:0.75rem">File mesh không khả dụng để xem (đang trong thùng rác)</div>
        </div>`;
      document.querySelectorAll('.modal-controls .modal-btn').forEach(btn => {
        if (btn.id !== 'modalCloseBtn') btn.style.display = 'none';
      });

    } else {
      /* ── Ảnh 2D ── */
      const img = document.createElement('img');
      img.src = thumbUrl;
      img.alt = name;
      img.className = 'modal-img';
      img.id = 'modal-img';
      img.style.transform = 'scale(1)';
      img.style.cursor = 'grab';
      modalBody.appendChild(img);

      if (typeof currentZoom !== 'undefined') currentZoom = 1;
      if (typeof translateX !== 'undefined') translateX = 0;
      if (typeof translateY !== 'undefined') translateY = 0;

      // Hiện lại nút zoom
      document.querySelectorAll('.modal-controls .modal-btn').forEach(btn => {
        if (btn.id !== 'modalCloseBtn') btn.style.display = 'flex';
      });
    }

    document.getElementById('modal').classList.add('show');
  };

  /* Hook đóng modal → cleanup Three.js */
  const modalEl = document.getElementById('modal');
  if (modalEl) {
    const observer = new MutationObserver(() => {
      if (!modalEl.classList.contains('show')) {
        if (threeCleanup) { threeCleanup(); threeCleanup = null; }
      }
    });
    observer.observe(modalEl, { attributes: true, attributeFilter: ['class'] });
  }

  /* ─────────────────────────────────────────────────────────────
   * ATTACH CARD EVENTS
   * ───────────────────────────────────────────────────────────── */
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

      card.querySelector('.compare-btn')?.addEventListener('click', (e) => {
        e.stopPropagation();
        openCompareModal(card);
      });

      card.querySelector('.del-btn')?.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteFile(filepath, type);
      });
    });
  }

  attachCardEvents(document);

  /* Mở modal so sánh từ ảnh đang xem trong modal thường */
window.openCompareFromModal = function() {
  // Kiểm tra xem có file hiện tại không (được lưu khi openModal)
  if (!currentFile || !currentFile.filepath) {
    showToast('Không có file để so sánh', true);
    return;
  }

  // Tìm thẻ card gốc dựa vào filepath
  const card = document.querySelector(`.img-card[data-filepath="${currentFile.filepath}"]`);
  if (!card) {
    showToast('Không tìm thấy thẻ ảnh gốc', true);
    return;
  }

  // Đóng modal thường
  closeModal();

  // Mở modal so sánh (hàm openCompareModal đã có từ trước)
  openCompareModal(card);
};

  /* ─────────────────────────────────────────────────────────────
   * FILE DELETION
   * ───────────────────────────────────────────────────────────── */
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

  /* ─────────────────────────────────────────────────────────────
   * TRASH FUNCTIONS
   * ───────────────────────────────────────────────────────────── */
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

      const liverCount = items.filter(it => it.subtype === 'liver').length;
      const tumorCount = items.filter(it => it.subtype === 'tumor').length;
      updateFilterCountsWithData(liverCount + tumorCount, liverCount, tumorCount);
    } catch(e) {
      grid.innerHTML = '<div style="color:var(--danger);padding:20px;">Lỗi tải thùng rác</div>';
    }
  }

  function createTrashCard(item) {
    const div = document.createElement('div');
    div.className = 'img-card';
    div.dataset.name = item.name;
    div.dataset.type = item.original_type;
    div.dataset.subtype = item.subtype || '';
    div.dataset.date = item.date_str;
    div.dataset.size = item.size;
    div.dataset.url = '#';
    div.dataset.thumb = item.thumb;
    div.dataset.filepath = item.file_path;
    div.dataset.originalType = item.original_type;

    let typeIcon = '📄', typeLabel = 'Raw';
    if (item.original_type === 'processed') { typeIcon = '⚙️'; typeLabel = 'Processed'; }
    else if (item.original_type === 'meshes') { typeIcon = '◈'; typeLabel = 'Mesh'; }

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
      e.stopPropagation(); restoreFile(item.file_path);
    });
    div.querySelector('.permanent-btn').addEventListener('click', (e) => {
      e.stopPropagation(); permanentDelete(item.file_path);
    });
    return div;
  }

  window.restoreFile = async function(filepath) {
    if (!confirm(`Khôi phục file này?`)) return;
    try {
      const res = await fetch(window.TRASH_API.restore + encodeURIComponent(filepath), { method: 'POST' });
      const data = await res.json();
      if (data.success) { showToast('Đã khôi phục'); setTimeout(() => location.reload(), 500); }
      else showToast(data.error, true);
    } catch(e) { showToast('Lỗi kết nối', true); }
  };

  window.permanentDelete = async function(filepath) {
    if (!confirm(`Xóa vĩnh viễn? Hành động không thể hoàn tác!`)) return;
    try {
      const res = await fetch(window.TRASH_API.permanent + encodeURIComponent(filepath), { method: 'DELETE' });
      const data = await res.json();
      if (data.success) { showToast('Đã xóa vĩnh viễn'); setTimeout(() => location.reload(), 500); }
      else showToast(data.error, true);
    } catch(e) { showToast('Lỗi kết nối', true); }
  };

  /* ─────────────────────────────────────────────────────────────
   * NAVIGATE TO TRAIN
   * ───────────────────────────────────────────────────────────── */
  document.getElementById('addNewBtn').addEventListener('click', () => {
    window.location.href = '/train';
  });

  /* ─────────────────────────────────────────────────────────────
   * FILTER & SEARCH
   * ───────────────────────────────────────────────────────────── */
  const filterTypeSelect = document.getElementById('filterTypeSelect');
  const searchInput = document.getElementById('searchInput');

  function filterCards() {
    const activeTab = document.querySelector('.tab.active')?.dataset.tab;
    const container = activeTab ? document.getElementById(`tab-${activeTab}`) : null;
    if (!container) return;

    const keyword = searchInput.value.toLowerCase();
    const filterType = filterTypeSelect.value;

    container.querySelectorAll('.img-card').forEach(card => {
      const name = card.querySelector('.img-name')?.textContent.toLowerCase() || '';
      const subtype = card.dataset.subtype || '';
      const matchSearch = name.includes(keyword);
      const matchType = (filterType === 'all') || (subtype === filterType);
      card.style.display = (matchSearch && matchType) ? '' : 'none';
    });
  }

  filterTypeSelect.addEventListener('change', filterCards);
  searchInput.addEventListener('input', filterCards);

  /* ─────────────────────────────────────────────────────────────
   * UPDATE FILTER COUNTS PER TAB
   * ───────────────────────────────────────────────────────────── */
  function updateFilterCountsWithData(total, liver, tumor) {
    const filterSelect = document.getElementById('filterTypeSelect');
    if (!filterSelect) return;
    filterSelect.querySelector('option[value="all"]').textContent = `Tất cả (${total})`;
    filterSelect.querySelector('option[value="liver"]').textContent = `Gan (${liver})`;
    filterSelect.querySelector('option[value="tumor"]').textContent = `Khối u (${tumor})`;
  }

  function updateFilterCounts(tabId) {
  const counts = window.SUBTYPE_COUNTS[tabId] || { liver: 0, tumor: 0 };
  const total = counts.liver + counts.tumor;
  updateFilterCountsWithData(total, counts.liver, counts.tumor);
  }

  /* ─────────────────────────────────────────────────────────────
   * LAZY LOADING THUMBNAILS
   * ───────────────────────────────────────────────────────────── */
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target;
        const filePath = img.dataset.file;
        if (filePath && !img.src.includes('/static/thumbnails/')) {
          fetch(`/archive/api/thumbnail?file=${encodeURIComponent(filePath)}`)
            .then(res => res.json())
            .then(data => { if (data.thumb_url) img.src = data.thumb_url; })
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

  /* ─────────────────────────────────────────────────────────────
   * MODAL DELETE BUTTON
   * ───────────────────────────────────────────────────────────── */
  document.getElementById('deleteModalBtn')?.addEventListener('click', () => {
    if (currentFile.filepath) { deleteFile(currentFile.filepath, currentFile.type); closeModal(); }
  });

    /* COMPARE FUNCTIONALITY */
  async function openCompareModal(card) {
    const name = card.dataset.name;
    const filepath = card.dataset.filepath;
    const url = card.dataset.url;
    const type = card.dataset.type;
    const isMesh = name.toLowerCase().endsWith('.obj') || type === 'meshes';

    const modal = document.getElementById('compareModal');
    document.getElementById('compare-title').textContent = `So sánh: ${name}`;

    const leftPane = document.getElementById('left-pane');
    const rightPane = document.getElementById('right-pane');
    leftPane.innerHTML = '';
    rightPane.innerHTML = '';
    if (compareCleanup) { compareCleanup(); compareCleanup = null; }

    // Hiển thị ảnh hiện tại bên trái
    renderPaneContent(leftPane, name, url, isMesh, filepath);

    // Gọi API tìm file ghép cặp
    try {
      const res = await fetch('/archive/find_pair', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: filepath })
      });
      const data = await res.json();
      if (data.error) {
        rightPane.innerHTML = `<div style="color:var(--text3);">⚠️ ${data.error}</div>`;
      } else {
        const isPairMesh = data.name.toLowerCase().endsWith('.obj');
        renderPaneContent(rightPane, data.name, data.url, isPairMesh, data.subpath);
      }
    } catch (err) {
      rightPane.innerHTML = `<div style="color:var(--danger);">Lỗi kết nối</div>`;
    }

    modal.classList.add('show');
  }

  function renderPaneContent(container, name, url, isMesh, filepath) {
    if (isMesh && url && url !== '#') {
      // Dùng Three.js viewer, truyền callback cleanup
      initOBJViewer(container, url, name, (cleanup) => { compareCleanup = cleanup; });
    } else if (isMesh) {
      container.innerHTML = `<div style="color:var(--text3);">Mesh không khả dụng</div>`;
    } else {
      // Ảnh 2D: gọi API thumbnail để lấy ảnh PNG
      fetch(`/archive/api/thumbnail?file=${encodeURIComponent(filepath)}`)
        .then(res => res.json())
        .then(data => {
          const img = document.createElement('img');
          img.src = data.thumb_url || url;
          img.alt = name;
          container.appendChild(img);
        })
        .catch(() => {
          const img = document.createElement('img');
          img.src = url;
          img.alt = name;
          container.appendChild(img);
        });
    }
  }

  function closeCompareModal() {
    document.getElementById('compareModal').classList.remove('show');
    if (compareCleanup) { compareCleanup(); compareCleanup = null; }
  }

  // Gắn sự kiện cho nút đóng modal so sánh nếu có
  document.getElementById('compareCloseBtn')?.addEventListener('click', closeCompareModal);
});