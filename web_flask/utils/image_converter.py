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

def generate_thumbnail(file_path, size=(300, 300)):
    """
    Tạo ảnh PNG thumbnail từ nhiều loại file (NIfTI, DICOM, .npy, ảnh thường, .obj).
    Trả về đường dẫn tương đối tới file PNG đã cache (dùng cho web).
    """
    file_path = str(file_path)
    # Tạo tên cache dựa trên hash của đường dẫn và thời gian sửa đổi
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
        # Tạo ảnh nền tối với hiệu ứng gradient đơn giản
        img = Image.new('RGB', size, color=(25, 30, 40))
        draw = ImageDraw.Draw(img)

        # Vẽ một hình lập phương cách điệu (đại diện cho 3D)
        cx, cy = size[0] // 2, size[1] // 2
        # Mặt trước
        draw.rectangle([cx - 25, cy - 20, cx + 5, cy + 10], fill=(0, 180, 160), outline=(0, 220, 200), width=2)
        # Mặt trên (giả 3D)
        draw.polygon([(cx - 25, cy - 20), (cx - 10, cy - 35), (cx + 20, cy - 35), (cx + 5, cy - 20)],
                     fill=(0, 210, 180), outline=(0, 240, 210), width=2)
        # Mặt bên phải
        draw.polygon([(cx + 5, cy - 20), (cx + 20, cy - 35), (cx + 20, cy - 5), (cx + 5, cy + 10)],
                     fill=(0, 150, 130), outline=(0, 190, 170), width=2)

        # Thêm tên file (rút gọn)
        short_name = os.path.basename(file_path)[:15] + ('…' if len(os.path.basename(file_path)) > 15 else '')
        draw.text((cx, cy + 45), short_name, fill=(200, 210, 220), anchor="mm")
        draw.text((cx, cy + 60), "[3D Mesh]", fill=(100, 150, 160), anchor="mm")

        img.save(cache_path)
        return cache_url

    # ----- Xử lý file .npy -----
    if lower.endswith('.npy'):
        try:
            data = np.load(file_path)
            if data.ndim == 4:
                # Shape (Slices, Height, Width, Channels) → lấy lát giữa, kênh đầu tiên (ảnh CT)
                slice_idx = data.shape[0] // 2
                img_array = data[slice_idx, :, :, 0]
            elif data.ndim == 3:
                # Có thể là (H, W, C) hoặc (Slices, H, W)
                if data.shape[0] < data.shape[2]:  # (H, W, C)
                    img_array = data[:, :, 0]
                else:  # (Slices, H, W)
                    slice_idx = data.shape[0] // 2
                    img_array = data[slice_idx, :, :]
            elif data.ndim == 2:
                img_array = data
            else:
                img_array = None
        except Exception as e:
            print(f"Lỗi đọc .npy {file_path}: {e}")

    # NIfTI
    if img_array is None and NIB_AVAILABLE and (lower.endswith('.nii') or lower.endswith('.nii.gz')):
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
    if img_array is None and DICOM_AVAILABLE and (lower.endswith('.dcm') or lower.endswith('.dicom')):
        try:
            ds = pydicom.dcmread(file_path)
            img_array = ds.pixel_array
        except Exception as e:
            print(f"Lỗi đọc DICOM {file_path}: {e}")

    # Ảnh thông thường (PNG, JPG...)
    if img_array is None and lower.endswith(('.png', '.jpg', '.jpeg')):
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