import os
import hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
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

def generate_thumbnail(file_path, size=(300, 300)):
    """
    Tạo ảnh PNG thumbnail từ file ảnh y tế (NIfTI, DICOM) hoặc ảnh thường.
    Trả về đường dẫn tương đối tới file PNG đã cache (dùng cho web).
    """
    file_path = str(file_path)
    stat = os.stat(file_path)
    hash_input = f"{file_path}_{stat.st_mtime}_{stat.st_size}"
    cache_key = hashlib.md5(hash_input.encode()).hexdigest()
    cache_filename = f"{cache_key}.png"
    cache_path = THUMBNAIL_CACHE_DIR / cache_filename
    cache_url = f"/static/thumbnails/{cache_filename}"

    # Nếu đã có cache, trả về URL
    if cache_path.exists():
        return cache_url

    # Thử đọc và tạo ảnh
    img_array = None
    lower = file_path.lower()

    # ----- Xử lý file .obj (mesh) -----
    if lower.endswith('.obj'):
        img = Image.new('RGB', size, color=(20, 25, 35))
        draw = ImageDraw.Draw(img)
        text = "3D MESH"
        # Dùng font mặc định
        bbox = draw.textbbox((0, 0), text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        draw.text(((size[0] - text_width) // 2, (size[1] - text_height) // 2),
                  text, fill=(0, 212, 170))
        img.save(cache_path)
        return cache_url

    # NIfTI
    if NIB_AVAILABLE and (lower.endswith('.nii') or lower.endswith('.nii.gz')):
        try:
            img = nib.load(file_path)
            data = img.get_fdata()
            if data.ndim == 3:
                slice_idx = data.shape[2] // 2
                img_array = data[:, :, slice_idx]
            elif data.ndim == 2:
                img_array = data
            else:
                img_array = data[:, :, data.shape[2]//2, 0] if data.ndim == 4 else None
        except Exception as e:
            print(f"Lỗi đọc NIfTI {file_path}: {e}")

    # DICOM
    elif DICOM_AVAILABLE and (lower.endswith('.dcm') or lower.endswith('.dicom')):
        try:
            ds = pydicom.dcmread(file_path)
            img_array = ds.pixel_array
        except Exception as e:
            print(f"Lỗi đọc DICOM {file_path}: {e}")

    # Ảnh thông thường (PNG, JPG...)
    elif lower.endswith(('.png', '.jpg', '.jpeg')):
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
        img.save(cache_path)
        return cache_url

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
    img.save(cache_path)

    return cache_url