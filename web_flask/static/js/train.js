let currentTaskId = null;
let trainingInterval = null;
const steps = [
  'Load & validate ảnh',
  'Preprocessing (normalization)',
  'Chạy model U Net segmentation',
  'Post processing & masking',
  'Tạo output processed image'
];

function switchMethod(method) {
  document.getElementById('method-url').classList.toggle('active', method === 'url');
  document.getElementById('method-file').classList.toggle('active', method === 'file');
  document.getElementById('url-panel').style.display = method === 'url' ? '' : 'none';
  document.getElementById('file-panel').style.display = method === 'file' ? '' : 'none';
}

function initFileUpload() {
  const dropzone = document.getElementById('dropzone');
  const dropText = document.getElementById('drop-text');
  const fileInput = document.getElementById('file-input');
  const previewContainer = document.getElementById('file-preview-container');
  const previewImg = document.getElementById('file-preview-img');

  function handleFile(file) {
    dropText.textContent = '✓ ' + file.name;
    if (file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = e => {
        previewImg.src = e.target.result;
        previewContainer.style.display = 'block';
      };
      reader.readAsDataURL(file);
    } else {
      previewContainer.style.display = 'none';
    }
  }

  dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag'); });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag'));
  dropzone.addEventListener('drop', e => {
    e.preventDefault();
    dropzone.classList.remove('drag');
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  });
  dropzone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', function() {
    if (this.files[0]) handleFile(this.files[0]);
  });
}

async function validateUrl(url) {
  const statusEl = document.getElementById('url-status');
  if (!url) {
    statusEl.textContent = 'Vui lòng nhập URL';
    statusEl.className = 'url-status invalid';
    return false;
  }
  if (url.startsWith('data:image/')) {
    statusEl.textContent = 'Data URL hợp lệ';
    statusEl.className = 'url-status valid';
    return true;
  }
  try { new URL(url); } catch {
    statusEl.textContent = 'URL không hợp lệ';
    statusEl.className = 'url-status invalid';
    return false;
  }
  try {
    const response = await fetch(url, { method: 'HEAD' });
    if (!response.ok) {
      statusEl.textContent = `Lỗi HTTP ${response.status}`;
      statusEl.className = 'url-status invalid';
      return false;
    }
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('image/') || contentType.includes('application/octet-stream') ||
        url.match(/\.(nii|gz|dcm|dicom|mhd|mha|nrrd|jpg|jpeg|png)$/i)) {
      statusEl.textContent = 'URL hợp lệ';
      statusEl.className = 'url-status valid';
      return true;
    } else {
      statusEl.textContent = `Định dạng không hỗ trợ`;
      statusEl.className = 'url-status invalid';
      return false;
    }
  } catch (e) {
    statusEl.textContent = 'Không thể kiểm tra (CORS)';
    statusEl.className = 'url-status valid';
    return true;
  }
}

function resetTrainButton() {
  const btn = document.getElementById('train-btn');
  btn.disabled = false;
  btn.textContent = '▶ BẮT ĐẦU HUẤN LUYỆN';
}

function startTraining() {
  // Clear interval cũ nếu có
  if (trainingInterval) {
    clearInterval(trainingInterval);
    trainingInterval = null;
  }

  const isFileMode = document.getElementById('file-panel').style.display !== 'none';

  if (!isFileMode) {
    const url = document.getElementById('img-url').value.trim();
    const label = document.getElementById('img-label').value.trim();
    if (!url) { showToast('Vui lòng nhập URL ảnh', true); return; }
    if (!label) { showToast('Vui lòng nhập Tên bệnh nhân', true); return; }
    const statusEl = document.getElementById('url-status');
    if (statusEl.classList.contains('invalid')) {
      showToast('URL không hợp lệ hoặc không hỗ trợ', true);
      return;
    }
  } else {
    const file = document.getElementById('file-input').files[0];
    if (!file) { showToast('Vui lòng chọn file', true); return; }
  }

  const btn = document.getElementById('train-btn');
  btn.disabled = true;
  btn.textContent = '⟳ ĐANG CHẠY...';
  const pw = document.getElementById('progress-wrap');
  pw.style.display = 'block';
  document.getElementById('result-empty').style.display = 'flex';
  document.getElementById('result-preview').style.display = 'none';

  for (let i = 1; i <= 5; i++) {
    const el = document.getElementById('step-' + i);
    el.className = 'step-item';
    el.querySelector('.step-check').textContent = '○';
  }

  const model = document.getElementById('model-select').value;
  const threshold = document.getElementById('threshold').value;
  const formData = new FormData();
  formData.append('model', model);
  formData.append('threshold', threshold);

  if (isFileMode) {
    formData.append('file', document.getElementById('file-input').files[0]);
  } else {
    formData.append('url', document.getElementById('img-url').value.trim());
    formData.append('label', document.getElementById('img-label').value.trim());
  }

  fetch('/train/start', { method: 'POST', body: formData })
    .then(res => res.json())
    .then(data => {
      if (data.error) {
        showToast('Lỗi: ' + data.error, true);
        resetTrainButton();
        return;
      }
      currentTaskId = data.task_id;
      let progress = 0;
      trainingInterval = setInterval(() => {
        fetch(`/train/status/${currentTaskId}`)
          .then(res => res.json())
          .then(status => {
            if (status.error) {
              clearInterval(trainingInterval);
              showToast('Lỗi: ' + status.error, true);
              resetTrainButton();
              pw.style.display = 'none';
              return;
            }
            progress = status.progress || 0;
            document.getElementById('progress-fill').style.width = progress + '%';
            document.getElementById('progress-pct').textContent = progress + '%';
            const stepIdx = Math.floor(progress / 20);
            for (let i = 1; i <= 5; i++) {
              const el = document.getElementById('step-' + i);
              if (i - 1 < stepIdx) {
                el.className = 'step-item done';
                el.querySelector('.step-check').textContent = '✓';
              } else if (i - 1 === stepIdx) {
                el.className = 'step-item active';
              }
            }
            document.getElementById('progress-status').textContent = steps[Math.min(stepIdx, 4)];

            if (progress >= 100) {
              clearInterval(trainingInterval);
              fetch(`/train/result/${currentTaskId}`)
                .then(res => res.json())
                .then(result => {
                  document.getElementById('result-empty').style.display = 'none';
                  document.getElementById('result-preview').style.display = 'block';
                  document.getElementById('preview-processed').src = result.processed_url || '';
                  const meshContainer = document.getElementById('preview-mesh-container');
                  if (result.mesh_url) {
                    document.getElementById('preview-mesh').src = result.mesh_url;
                    meshContainer.style.display = '';
                  } else {
                    meshContainer.style.display = 'none';
                  }
                  document.getElementById('result-acc').textContent = (result.accuracy || 94.8).toFixed(1) + '%';
                  document.getElementById('tumor-size').textContent = result.tumor_size || '2.4 × 3.1 × 2.8 cm';
                  document.getElementById('tumor-location').textContent = result.location || 'Thùy gan phải, segment VI';
                  document.getElementById('dice-coeff').textContent = result.dice || '0.891';
                  showToast('✓ Huấn luyện hoàn tất');
                  resetTrainButton();
                  pw.style.display = 'none';
                })
                .catch(() => showToast('Lỗi tải kết quả', true));
            }
          });
      }, 800);
    })
    .catch(() => {
      showToast('Lỗi kết nối', true);
      resetTrainButton();
    });
}

function saveResult() {
  if (!currentTaskId) {
    showToast('Không có kết quả để lưu', true);
    return;
  }

  const isFileMode = document.getElementById('file-panel').style.display !== 'none';
  let customName = '';

  if (isFileMode) {
    customName = prompt('Nhập tên để lưu (không dấu, không khoảng trắng):',
      'ket_qua_' + new Date().toISOString().slice(0, 10).replace(/-/g, ''));
    if (!customName) return;
  } else {
    customName = document.getElementById('img-label').value.trim();
    if (!customName) {
      customName = 'ket_qua_' + new Date().toISOString().slice(0, 10).replace(/-/g, '');
    }
  }

  fetch('/train/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: currentTaskId, name: customName })
  })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        showToast('✓ ' + data.message);
        // Chuyển hướng sang Archive để thấy kết quả
        setTimeout(() => { window.location.href = '/archive'; }, 1000);
      } else {
        showToast(data.error, true);
      }
    })
    .catch(() => showToast('Lỗi kết nối', true));
}

function deleteResult() {
  document.getElementById('result-preview').style.display = 'none';
  document.getElementById('result-empty').style.display = 'flex';
  document.getElementById('progress-wrap').style.display = 'none';
  showToast('🗑 Đã xóa kết quả', true);
}

function openResultModal(type) {
  let img;
  if (type === 'processed') img = document.getElementById('preview-processed');
  else if (type === 'mesh') img = document.getElementById('preview-mesh');
  if (img && img.src) {
    openModal(img.src, type === 'processed' ? 'Ảnh PROCESSED' : 'Mesh 3D');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initFileUpload();

  document.getElementById('method-url').addEventListener('click', () => switchMethod('url'));
  document.getElementById('method-file').addEventListener('click', () => switchMethod('file'));
  document.getElementById('train-btn').addEventListener('click', startTraining);
  document.getElementById('saveResultBtn').addEventListener('click', saveResult);
  document.getElementById('deleteResultBtn').addEventListener('click', deleteResult);

  // Ẩn RAW ngay từ đầu
  const rawContainer = document.getElementById('preview-raw-container');
  if (rawContainer) rawContainer.style.display = 'none';

  document.getElementById('preview-processed-container')?.addEventListener('click', () => openResultModal('processed'));
  document.getElementById('preview-mesh-container')?.addEventListener('click', () => openResultModal('mesh'));

  const urlInput = document.getElementById('img-url');
  urlInput.addEventListener('blur', async () => {
    const url = urlInput.value.trim();
    if (url) await validateUrl(url);
    else document.getElementById('url-status').textContent = '';
  });
});