import os
import uuid
import shutil
import threading
import requests
from datetime import datetime
from pathlib import Path

from flask import Blueprint, render_template, request, jsonify
from werkzeug.utils import secure_filename

from web_flask.utils.image_converter import generate_thumbnail
from web_flask.utils.pipeline import run_pipeline_with_progress

train_bp = Blueprint('train', __name__, template_folder='../../templates')

BASE_DIR      = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR      = BASE_DIR / 'data'
TEMP_UPLOAD   = DATA_DIR / 'temp' / 'uploads'
TEMP_OUTPUT   = DATA_DIR / 'temp' / 'output'
RAW_DIR       = DATA_DIR / 'raw'   / 'liver'
PROCESSED_DIR = DATA_DIR / 'processed' / 'liver'
MESH_DIR      = DATA_DIR / 'meshes'

for d in (TEMP_UPLOAD, TEMP_OUTPUT, RAW_DIR, PROCESSED_DIR, MESH_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Task store (in-memory)
tasks: dict = {}

ALLOWED_EXTENSIONS = {'nii', 'gz', 'dcm'}


# Helpers
def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def download_from_url(url: str, save_path: str) -> None:
    """Tải file từ URL về đường dẫn chỉ định (streaming)."""
    response = requests.get(url, stream=True,
                            headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
    response.raise_for_status()
    with open(save_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


# Routes
@train_bp.route('/')
def train_page():
    return render_template('train.html')


@train_bp.route('/start', methods=['POST'])
def start_training():
    """Nhận file/URL, tạo task, khởi thread inference, trả về task_id ngay."""
    model     = request.form.get('model', 'liver')
    threshold = request.form.get('threshold', '0.85')
    label     = request.form.get('label', '').strip()
    task_id   = str(uuid.uuid4())
    model_type = 'liver' if 'liver' in model.lower() else 'tumor'

    input_path: Path | None = None
    mask_path:  Path | None = None
    filename:   str  | None = None

    # Chế độ Upload File
    if 'file' in request.files:
        file = request.files['file']
        if not file.filename:
            return jsonify({'error': 'Chưa chọn file'}), 400
        if not allowed_file(file.filename):
            return jsonify({'error': 'Chỉ hỗ trợ .nii, .nii.gz, .dcm'}), 400

        filename   = secure_filename(file.filename)
        input_path = TEMP_UPLOAD / f'{task_id}_{filename}'
        file.save(str(input_path))

        if 'mask' in request.files:
            mask_file = request.files['mask']
            if mask_file.filename and allowed_file(mask_file.filename):
                mask_path = TEMP_UPLOAD / f'{task_id}_mask_{secure_filename(mask_file.filename)}'
                mask_file.save(str(mask_path))

    # Chế độ URL Link
    else:
        url = request.form.get('url', '').strip()
        if not url:
            return jsonify({'error': 'Vui lòng nhập URL'}), 400
        if not label:
            return jsonify({'error': 'Vui lòng nhập tên bệnh nhân (nhãn)'}), 400

        base_name  = secure_filename(label.replace(' ', '_'))
        input_path = TEMP_UPLOAD / f'{task_id}_{base_name}.nii.gz'
        try:
            download_from_url(url, str(input_path))
        except Exception as e:
            return jsonify({'error': f'Lỗi tải URL: {e}'}), 400

        mask_url_str = request.form.get('mask_url', '').strip()
        if mask_url_str:
            mask_path = TEMP_UPLOAD / f'{task_id}_mask_{base_name}.nii.gz'
            try:
                download_from_url(mask_url_str, str(mask_path))
            except Exception as e:
                print(f"⚠️  Lỗi tải mask URL: {e}")
                mask_path = None

    if not input_path:
        return jsonify({'error': 'Không có file đầu vào'}), 400

    output_path = TEMP_OUTPUT / f'{task_id}_seg.nii.gz'

    # Tạo task
    tasks[task_id] = {
        'id':         task_id,
        'status':     'pending',
        'progress':   0,
        'filename':   filename or input_path.name,
        'label':      label,
        'created_at': datetime.now().isoformat(),
        'model':      model,
        'threshold':  threshold,
    }

    # Khởi thread — toàn bộ logic nằm trong pipeline.run_pipeline_with_progress
    thread = threading.Thread(
        target=run_pipeline_with_progress,
        args=(tasks[task_id], str(input_path), str(mask_path) if mask_path else None,
              str(output_path), model_type, threshold),
        daemon=True,
    )
    thread.start()

    return jsonify({'task_id': task_id, 'message': 'Inference started'})


@train_bp.route('/status/<task_id>')
def training_status(task_id: str):
    """Poll trạng thái & tiến trình của task."""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task không tồn tại'}), 404
    return jsonify({
        'progress': task.get('progress', 0),
        'status':   task.get('status', 'unknown'),
    })


@train_bp.route('/preview', methods=['POST'])
def preview_image():
    """Upload file tạm, trả về URL thumbnail để xem trước."""
    if 'file' not in request.files:
        return jsonify({'error': 'Không có file'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Chưa chọn file'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'Chỉ hỗ trợ .nii, .nii.gz, .dcm'}), 400

    temp_path = TEMP_UPLOAD / f'{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}'
    file.save(str(temp_path))
    return jsonify({'thumb_url': generate_thumbnail(str(temp_path))})


@train_bp.route('/result/<task_id>')
def training_result(task_id: str):
    """Trả về URL thumbnail kết quả (chỉ khi completed)."""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task không tồn tại'}), 404
    if task['status'] != 'completed':
        return jsonify({'error': 'Inference chưa hoàn tất'}), 400
    return jsonify(task.get('result', {}))


@train_bp.route('/save', methods=['POST'])
def save_result():
    """Lưu kết quả từ temp/ vào kho dữ liệu chính."""
    data        = request.get_json()
    task_id     = data.get('task_id')
    custom_name = data.get('name', '').strip()

    task = tasks.get(task_id)
    if not task or task['status'] != 'completed':
        return jsonify({'success': False, 'error': 'Task không hợp lệ hoặc chưa hoàn tất'}), 400

    if not custom_name:
        custom_name = task.get('label') or f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    safe_name = secure_filename(custom_name) or f"result_{task_id[:8]}"

    raw_dest       = RAW_DIR / 'imagesTr' / f'{safe_name}.nii.gz'
    processed_dest = PROCESSED_DIR / f'{safe_name}_seg.nii.gz'
    mesh_dest      = MESH_DIR / f'{safe_name}.obj'
    raw_dest.parent.mkdir(parents=True, exist_ok=True)

    # Kiểm tra trùng tên
    existing = [name for name, path in [('processed', processed_dest), ('meshes', mesh_dest)]
                if path.exists()]
    if existing:
        return jsonify({'success': False,
                        'error': f'Tên đã tồn tại trong: {", ".join(existing)}'}), 409

    try:
        # Raw (chỉ copy nếu chưa có)
        raw_src = task.get('temp_raw_path')
        if raw_src and not raw_dest.exists() and Path(raw_src).exists():
            shutil.copy2(raw_src, raw_dest)

        # Processed
        proc_src = task.get('temp_processed_path')
        if proc_src and Path(proc_src).exists():
            shutil.copy2(proc_src, processed_dest)

        # Mesh (tùy chọn)
        mesh_src = task.get('temp_mesh_path')
        if mesh_src and Path(mesh_src).exists():
            shutil.copy2(mesh_src, mesh_dest)

        # Dọn file tạm
        for p in filter(None, [raw_src, task.get('temp_mask_path'), proc_src, mesh_src]):
            if Path(p).exists():
                os.remove(p)

        return jsonify({'success': True, 'message': f'Đã lưu với tên {safe_name}'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500