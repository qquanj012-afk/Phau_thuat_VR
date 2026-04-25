# train_model/scripts/check_format.py
import argparse
import sys
from pathlib import Path

import numpy as np
import nibabel as nib


def check_nifti(file_path: Path):
    """Đọc file .nii/.nii.gz và in thông tin."""
    img = nib.load(file_path)
    data = img.get_fdata()
    header = img.header
    zooms = header.get_zooms()[:3]

    print(f"📂 Định dạng: NIfTI")
    print(f"   Kích thước: {data.shape}")
    print(f"   Kiểu dữ liệu: {data.dtype}")
    print(f"   Min / Max: {data.min():.2f} / {data.max():.2f}")
    print(f"   Spacing (x, y, z): {zooms}")
    if data.ndim == 3:
        print(f"   Số lát cắt (z): {data.shape[2]}")
        mid = data.shape[2] // 2
        slice_mid = data[:, :, mid]
        print(f"   Lát giữa (z={mid}): min={slice_mid.min():.2f}, max={slice_mid.max():.2f}, "
              f"unique values={len(np.unique(slice_mid))}")


def check_numpy(file_path: Path):
    """Đọc file .npy và in thông tin."""
    data = np.load(file_path)
    print(f"📂 Định dạng: NumPy (.npy)")
    print(f"   Kích thước: {data.shape}")
    print(f"   Kiểu dữ liệu: {data.dtype}")
    print(f"   Min / Max: {data.min():.4f} / {data.max():.4f}")

    if data.ndim == 2:
        print(f"   Lát 2D: unique={len(np.unique(data))}")
    elif data.ndim == 3:
        mid = data.shape[0] // 2
        slice_mid = data[mid, :, :]
        print(f"   Lát giữa (axis=0, index={mid}): shape={slice_mid.shape}, "
              f"min={slice_mid.min():.4f}, max={slice_mid.max():.4f}")
    elif data.ndim == 4:
        print(f"   Tensor 4D: có thể là ảnh đã xử lý (D, H, W, C)")


def main():
    parser = argparse.ArgumentParser(description="Kiểm tra định dạng tệp .nii / .npy")
    parser.add_argument("--input", help="Đường dẫn tới file (.nii, .nii.gz, .npy). "
                                        "Nếu không truyền, script sẽ hỏi bạn nhập.")
    args = parser.parse_args()

    if args.input:
        file_path = Path(args.input)
    else:
        # Nhập trực tiếp từ bàn phím
        path_str = input("📁 Nhập đường dẫn file: ").strip().strip('"').strip("'")
        file_path = Path(path_str)

    if not file_path.exists():
        print(f"❌ File không tồn tại: {file_path}")
        sys.exit(1)

    suffix = file_path.suffix.lower()
    if suffix == '.npy':
        check_numpy(file_path)
    elif suffix in ('.nii', '.gz'):
        check_nifti(file_path)
    else:
        # Thử dùng nibabel cho các định dạng không có đuôi chuẩn
        try:
            check_nifti(file_path)
        except Exception:
            print(f"❌ Định dạng không được hỗ trợ hoặc file lỗi: {file_path}")

if __name__ == "__main__":
    main()