let currentTaskId = null;
let trainingInterval = null;
window.currentMode = 'url'; // 'url' hoặc 'file'

const steps = [
  'Load & validate ảnh',
  'Preprocessing (normalization)',
  'Chạy model U Net segmentation',
  'Post processing & masking',
  'Tạo output processed image'
];

// Chuyển đổi chế độ nhập liệu
function switchMethod(method) {
  window.currentMode = method;
  document.getElementById('method-url').classList.toggle('active', method === 'url');
  document.getElementById('method-file').classList.toggle('active', method === 'file');
  document.getElementById('url-panel').classList.toggle('hidden', method !== 'url');
  document.getElementById('file-panel').classList.toggle('hidden', method !== 'file');
}

// Khởi tạo drag & drop + click chọn file
function initFileUpload() {
  function setupDropzone(dropzoneId, dropTextId, fileInputId, previewContainerId, previewImgId) {
    const dropzone = document.getElementById(dropzoneId);
    const dropText = document.getElementById(dropTextId);
    const fileInput = document.getElementById(fileInputId);
    const previewContainer = document.getElementById(previewContainerId);
    const previewImg = document.getElementById(previewImgId);

    if (!dropzone || !dropText || !fileInput) return;

    // Ngăn chặn hành vi mặc định trên tất cả phần tử con
    const allElements = [dropzone, ...dropzone.querySelectorAll('*')];
    allElements.forEach(el => {
      el.addEventListener('dragover', e => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('drag');
      });
      el.addEventListener('dragleave', e => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('drag');
      });
      el.addEventListener('drop', e => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('drag');
        const file = e.dataTransfer.files[0];
        if (file) {
          // Gán file vào input để form có thể đọc được
          const dt = new DataTransfer();
          dt.items.add(file);
          fileInput.files = dt.files;
          handleFile(file, dropText, previewContainer, previewImg);
        }
      });
    });

    // Click mở hộp thoại chọn file
    dropzone.addEventListener('click', () => fileInput.click());

    // Khi chọn file qua hộp thoại
    fileInput.addEventListener('change', function() {
      if (this.files[0]) {
        handleFile(this.files[0], dropText, previewContainer, previewImg);
      }
    });
  }

  async function handleFile(file, dropText, previewContainer, previewImg) {
    dropText.textContent = '✓ ' + file.name;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch('/train/preview', { method: 'POST', body: formData });
      const data = await res.json();
      if (data.thumb_url && previewImg) {
        previewImg.src = data.thumb_url;
        if (previewContainer) previewContainer.style.display = 'block';
      }
    } catch (e) {
      console.error('Preview failed', e);
      if (previewContainer) previewContainer.style.display = 'none';
    }
  }

  setupDropzone('dropzone-ct', 'drop-text-ct', 'file-input-ct', 'file-preview-container-ct', 'file-preview-img-ct');
  setupDropzone('dropzone-mask', 'drop-text-mask', 'file-input-mask', 'file-preview-container-mask', 'file-preview-img-mask');
}

// Validate URL
async function validateUrl(url) {
  const statusEl = document.getElementById('url-status');
  if (!url) {
    statusEl.textContent = 'Vui lòng nhập URL';
    statusEl.className = 'url-status invalid';
    return false;
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

// Huấn luyện
function startTraining() {
  // Clear interval cũ nếu có
  if (trainingInterval) {
    clearInterval(trainingInterval);
    trainingInterval = null;
  }

  const isFileMode = window.currentMode === 'file';
  const formData = new FormData();
  formData.append('model', document.getElementById('model-select').value);
  formData.append('threshold', document.getElementById('threshold').value);

  if (isFileMode) {
    const ctInput = document.getElementById('file-input-ct');
    const ctFile = ctInput.files[0];
    if (!ctFile) { showToast('Vui lòng chọn file CT', true); return; }
    formData.append('file', ctFile);

    const maskInput = document.getElementById('file-input-mask');
    if (maskInput.files[0]) formData.append('mask', maskInput.files[0]);
  } else {
    const url = document.getElementById('img-url').value.trim();
    const label = document.getElementById('img-label').value.trim();
    if (!url) { showToast('Vui lòng nhập URL ảnh CT', true); return; }
    if (!label) { showToast('Vui lòng nhập Tên bệnh nhân', true); return; }

    const statusEl = document.getElementById('url-status');
    if (statusEl.classList.contains('invalid')) {
      showToast('URL không hợp lệ hoặc không hỗ trợ', true);
      return;
    }

    formData.append('url', url);
    formData.append('label', label);

    const maskUrl = document.getElementById('mask-url').value.trim();
    if (maskUrl) formData.append('mask_url', maskUrl);
  }

  // Reset giao diện
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

function resetTrainButton() {
  const btn = document.getElementById('train-btn');
  btn.disabled = false;
  btn.textContent = '▶ BẮT ĐẦU HUẤN LUYỆN';
}

document.addEventListener('DOMContentLoaded', () => {
  initFileUpload();

  document.getElementById('method-url').addEventListener('click', () => switchMethod('url'));
  document.getElementById('method-file').addEventListener('click', () => switchMethod('file'));
  document.getElementById('train-btn').addEventListener('click', startTraining);
  document.getElementById('saveResultBtn').addEventListener('click', saveResult);
  document.getElementById('deleteResultBtn').addEventListener('click', deleteResult);

  document.getElementById('preview-processed-container')?.addEventListener('click', () => openResultModal('processed'));
  document.getElementById('preview-mesh-container')?.addEventListener('click', () => openResultModal('mesh'));

  const urlInput = document.getElementById('img-url');
  if (urlInput) {
    urlInput.addEventListener('blur', async () => {
      const url = urlInput.value.trim();
      if (url) await validateUrl(url);
      else document.getElementById('url-status').textContent = '';
    });
  }
});