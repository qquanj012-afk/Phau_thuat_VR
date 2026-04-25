import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent   # 3 cấp: utils → web_flask → gốc
DATA_DIR = BASE_DIR / 'data'
TRASH_DIR = DATA_DIR / '.trash'

MEDICAL_EXTS = {'.nii', '.nii.gz', '.dcm', '.dicom', '.mhd', '.mha', '.nrrd', '.png', '.jpg', '.jpeg', '.npy'}
MESH_EXTS = {'.obj', '.stl', '.ply', '.glb', '.gltf'}

def count_files_in_dir(path, extensions):
    """Đếm tất cả file có phần mở rộng nằm trong `extensions` tại `path` (đệ quy)."""
    if not path.exists():
        return 0
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            if any(f.lower().endswith(ext) for ext in extensions):
                total += 1
    return total

def count_img_npy(path):
    """Đếm số file _img.npy (đại diện cho processed)."""
    if not path.exists():
        return 0
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            if f.endswith('_img.npy'):
                total += 1
    return total

def count_subtype(items, subtype):
    return sum(1 for item in items if item.get('subtype') == subtype)

def get_raw_count():
    """Toàn bộ ảnh raw (gồm imagesTr của liver + tumor)."""
    liver = count_files_in_dir(DATA_DIR / 'raw' / 'liver' / 'imagesTr', MEDICAL_EXTS)
    tumor = count_files_in_dir(DATA_DIR / 'raw' / 'tumor', MEDICAL_EXTS)
    return liver + tumor

def get_raw_liver_count():
    return count_files_in_dir(DATA_DIR / 'raw' / 'liver' / 'imagesTr', MEDICAL_EXTS)

def get_raw_tumor_count():
    return count_files_in_dir(DATA_DIR / 'raw' / 'tumor', MEDICAL_EXTS)

def get_processed_count():
    return count_img_npy(DATA_DIR / 'processed' / 'liver') + \
           count_img_npy(DATA_DIR / 'processed' / 'tumor')

def get_mesh_count():
    """Đếm toàn bộ file mesh trong data/meshes (bao gồm tất cả thư mục con)."""
    return count_files_in_dir(DATA_DIR / 'meshes', MESH_EXTS)

def get_trash_count():
    return count_files_in_dir(TRASH_DIR, MEDICAL_EXTS | MESH_EXTS)