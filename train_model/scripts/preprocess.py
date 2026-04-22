import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import nibabel as nib
import numpy as np
from tqdm import tqdm

from config import RAW_DATA_DIR, PROCESSED_DIR, TARGET_SIZE
from utils.image_processing import preprocess_slice, apply_liver_window, apply_tumor_window


def find_nifti_files(raw_dir: Path):
    """Tìm đệ quy tất cả file .nii và .nii.gz trong thư mục raw."""
    return list(raw_dir.glob("**/*.nii")) + list(raw_dir.glob("**/*.nii.gz"))


def preprocess_dataset(raw_dir: Path, processed_dir: Path, target_size: tuple, window_type: str):
    """Tiền xử lý toàn bộ ảnh NIfTI trong raw_dir và lưu thành .npy vào processed_dir."""
    processed_dir.mkdir(parents=True, exist_ok=True)

    files = find_nifti_files(raw_dir)
    if not files:
        print(f"⚠️ Không tìm thấy file .nii/.nii.gz nào trong {raw_dir}")
        return

    window_func = apply_liver_window if window_type == 'liver' else apply_tumor_window

    for file_path in tqdm(files, desc="Đang tiền xử lý"):
        try:
            img = nib.load(file_path)
            data = img.get_fdata()
            if data.ndim == 4:
                data = data[..., 0]
            elif data.ndim == 2:
                data = data[:, :, np.newaxis]

            processed_slices = []
            for i in range(data.shape[2]):
                slice_img = data[:, :, i]
                processed = preprocess_slice(slice_img, window_func, target_size)
                processed_slices.append(processed)

            # Lưu với tên file gốc (bỏ đuôi .nii/.gz)
            output_name = file_path.name.replace('.nii.gz', '').replace('.nii', '')
            output_path = processed_dir / f"{output_name}.npy"
            np.save(output_path, np.array(processed_slices, dtype=np.float32))

        except Exception as e:
            print(f"Lỗi khi xử lý {file_path.name}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Tiền xử lý tập dữ liệu CT.")
    parser.add_argument("--dataset", choices=["liver", "tumor"], default="liver",
                        help="Loại dữ liệu cần xử lý (mặc định: liver)")
    args = parser.parse_args()

    raw_dir = RAW_DATA_DIR / args.dataset
    processed_dir = PROCESSED_DIR / args.dataset

    if not raw_dir.exists():
        print(f"❌ Thư mục raw không tồn tại: {raw_dir}")
        sys.exit(1)

    print(f"🔄 Tiền xử lý dữ liệu {args.dataset}...")
    preprocess_dataset(raw_dir, processed_dir, TARGET_SIZE, args.dataset)
    print(f"✅ Hoàn thành! Dữ liệu đã lưu tại {processed_dir}")


if __name__ == "__main__":
    main()