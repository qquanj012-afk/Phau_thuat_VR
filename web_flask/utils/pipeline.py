"""
Module quản lý pipeline inference: gọi các script trong train_model/scripts/
để xử lý ảnh upload từ web.
"""
import subprocess
import sys
import uuid
import shutil
from pathlib import Path

# Đường dẫn gốc dự án
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TRAIN_MODEL_DIR = BASE_DIR / 'train_model'
SCRIPTS_DIR = TRAIN_MODEL_DIR / 'scripts'

# Đường dẫn dữ liệu tạm
DATA_DIR = BASE_DIR / 'data'
TEMP_DIR = DATA_DIR / 'temp'
TEMP_UPLOAD = TEMP_DIR / 'uploads'
TEMP_OUTPUT = TEMP_DIR / 'output'
TEMP_UPLOAD.mkdir(parents=True, exist_ok=True)
TEMP_OUTPUT.mkdir(parents=True, exist_ok=True)


def run_preprocess_single(input_path: Path, output_npy: Path, window_type='liver'):
    """
    Gọi script preprocess_single.py (nếu có) để tiền xử lý 1 ảnh.
    Trả về True nếu thành công.
    """
    script = SCRIPTS_DIR / 'preprocess_single.py'
    if not script.exists():
        print("⚠️ preprocess_single.py không tồn tại, bỏ qua tiền xử lý.")
        return False
    cmd = [
        sys.executable, str(script),
        '--input', str(input_path),
        '--output', str(output_npy),
        '--window', window_type
    ]
    try:
        subprocess.run(cmd, check=True, timeout=300)
        return True
    except Exception as e:
        print(f"❌ Lỗi tiền xử lý: {e}")
        return False


def run_inference_single(input_npy: Path, output_seg: Path, model_type='liver', threshold=0.5):
    """
    Gọi script inference.py (hoặc inference_single.py) để chạy inference.
    Trả về True nếu thành công.
    """
    script = SCRIPTS_DIR / 'inference.py'
    if not script.exists():
        script = SCRIPTS_DIR / 'inference_single.py'
    if not script.exists():
        raise FileNotFoundError("Không tìm thấy script inference.py hoặc inference_single.py")

    cmd = [
        sys.executable, str(script),
        '--input', str(input_npy),
        '--output', str(output_seg),
        '--model_type', model_type,
        '--threshold', str(threshold)
    ]
    subprocess.run(cmd, check=True, timeout=600)
    return True


def run_mesh_generator(input_seg: Path, output_mesh: Path):
    """
    Gọi script mesh_generator.py để tạo mesh 3D.
    Trả về True nếu thành công.
    """
    script = SCRIPTS_DIR / 'mesh_generator.py'
    if not script.exists():
        print("⚠️ mesh_generator.py không tồn tại.")
        return False
    cmd = [
        sys.executable, str(script),
        '--input', str(input_seg),
        '--output', str(output_mesh)
    ]
    try:
        subprocess.run(cmd, check=True, timeout=120)
        return True
    except Exception as e:
        print(f"❌ Lỗi tạo mesh: {e}")
        return False


def process_uploaded_file(input_path: Path, model_type='liver', threshold=0.5):
    """
    Pipeline đầy đủ cho 1 file upload: tiền xử lý -> inference -> mesh.
    Trả về dict chứa đường dẫn các file kết quả.
    """
    task_id = str(uuid.uuid4())[:8]
    npy_path = TEMP_OUTPUT / f"{task_id}_preprocessed.npy"
    seg_path = TEMP_OUTPUT / f"{task_id}_seg.nii.gz"
    mesh_path = TEMP_OUTPUT / f"{task_id}_mesh.obj"

    result = {
        'raw_path': input_path,
        'processed_path': None,
        'mesh_path': None
    }

    # 1. Tiền xử lý (nếu có script)
    if run_preprocess_single(input_path, npy_path, model_type):
        inference_input = npy_path
    else:
        inference_input = input_path  # fallback

    # 2. Inference
    try:
        run_inference_single(inference_input, seg_path, model_type, threshold)
        result['processed_path'] = seg_path
    except Exception as e:
        print(f"❌ Inference thất bại: {e}")
        return result

    # 3. Tạo mesh
    if run_mesh_generator(seg_path, mesh_path):
        result['mesh_path'] = mesh_path

    return result