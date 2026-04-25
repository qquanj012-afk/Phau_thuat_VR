import cv2
import numpy as np
from PIL import Image

# Import config
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import TARGET_SIZE, LIVER_WINDOW, TUMOR_WINDOW, ADD_COORDINATE_CHANNELS

def apply_window(img, window_center, window_width):
    """Áp dụng cửa sổ CT (windowing) và chuẩn hóa về [0,1]."""
    img_min = window_center - window_width // 2
    img_max = window_center + window_width // 2
    img_clipped = np.clip(img, img_min, img_max)
    img_8bit = cv2.normalize(img_clipped, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(img_8bit) / 255.0

def apply_liver_window(img):
    """Áp dụng window cho gan."""
    return apply_window(img, *LIVER_WINDOW)

def apply_tumor_window(img):
    """Áp dụng window cho u."""
    return apply_window(img, *TUMOR_WINDOW)

def add_coordinate_channels(img_size):
    """Tạo kênh tọa độ X, Y chuẩn hóa về [0,1]."""
    h, w = img_size
    xx, yy = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, h))
    return xx.astype(np.float32), yy.astype(np.float32)


def preprocess_slice(slice_img, window_func, target_size):
    """
    Tiền xử lý một lát cắt CT.
    Nếu target_size = (0,0) thì giữ nguyên kích thước.
    """
    # Áp dụng cửa sổ HU (ví dụ liver window)
    img_win = window_func(slice_img)

    # Resize nếu target_size > 0
    if target_size[0] > 0 and target_size[1] > 0:
        img_res = cv2.resize(img_win, target_size, interpolation=cv2.INTER_LINEAR)
    else:
        img_res = img_win

    # Chuẩn hóa về [0, 1]
    img_min, img_max = img_res.min(), img_res.max()
    if img_max - img_min > 1e-8:
        img_norm = (img_res - img_min) / (img_max - img_min)
    else:
        img_norm = img_res - img_min

    return img_norm.astype(np.float32)

def load_and_preprocess_volume(file_path, window_type='liver'):
    """
    Đọc file ảnh (NIfTI hoặc PNG/JPG) và tiền xử lý toàn bộ volume.
    Trả về mảng (Slices, H, W, C).
    """
    import nibabel as nib
    lower = file_path.lower()
    window_func = apply_liver_window if window_type == 'liver' else apply_tumor_window

    if lower.endswith('.nii') or lower.endswith('.nii.gz'):
        img_obj = nib.load(file_path)
        img_data = img_obj.get_fdata()
        if img_data.ndim == 4:
            img_data = img_data[..., 0]
        elif img_data.ndim == 2:
            img_data = img_data[:, :, np.newaxis]
    else:
        pil_img = Image.open(file_path).convert('L')
        img_2d = np.array(pil_img).astype(np.float32)
        img_data = img_2d[:, :, np.newaxis]

    processed_slices = []
    for i in range(img_data.shape[2]):
        slice_img = img_data[:, :, i]
        processed = preprocess_slice(slice_img, window_func)
        processed_slices.append(processed)

    return np.array(processed_slices).astype(np.float32)