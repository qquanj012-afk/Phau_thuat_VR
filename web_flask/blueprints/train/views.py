import os
import sys
import uuid
import shutil
import subprocess
import threading
import time
import requests
import base64
import re
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify, url_for
from werkzeug.utils import secure_filename

train_bp = Blueprint('train', __name__, template_folder='../../templates')

# Đường dẫn dự án
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
WEB_FLASK_DIR = BASE_DIR / 'web_flask'
TRAIN_MODEL_DIR = BASE_DIR / 'train_model'
SCRIPTS_DIR = TRAIN_MODEL_DIR / 'scripts'
DATA_DIR = BASE_DIR / 'data'

TEMP_UPLOAD = DATA_DIR / 'temp' / 'uploads'
TEMP_OUTPUT = DATA_DIR / 'temp' / 'output'
os.makedirs(TEMP_UPLOAD, exist_ok=True)
os.makedirs(TEMP_OUTPUT, exist_ok=True)

RAW_DIR = DATA_DIR / 'raw' / 'liver'
PROCESSED_DIR = DATA_DIR / 'processed' / 'liver'
MESH_DIR = DATA_DIR / 'meshes'
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(MESH_DIR, exist_ok=True)

# Import image_converter từ web_flask.utils
sys.path.append(str(WEB_FLASK_DIR))
from utils.image_converter import generate_thumbnail

tasks = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'nii', 'gz', 'dcm', 'png', 'jpg', 'jpeg'}

def download_from_url(url, save_path):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, stream=True, headers=headers, timeout=30)
    response.raise_for_status()
    with open(save_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

def save_data_url(data_url, save_path):
    header, encoded = data_url.split(',', 1)
    ext_match = re.search(r'data:image/(\w+);base64', header)
    ext = ext_match.group(1) if ext_match else 'jpg'
    if ext == 'jpeg':
        ext = 'jpg'
    file_data = base64.b64decode(encoded)
    base, _ = os.path.splitext(save_path)
    save_path = f"{base}.{ext}"
    with open(save_path, 'wb') as f:
        f.write(file_data)
    return save_path

def run_inference_async(task_id, input_path, output_path, model_type, threshold):
    task = tasks[task_id]
    task['status'] = 'running'
    task['progress'] = 0

    script_path = SCRIPTS_DIR / 'inference.py'
    log_file = TEMP_OUTPUT / f'{task_id}_inference.log'

    if not script_path.exists():
        task['status'] = 'failed'
        task['error'] = f'Script inference.py không tồn tại'
        return

    cmd = [
        sys.executable, str(script_path),
        '--input', str(input_path),
        '--output', str(output_path),
        '--model_type', model_type,
        '--threshold', str(threshold)
    ]

    try:
        with open(log_file, 'w', encoding='utf-8') as log_f:
            process = subprocess.Popen(cmd, stdout=log_f, stderr=subprocess.STDOUT)
            task['pid'] = process.pid

            while process.poll() is None:
                if task.get('abort'):
                    process.terminate()
                    task['status'] = 'aborted'
                    return
                # Giả lập tiến độ (có thể cải tiến sau)
                if (TEMP_OUTPUT / f"{task_id}_seg.nii.gz").exists():
                    task['progress'] = min(task['progress'] + 1, 99)
                time.sleep(1)

            if process.returncode == 0:
                task['progress'] = 100
                task['status'] = 'completed'
                task['temp_raw_path'] = str(input_path)
                task['temp_processed_path'] = str(output_path)

                # Tạo mesh
                mesh_path = TEMP_OUTPUT / f"{task_id}_mesh.obj"
                mesh_script = SCRIPTS_DIR / 'mesh_generator.py'
                mesh_url = ''
                if mesh_script.exists():
                    try:
                        subprocess.run([
                            sys.executable, str(mesh_script),
                            '--input', str(output_path),
                            '--output', str(mesh_path)
                        ], check=True, timeout=120)
                        task['temp_mesh_path'] = str(mesh_path)
                        mesh_url = generate_thumbnail(str(mesh_path)) if mesh_path.exists() else ''
                    except Exception as e:
                        print(f"Mesh generation failed: {e}")

                raw_thumb = generate_thumbnail(str(input_path)) if Path(input_path).exists() else ''
                processed_thumb = generate_thumbnail(str(output_path)) if Path(output_path).exists() else ''
                task['result'] = {
                    'raw_url': raw_thumb,
                    'processed_url': processed_thumb,
                    'mesh_url': mesh_url,
                    'tumor_size': '2.4 × 3.1 × 2.8 cm',
                    'location': 'Thùy gan phải, segment VI',
                    'dice': 0.891
                }
            else:
                task['status'] = 'failed'
                with open(log_file, 'r') as f:
                    task['error'] = f'Script exited with code {process.returncode}. Log: {f.read()[-500:]}'
    except Exception as e:
        task['status'] = 'failed'
        task['error'] = str(e)

@train_bp.route('/')
def train_page():
    return render_template('train.html')

@train_bp.route('/start', methods=['POST'])
def start_training():
    model = request.form.get('model', 'resunet')
    threshold = request.form.get('threshold', '0.85')
    label = request.form.get('label', '').strip()

    task_id = str(uuid.uuid4())
    model_type = 'liver' if 'liver' in model.lower() else 'tumor'

    input_path = None
    filename = None

    if 'file' in request.files:
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Chưa chọn file'}), 400
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            input_path = TEMP_UPLOAD / f"{task_id}_{filename}"
            file.save(str(input_path))
        else:
            return jsonify({'error': 'Định dạng file không được hỗ trợ'}), 400
    else:
        url = request.form.get('url', '').strip()
        if not url:
            return jsonify({'error': 'Vui lòng nhập URL'}), 400
        if not label:
            return jsonify({'error': 'Vui lòng nhập Tên bệnh nhân (nhãn)'}), 400

        base_filename = label.replace(' ', '_') if label else 'downloaded'
        input_path = TEMP_UPLOAD / f"{task_id}_{secure_filename(base_filename)}.jpg"
        try:
            if url.startswith('data:image/'):
                input_path = Path(save_data_url(url, str(input_path)))
            else:
                download_from_url(url, str(input_path))
        except Exception as e:
            return jsonify({'error': f'Lỗi xử lý URL: {str(e)}'}), 400

    output_path = TEMP_OUTPUT / f"{task_id}_seg.nii.gz"

    tasks[task_id] = {
        'id': task_id,
        'status': 'pending',
        'progress': 0,
        'filename': filename or input_path.name,
        'label': label,
        'created_at': datetime.now().isoformat(),
        'input_path': str(input_path),
        'output_path': str(output_path),
        'model': model,
        'threshold': threshold
    }

    thread = threading.Thread(target=run_inference_async,
                              args=(task_id, str(input_path), str(output_path), model_type, threshold))
    thread.daemon = True
    thread.start()

    return jsonify({'task_id': task_id, 'message': 'Inference started'})

@train_bp.route('/status/<task_id>')
def training_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task không tồn tại'}), 404
    return jsonify({'progress': task.get('progress', 0), 'status': task.get('status', 'unknown')})

@train_bp.route('/result/<task_id>')
def training_result(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task không tồn tại'}), 404
    if task['status'] != 'completed':
        return jsonify({'error': 'Inference chưa hoàn tất'}), 400
    return jsonify(task.get('result', {}))

@train_bp.route('/save', methods=['POST'])
def save_result():
    data = request.get_json()
    task_id = data.get('task_id')
    custom_name = data.get('name', '').strip()

    task = tasks.get(task_id)
    if not task or task['status'] != 'completed':
        return jsonify({'success': False, 'error': 'Task không hợp lệ hoặc chưa hoàn tất'}), 400

    if not custom_name:
        custom_name = task.get('label') or f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    safe_name = secure_filename(custom_name)
    if not safe_name:
        safe_name = f"result_{task_id[:8]}"

    raw_ext = Path(task['temp_raw_path']).suffix
    raw_dest = RAW_DIR / f"{safe_name}{raw_ext}"
    processed_dest = PROCESSED_DIR / f"{safe_name}_seg.nii.gz"
    mesh_dest = MESH_DIR / f"{safe_name}.obj"

    existing = []
    if raw_dest.exists(): existing.append('raw')
    if processed_dest.exists(): existing.append('processed')
    if mesh_dest.exists(): existing.append('meshes')
    if existing:
        return jsonify({'success': False, 'error': f'Tên đã tồn tại trong: {", ".join(existing)}'}), 409

    try:
        if Path(task['temp_raw_path']).exists():
            shutil.copy2(task['temp_raw_path'], raw_dest)
        if Path(task['temp_processed_path']).exists():
            shutil.copy2(task['temp_processed_path'], processed_dest)
        if task.get('temp_mesh_path') and Path(task['temp_mesh_path']).exists():
            shutil.copy2(task['temp_mesh_path'], mesh_dest)

        # Xóa file tạm
        for p in [task['temp_raw_path'], task['temp_processed_path'], task.get('temp_mesh_path')]:
            if p and Path(p).exists():
                os.remove(p)

        return jsonify({'success': True, 'message': f'Đã lưu với tên {safe_name}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500