import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import nibabel as nib
import numpy as np
from tqdm import tqdm

from config import RAW_DATA_DIR, PROCESSED_DIR, TARGET_SIZE
from utils.image_processing import preprocess_slice, apply_liver_window


def preprocess_dataset(raw_dir: Path, processed_dir: Path, target_size: tuple):
    """Tiền xử lý toàn bộ tập dữ liệu."""
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Lấy tất cả file .nii / .nii.gz
    files = list(raw_dir.glob("*.nii*"))
    if not files:
        print(f"⚠️ Không tìm thấy file nào trong {raw_dir}")
        return

    for file_path in tqdm(files, desc="Đang tiền xử lý"):
        try:
            img = nib.load(file_path)
            data = img.get_fdata()
            if data.ndim == 4:
                data = data[..., 0]  # Lấy volume đầu tiên nếu là 4D
            elif data.ndim == 2:
                data = data[:, :, np.newaxis]

            processed_slices = []
            for i in range(data.shape[2]):
                slice_img = data[:, :, i]
                # Áp dụng window cho gan (có thể đổi thành tumor nếu cần)
                processed = preprocess_slice(slice_img, apply_liver_window, target_size)
                processed_slices.append(processed)

            output_path = processed_dir / f"{file_path.stem}.npy"
            np.save(output_path, np.array(processed_slices, dtype=np.float32))
        except Exception as e:
            print(f"Lỗi khi xử lý {file_path.name}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Tiền xử lý tập dữ liệu CT.")
    parser.add_argument("--type", choices=["liver", "tumor"], default="liver",
                        help="Loại dữ liệu cần xử lý")
    args = parser.parse_args()

    raw_dir = RAW_DATA_DIR / args.type
    processed_dir = PROCESSED_DIR / args.type

    if not raw_dir.exists():
        print(f"❌ Thư mục raw không tồn tại: {raw_dir}")
        sys.exit(1)

    print(f"🔄 Tiền xử lý dữ liệu {args.type}...")
    preprocess_dataset(raw_dir, processed_dir, TARGET_SIZE)
    print(f"✅ Hoàn thành! Dữ liệu đã lưu tại {processed_dir}")


if __name__ == "__main__":
    main()