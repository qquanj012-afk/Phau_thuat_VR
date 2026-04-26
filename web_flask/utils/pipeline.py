"""
Pipeline inference cho web_flask:
  run_pipeline_with_progress()  — pipeline đầy đủ, gọi từ thread trong train/views.py
  run_preprocess_single()       — tiền xử lý đơn lẻ (helper)
  run_mesh_generator()          — tạo mesh 3D (helper)
"""
import os
import re
import sys
import subprocess
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = BASE_DIR / 'train_model' / 'scripts'
TEMP_OUTPUT = BASE_DIR / 'data' / 'temp' / 'output'
TEMP_UPLOAD = BASE_DIR / 'data' / 'temp' / 'uploads'

TEMP_OUTPUT.mkdir(parents=True, exist_ok=True)
TEMP_UPLOAD.mkdir(parents=True, exist_ok=True)


def run_preprocess_single(input_path: Path, output_npy: Path,
                          window_type: str = 'liver') -> bool:
    script = SCRIPTS_DIR / 'preprocess_single.py'
    if not script.exists():
        print("⚠️  preprocess_single.py không tồn tại, bỏ qua.")
        return False
    try:
        subprocess.run(
            [sys.executable, str(script),
             '--input',  str(input_path),
             '--output', str(output_npy),
             '--window', window_type],
            check=True, timeout=300
        )
        return True
    except Exception as e:
        print(f"❌ Lỗi tiền xử lý: {e}")
        return False


def run_mesh_generator(input_seg: Path, output_mesh: Path,
                       upsample: int = 2, sigma: float = 0.8) -> bool:
    script = SCRIPTS_DIR / 'mesh_generator.py'
    if not script.exists():
        print("⚠️  mesh_generator.py không tồn tại.")
        return False
    try:
        subprocess.run(
            [sys.executable, str(script),
             '--input',    str(input_seg),
             '--output',   str(output_mesh),
             '--upsample', str(upsample),
             '--sigma',    str(sigma)],
            check=True, timeout=180
        )
        return True
    except Exception as e:
        print(f"❌ Lỗi tạo mesh: {e}")
        return False


def run_pipeline_with_progress(task, input_path, mask_path,
                                output_path, model_type, threshold):
    from web_flask.utils.image_converter import generate_thumbnail

    task['status']   = 'running'
    task['progress'] = 0

    script_path = SCRIPTS_DIR / 'inference.py'
    task_id     = task['id']
    log_file    = TEMP_OUTPUT / f'{task_id}_inference.log'

    if not script_path.exists():
        task['status'] = 'failed'
        task['error']  = 'Không tìm thấy train_model/scripts/inference.py'
        return

    cmd = [
        sys.executable, str(script_path),
        '--input',      str(input_path),
        '--output',     str(output_path),
        '--model_type', model_type,
        '--threshold',  str(threshold),
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        task['pid'] = process.pid

        with open(log_file, 'w', encoding='utf-8') as log_f:
            for line in process.stdout:
                log_f.write(line)
                log_f.flush()
                m = re.search(r'PROGRESS:(\d+)', line)
                if m:
                    task['progress'] = int(m.group(1))
                if task.get('abort'):
                    process.terminate()
                    task['status'] = 'aborted'
                    return

        process.wait()

        if process.returncode != 0:
            task['status'] = 'failed'
            with open(log_file, 'r', encoding='utf-8') as f:
                task['error'] = (
                    f'inference.py thoát với code {process.returncode}.\n'
                    f'Log (500 ký tự cuối):\n{f.read()[-500:]}'
                )
            return

        task['progress']            = 100
        task['status']              = 'completed'
        task['temp_raw_path']       = str(input_path)
        task['temp_mask_path']      = str(mask_path) if mask_path else None
        task['temp_processed_path'] = str(output_path)

        mesh_path = TEMP_OUTPUT / f'{task_id}_mesh.obj'
        mesh_url  = ''
        if run_mesh_generator(Path(output_path), mesh_path):
            task['temp_mesh_path'] = str(mesh_path)
            if mesh_path.exists():
                mesh_url = generate_thumbnail(str(mesh_path))

        task['result'] = {
            'raw_url':       generate_thumbnail(str(input_path))  if Path(input_path).exists()  else '',
            'processed_url': generate_thumbnail(str(output_path)) if Path(output_path).exists() else '',
            'mesh_url':      mesh_url,
        }

    except Exception as e:
        task['status'] = 'failed'
        task['error']  = str(e)