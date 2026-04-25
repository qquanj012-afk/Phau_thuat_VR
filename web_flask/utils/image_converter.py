import os
import hashlib
import numpy as np
from PIL import Image, ImageDraw
from pathlib import Path

# Thử import thư viện y tế (có thể không có sẵn, xử lý lỗi)
try:
    import nibabel as nib
    NIB_AVAILABLE = True
except ImportError:
    NIB_AVAILABLE = False

try:
    import pydicom
    DICOM_AVAILABLE = True
except ImportError:
    DICOM_AVAILABLE = False

# Đường dẫn thư mục cache thumbnail (nằm trong static của web_flask)
BASE_DIR = Path(__file__).resolve().parent.parent
THUMBNAIL_CACHE_DIR = BASE_DIR / 'static' / 'thumbnails'
os.makedirs(THUMBNAIL_CACHE_DIR, exist_ok=True)

def get_thumbnail_path(file_path):
    """
    Xác định đường dẫn lưu thumbnail dựa trên cấu trúc thư mục gốc.
    Ví dụ: data/raw/liver/imagesTr/liver_0.nii
           -> static/thumbnails/raw/liver/imagesTr/liver_0.png
    """
    file_path = Path(file_path)
    # Tìm vị trí của 'data' trong đường dẫn
    parts = file_path.parts
    try:
        data_idx = parts.index('data')
    except ValueError:
        # Nếu không có 'data' trong đường dẫn, dùng hash cũ
        return None

    # Lấy phần đường dẫn sau 'data'
    relative = Path(*parts[data_idx + 1:])
    # Thay đuôi file thành .png
    thumb_name = relative.stem + '.png'
    thumb_dir = THUMBNAIL_CACHE_DIR / relative.parent
    thumb_dir.mkdir(parents=True, exist_ok=True)
    return thumb_dir / thumb_name

def _fallback_save(img, file_path):
    """Lưu thumbnail với tên hash (khi không xác định được cấu trúc)."""
    stat = os.stat(file_path)
    hash_input = f"{file_path}_{stat.st_mtime}_{stat.st_size}"
    cache_key = hashlib.md5(hash_input.encode()).hexdigest()
    cache_filename = f"{cache_key}.png"
    cache_path = THUMBNAIL_CACHE_DIR / cache_filename
    img.save(cache_path)
    return f"/static/thumbnails/{cache_filename}"

def generate_thumbnail(file_path, size=(300, 300)):
    """
    Tạo ảnh PNG thumbnail từ nhiều loại file (NIfTI, DICOM, .npy, ảnh thường, .obj).
    Trả về đường dẫn tương đối tới file PNG đã cache (dùng cho web).
    """
    file_path = str(file_path)
    file_path_obj = Path(file_path)
    lower = file_path_obj.suffix.lower()

    # Xác định đường dẫn lưu thumbnail
    thumb_path = get_thumbnail_path(file_path)

    # Nếu đã có cache, trả về URL
    if thumb_path and thumb_path.exists():
        rel = thumb_path.relative_to(THUMBNAIL_CACHE_DIR)
        return f"/static/thumbnails/{rel.as_posix()}"

    # Thử đọc và tạo ảnh
    img_array = None

    # ----- Xử lý file .obj (mesh) -----
    if lower == '.obj':
        img = Image.new('RGB', size, color=(25, 30, 40))
        draw = ImageDraw.Draw(img)
        cx, cy = size[0] // 2, size[1] // 2
        draw.rectangle([cx - 25, cy - 20, cx + 5, cy + 10], fill=(0, 180, 160), outline=(0, 220, 200), width=2)
        draw.polygon([(cx - 25, cy - 20), (cx - 10, cy - 35), (cx + 20, cy - 35), (cx + 5, cy - 20)],
                     fill=(0, 210, 180), outline=(0, 240, 210), width=2)
        draw.polygon([(cx + 5, cy - 20), (cx + 20, cy - 35), (cx + 20, cy - 5), (cx + 5, cy + 10)],
                     fill=(0, 150, 130), outline=(0, 190, 170), width=2)
        short_name = os.path.basename(file_path)[:15] + ('…' if len(os.path.basename(file_path)) > 15 else '')
        draw.text((cx, cy + 45), short_name, fill=(200, 210, 220), anchor="mm")
        draw.text((cx, cy + 60), "[3D Mesh]", fill=(100, 150, 160), anchor="mm")

        if thumb_path:
            img.save(thumb_path)
            rel = thumb_path.relative_to(THUMBNAIL_CACHE_DIR)
            return f"/static/thumbnails/{rel.as_posix()}"
        else:
            # Fallback hash
            return _fallback_save(img, file_path)

    # ----- Xử lý file .npy -----
    if lower == '.npy':
        try:
            data = np.load(file_path)
            if data.ndim == 4:
                slice_idx = data.shape[0] // 2
                img_array = data[slice_idx, :, :, 0]
            elif data.ndim == 3:
                if data.shape[0] < data.shape[2]:
                    img_array = data[:, :, 0]
                else:
                    slice_idx = data.shape[0] // 2
                    img_array = data[slice_idx, :, :]
            elif data.ndim == 2:
                img_array = data
        except Exception as e:
            print(f"Lỗi đọc .npy {file_path}: {e}")

    # NIfTI
    if img_array is None and NIB_AVAILABLE and (lower in ('.nii', '.gz')):
        try:
            img = nib.load(file_path)
            data = img.get_fdata()
            if data.ndim == 3:
                slice_idx = data.shape[2] // 2
                img_array = data[:, :, slice_idx]
            elif data.ndim == 2:
                img_array = data
            elif data.ndim == 4:
                img_array = data[:, :, data.shape[2]//2, 0]
        except Exception as e:
            print(f"Lỗi đọc NIfTI {file_path}: {e}")

    # DICOM
    if img_array is None and DICOM_AVAILABLE and lower in ('.dcm', '.dicom'):
        try:
            ds = pydicom.dcmread(file_path)
            img_array = ds.pixel_array
        except Exception as e:
            print(f"Lỗi đọc DICOM {file_path}: {e}")

    # Ảnh thông thường (PNG, JPG...)
    if img_array is None and lower in ('.png', '.jpg', '.jpeg'):
        try:
            pil_img = Image.open(file_path).convert('L')
            img_array = np.array(pil_img)
        except Exception as e:
            print(f"Lỗi đọc ảnh thường {file_path}: {e}")

    # Nếu không đọc được, tạo ảnh trắng có text
    if img_array is None:
        img = Image.new('RGB', size, color=(30, 30, 40))
        draw = ImageDraw.Draw(img)
        text = os.path.basename(file_path)[:20]
        draw.text((10, size[1]//2), text, fill=(100, 150, 200))
        if thumb_path:
            img.save(thumb_path)
            rel = thumb_path.relative_to(THUMBNAIL_CACHE_DIR)
            return f"/static/thumbnails/{rel.as_posix()}"
        else:
            return _fallback_save(img, file_path)

    # Chuẩn hóa ảnh về 0-255
    img_array = np.array(img_array, dtype=np.float32)
    if img_array.max() > img_array.min():
        img_array = (img_array - img_array.min()) / (img_array.max() - img_array.min())
    else:
        img_array = np.zeros_like(img_array)
    img_array = (img_array * 255).astype(np.uint8)

    # Tạo ảnh PIL, resize về kích thước thumbnail
    img = Image.fromarray(img_array).convert('L')
    img = img.resize(size, Image.Resampling.LANCZOS)

    if thumb_path:
        img.save(thumb_path)
        rel = thumb_path.relative_to(THUMBNAIL_CACHE_DIR)
        return f"/static/thumbnails/{rel.as_posix()}"
    else:
        return _fallback_save(img, file_path)